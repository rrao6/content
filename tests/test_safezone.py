from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from analysis import (
    PosterAnalysisPipeline,
    PosterAnalysisResult,
    SafeZoneAnalyzer,
    SAFE_ZONE_PROMPT,
    VisionAPIError,
    ResponseParsingError,
    ImageDownloadError,
)
from models import PosterImage


class DummyChatClient:
    def __init__(self, text: str):
        self.text = text

    class DummyChatCompletions:
        def __init__(self, text: str):
            self.text = text

        def create(self, *_, **__):
            message = SimpleNamespace(
                content=[SimpleNamespace(type="text", text=self.text)]
            )
            choice = SimpleNamespace(message=message)
            return SimpleNamespace(choices=[choice])

    class DummyChat:
        def __init__(self, text: str):
            self.completions = DummyChatClient.DummyChatCompletions(text)

    @property
    def chat(self):
        return DummyChatClient.DummyChat(self.text)


def test_safe_zone_analyzer_parses_json():
    client = DummyChatClient(
        '{"top_safe_zone":{"contains_key_elements":false,"confidence":95,"justification":"clear"},'
        '"bottom_safe_zone":{"contains_key_elements":true,"confidence":80,"justification":"text"}}'
    )
    analyzer = SafeZoneAnalyzer(
        provider="openai",
        model="test-model",
        prompt=SAFE_ZONE_PROMPT,
        api_key="dummy",
        client=client,
    )

    result = analyzer.analyze("https://example.com/poster.jpg")
    assert result["top_safe_zone"]["contains_key_elements"] is False
    assert result["bottom_safe_zone"]["confidence"] == 80


@patch('analysis.get_analysis_cache')
def test_pipeline_collects_results(mock_get_cache):
    # Mock the cache
    mock_cache = MagicMock()
    mock_cache.get.return_value = None  # No cache hits
    mock_cache.wait_if_needed.return_value = None  # No rate limiting
    mock_get_cache.return_value = mock_cache
    
    analyzer = MagicMock()
    analyzer.analyze.side_effect = [
        {"top_safe_zone": {}, "bottom_safe_zone": {}},
        VisionAPIError("vision failure"),
    ]
    service = MagicMock()
    service.iter_poster_images.return_value = [
        PosterImage(content_id=1, poster_img_url="https://img/1.jpg"),
        PosterImage(content_id=2, poster_img_url="https://img/2.jpg"),
    ]

    class DummyConfig:
        enable_analysis_cache = True
        cache_expiry_hours = 24
        vision_requests_per_minute = 30

    pipeline = PosterAnalysisPipeline(service, analyzer, config=DummyConfig())
    results = pipeline.run(limit=2, download_images=False)  # Skip download for test

    assert len(results) == 2
    assert results[0].analysis is not None
    assert "vision failure" in results[1].error
    
    # Verify cache interactions
    assert mock_cache.get.call_count == 2
    assert mock_cache.put.call_count == 1  # Only successful result cached
    assert mock_cache.record_request.call_count == 2


def test_safe_zone_analyzer_handles_errors():
    """Test that analyzer properly handles and raises specific error types."""
    # Test API error
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API error")
    
    analyzer = SafeZoneAnalyzer(
        provider="openai",
        model="test-model",
        prompt=SAFE_ZONE_PROMPT,
        api_key="dummy",
        client=client,
    )
    
    with pytest.raises(VisionAPIError) as exc_info:
        analyzer.analyze("https://example.com/poster.jpg")
    assert "API error" in str(exc_info.value)
    
    # Test parsing error
    client2 = DummyChatClient("not valid json")
    analyzer2 = SafeZoneAnalyzer(
        provider="openai",
        model="test-model",
        prompt=SAFE_ZONE_PROMPT,
        api_key="dummy",
        client=client2,
    )
    
    with pytest.raises(ResponseParsingError) as exc_info:
        analyzer2.analyze("https://example.com/poster.jpg")
    assert "non-JSON output" in str(exc_info.value)


@patch('analysis._download_image_to_base64')
@patch('analysis.get_analysis_cache')
def test_pipeline_with_image_download(mock_get_cache, mock_download):
    """Test pipeline with image download enabled."""
    # Mock cache
    mock_cache = MagicMock()
    mock_cache.get.return_value = None
    mock_cache.wait_if_needed.return_value = None
    mock_cache.get_stats.return_value = {'size': 0, 'enabled': True}
    mock_get_cache.return_value = mock_cache
    
    # Mock download
    mock_download.return_value = "data:image/png;base64,iVBORw0KGgo..."
    
    # Mock analyzer
    analyzer = MagicMock()
    analyzer.analyze.return_value = {
        "top_safe_zone": {"contains_key_elements": True},
        "bottom_safe_zone": {"contains_key_elements": False}
    }
    
    # Mock service
    service = MagicMock()
    service.iter_poster_images.return_value = [
        PosterImage(content_id=1, poster_img_url="http://img.adrise.tv/test.png"),
    ]
    
    pipeline = PosterAnalysisPipeline(service, analyzer)
    results = pipeline.run(limit=1, download_images=True)
    
    assert len(results) == 1
    assert results[0].analysis is not None
    assert mock_download.call_count == 1
    assert analyzer.analyze.call_args[0][0].startswith("data:image/png;base64,")


@patch('analysis.get_analysis_cache')
def test_pipeline_with_cache_hit(mock_get_cache):
    """Test pipeline when result is found in cache."""
    # Mock cache with a hit
    cached_result = {
        "top_safe_zone": {"contains_key_elements": False},
        "bottom_safe_zone": {"contains_key_elements": True}
    }
    mock_cache = MagicMock()
    mock_cache.get.return_value = cached_result
    mock_cache.get_stats.return_value = {'size': 1, 'enabled': True}
    mock_get_cache.return_value = mock_cache
    
    # Mock analyzer (should not be called due to cache hit)
    analyzer = MagicMock()
    
    # Mock service
    service = MagicMock()
    service.iter_poster_images.return_value = [
        PosterImage(content_id=1, poster_img_url="https://img/1.jpg"),
    ]
    
    pipeline = PosterAnalysisPipeline(service, analyzer)
    results = pipeline.run(limit=1)
    
    assert len(results) == 1
    assert results[0].analysis == cached_result
    assert analyzer.analyze.call_count == 0  # Should not call analyzer
    assert mock_cache.put.call_count == 0  # Should not store in cache


@patch('analysis._download_image_to_base64')
@patch('analysis.get_analysis_cache')
def test_pipeline_download_failure(mock_get_cache, mock_download):
    """Test pipeline handling of download failures."""
    # Mock cache
    mock_cache = MagicMock()
    mock_cache.get.return_value = None
    mock_cache.get_stats.return_value = {'size': 0, 'enabled': True}
    mock_get_cache.return_value = mock_cache
    
    # Mock download failure
    mock_download.side_effect = ImageDownloadError("Network error")
    
    # Mock service
    service = MagicMock()
    service.iter_poster_images.return_value = [
        PosterImage(content_id=1, poster_img_url="http://img.adrise.tv/test.png"),
    ]
    
    analyzer = MagicMock()
    pipeline = PosterAnalysisPipeline(service, analyzer)
    results = pipeline.run(limit=1, download_images=True)
    
    assert len(results) == 1
    assert results[0].analysis is None
    assert "Image download failed" in results[0].error
    assert analyzer.analyze.call_count == 0  # Should not analyze if download fails

