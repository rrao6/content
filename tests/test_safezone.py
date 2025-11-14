from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from analysis import PosterAnalysisPipeline, PosterAnalysisResult, SafeZoneAnalyzer, SAFE_ZONE_PROMPT
from models import PosterImage


class DummyClient:
    def __init__(self, text: str):
        self.text = text

    class DummyResponses:
        def __init__(self, text: str):
            self.text = text

        def create(self, *_, **__):
            content = SimpleNamespace(type="output_text", text=self.text)
            output = SimpleNamespace(content=[content])
            return SimpleNamespace(output=[output])

    @property
    def responses(self):
        return self.DummyResponses(self.text)


def test_safe_zone_analyzer_parses_json():
    client = DummyClient(
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


def test_pipeline_collects_results():
    analyzer = MagicMock()
    analyzer.analyze.side_effect = [
        {"top_safe_zone": {}, "bottom_safe_zone": {}},
        Exception("vision failure"),
    ]
    service = MagicMock()
    service.iter_poster_images.return_value = [
        PosterImage(content_id=1, poster_img_url="https://img/1.jpg"),
        PosterImage(content_id=2, poster_img_url="https://img/2.jpg"),
    ]

    class DummyConfig:
        pass

    pipeline = PosterAnalysisPipeline(service, analyzer, config=DummyConfig())
    results = pipeline.run(limit=2)

    assert len(results) == 2
    assert results[0].analysis is not None
    assert results[1].error == "vision failure"

