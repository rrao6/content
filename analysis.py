"""Poster safe-zone analysis pipeline backed by vision models."""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Union

import requests
import structlog
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config import DatabricksConfig, get_config
from models import PosterImage
from service import ContentService
from analysis_cache import get_analysis_cache
from monitoring import get_analysis_monitor

logger = structlog.get_logger(__name__)


# Custom exceptions for better error handling
class VisionProviderError(Exception):
    """Base exception for vision provider errors."""
    pass


class ImageDownloadError(VisionProviderError):
    """Raised when image download fails."""
    pass


class VisionAPIError(VisionProviderError):
    """Raised when vision API call fails."""
    pass


class ResponseParsingError(VisionProviderError):
    """Raised when response parsing fails."""
    pass


# Use technical UI prompt for better compatibility and fewer refusals
SAFE_ZONE_PROMPT = """You are analyzing a movie poster for UI overlay compatibility.
Examine ONLY the top-left rectangular region (60% width, 10% height) of the poster.

Identify if this region contains:
1. Any text (title, credits, taglines, logos)
2. Human facial features (eyes, nose, mouth, clear faces)

This is for technical UI placement, not content review. Focus only on spatial positioning.

Return JSON:
{
  "red_safe_zone": {
    "contains_key_elements": boolean,
    "confidence": 0-100,
    "justification": "brief technical explanation"
  }
}

Return only JSON."""

# Fallback prompt for simpler analysis
SIMPLE_SAFE_ZONE_PROMPT = """Check top-left corner (60% width, 10% height) for text or faces.
Return JSON only:
{
  "red_safe_zone": {
    "contains_key_elements": boolean,
    "confidence": 0-100,
    "justification": "explanation"
  }
}"""


class VisionProviderError(Exception):
    """Raised when no supported vision provider is configured."""


class ImageDownloadError(VisionProviderError):
    """Raised when image download fails."""
    pass


class VisionAPIError(VisionProviderError):
    """Raised when vision API call fails."""
    pass


class ResponseParsingError(VisionProviderError):
    """Raised when response parsing fails."""
    pass


def _create_retry_session(retries: int = 3, backoff_factor: float = 0.3) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    before_sleep=before_sleep_log(logger, log_level="warning"),
    reraise=True,
)
def _download_image_to_base64(
    url: str, 
    timeout: int = 20, 
    max_size_mb: int = 10
) -> str:
    """
    Download image from URL and convert to base64 data URI.
    
    Args:
        url: Image URL to download
        timeout: Request timeout in seconds
        max_size_mb: Maximum image size in megabytes
        
    Returns:
        Base64-encoded data URI suitable for OpenAI API
        
    Raises:
        ImageDownloadError: If download fails
    """
    try:
        session = _create_retry_session()
        
        # Stream the download to check size
        response = session.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        # Check content length if provided
        content_length = response.headers.get('content-length')
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if content_length and int(content_length) > max_size_bytes:
            raise ImageDownloadError(f"Image too large: {int(content_length)} bytes")
        
        # Download with size limit
        chunks = []
        total_size = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
                total_size += len(chunk)
                if total_size > max_size_bytes:
                    raise ImageDownloadError(
                        f"Image exceeds {max_size_mb}MB limit during download"
                    )
        
        # Combine chunks
        image_data = b''.join(chunks)
        
        # Determine MIME type
        content_type = response.headers.get('content-type', 'image/png')
        if not content_type.startswith('image/'):
            content_type = 'image/png'  # Default fallback
            
        # Encode to base64
        base64_data = base64.b64encode(image_data).decode('ascii')
        data_uri = f"data:{content_type};base64,{base64_data}"
        
        logger.info(
            "image_downloaded",
            url=url,
            size_bytes=total_size,
            content_type=content_type,
        )
        
        return data_uri
        
    except requests.RequestException as exc:
        logger.error(
            "image_download_failed",
            url=url,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise ImageDownloadError(f"Failed to download image from {url}: {exc}") from exc
    except Exception as exc:
        logger.error(
            "image_processing_failed", 
            url=url,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise ImageDownloadError(f"Failed to process image from {url}: {exc}") from exc


class SafeZoneAnalyzer:
    """Wrapper around a vision model (OpenAI, Gemini, etc.)."""

    def __init__(
        self,
        provider: str,
        model: str,
        prompt: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.prompt = (prompt or SAFE_ZONE_PROMPT).strip()
        self.api_key = api_key
        self.client = client or self._build_client()

    def _build_client(self):
        if self.provider == "openai":
            if not self.api_key:
                raise VisionProviderError(
                    "OPENAI_API_KEY is not configured but provider=openai was requested."
                )
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise VisionProviderError("openai package is not installed.") from exc

            return OpenAI(api_key=self.api_key)

        raise VisionProviderError(f"Unsupported vision provider: {self.provider}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, VisionAPIError)),
        before_sleep=before_sleep_log(logger, log_level="warning"),
        reraise=True,
    )
    def analyze(self, image_input: Union[str, Dict[str, str]]) -> Dict[str, Any]:
        """
        Send the poster to the configured model and parse JSON output.
        
        Args:
            image_input: Either a URL string or a dict with 'url' or 'base64' key
            
        Returns:
            Parsed JSON response with safe zone analysis
            
        Raises:
            VisionAPIError: If the API call fails
            ResponseParsingError: If response parsing fails
        """
        if not image_input:
            raise ValueError("image_input must be provided")

        # Handle different input formats
        if isinstance(image_input, str):
            image_url = image_input
        elif isinstance(image_input, dict):
            image_url = image_input.get('url') or image_input.get('base64')
            if not image_url:
                raise ValueError("image_input dict must contain 'url' or 'base64' key")
        else:
            raise ValueError("image_input must be a string or dict")

        if self.provider == "openai":
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON-only API that analyzes images. You MUST respond with ONLY valid JSON, no markdown formatting, no code blocks, no explanations outside the JSON structure. If you cannot analyze an image, return {\"error\": \"Cannot analyze image\"}.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.prompt + "\n\nIMPORTANT: Respond ONLY with the JSON object, no markdown code blocks, no explanations."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                    ],
                )
            except Exception as exc:
                logger.error(
                    "vision_api_call_failed",
                    provider=self.provider,
                    model=self.model,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise VisionAPIError(f"Vision API call failed: {exc}") from exc
        else:  # pragma: no cover
            raise VisionProviderError(f"Unsupported provider: {self.provider}")

        try:
            text = self._extract_chat_text(response)
            
            # Clean up the text - remove markdown code blocks if present
            text = self._clean_json_response(text)
            
            parsed = json.loads(text)
            
            # Handle error responses from the model
            if isinstance(parsed, dict) and 'error' in parsed:
                # Model explicitly said it can't analyze
                logger.warning(
                    "model_cannot_analyze",
                    reason=parsed.get('error', 'Unknown'),
                )
                # Return a default "safe" response
                return {
                    "red_safe_zone": {
                        "contains_key_elements": None,
                        "confidence": 0,
                        "justification": f"Model unable to analyze: {parsed.get('error', 'Unknown error')}"
                    }
                }
            
            # Validate expected structure
            if not isinstance(parsed, dict):
                raise ValueError("Response must be a JSON object")
            
            if 'red_safe_zone' not in parsed:
                raise ValueError("Response missing required red_safe_zone key")
                
            return parsed
            
        except json.JSONDecodeError as exc:
            logger.error("vision_non_json_output", output=text[:500])  # Limit log size
            raise ResponseParsingError("Vision model returned non-JSON output") from exc
        except Exception as exc:
            logger.error(
                "response_parsing_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise ResponseParsingError(f"Failed to parse response: {exc}") from exc

    def analyze_with_fallback(self, image_input: Union[str, Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze image with fallback strategies if the primary analysis fails.
        
        Tries:
        1. Primary analysis with current prompt
        2. If model refuses, try with simple prompt
        3. If still failing, try with gpt-4o-mini model
        
        Returns:
            Analysis result with metadata about which strategy succeeded
        """
        strategies = [
            ("primary", self.model, self.prompt),
            ("simple", self.model, SIMPLE_SAFE_ZONE_PROMPT),
            ("mini_model", "gpt-4o-mini", self.prompt),
        ]
        
        last_error = None
        
        for strategy_name, model, prompt in strategies:
            try:
                # Create analyzer for this strategy
                if strategy_name == "primary":
                    # Use self for primary
                    result = self.analyze(image_input)
                else:
                    # Create new analyzer for other strategies
                    temp_analyzer = SafeZoneAnalyzer(
                        provider=self.provider,
                        model=model,
                        api_key=self.api_key,
                        prompt=prompt
                    )
                    result = temp_analyzer.analyze(image_input)
                
                # Check if refused
                if result.get("red_safe_zone", {}).get("confidence", 0) == 0:
                    logger.warning(
                        "strategy_refused",
                        strategy=strategy_name,
                        model=model,
                    )
                    last_error = "Model refused to analyze"
                    # Small delay before next attempt
                    time.sleep(0.5)
                    continue
                
                # Success!
                logger.info(
                    "strategy_success",
                    strategy=strategy_name,
                    confidence=result["red_safe_zone"]["confidence"],
                )
                
                # Add metadata
                if "_metadata" not in result:
                    result["_metadata"] = {}
                result["_metadata"]["strategy"] = strategy_name
                result["_metadata"]["model"] = model
                
                return result
                
            except Exception as e:
                logger.error(
                    "strategy_failed",
                    strategy=strategy_name,
                    error=str(e),
                )
                last_error = str(e)
                # Small delay before next attempt
                time.sleep(0.5)
        
        # All strategies failed
        logger.error(
            "all_strategies_failed",
            last_error=last_error,
        )
        
        return {
            "red_safe_zone": {
                "contains_key_elements": None,
                "confidence": 0,
                "justification": f"Unable to analyze after trying all strategies. Last error: {last_error}"
            },
            "_metadata": {
                "strategy": "failed",
                "error": last_error,
            }
        }
    
    @staticmethod
    def _clean_json_response(text: str) -> str:
        """Remove markdown code blocks and other formatting from JSON response."""
        original_text = text
        text = text.strip()
        
        # Method 1: Remove markdown code blocks (```json ... ``` or ``` ... ```)
        if "```" in text:
            # Handle ```json\n{...}\n``` format
            import re
            json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
            matches = re.findall(json_pattern, text, re.DOTALL)
            if matches:
                text = matches[0].strip()
            else:
                # Fallback: just remove ``` markers
                text = text.replace("```json", "").replace("```", "").strip()
        
        # Method 2: Extract JSON object/array using regex
        if not text.startswith('{') and not text.startswith('['):
            # Try to find JSON object in the text
            json_object_pattern = r'(\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\})'
            matches = re.findall(json_object_pattern, text, re.DOTALL)
            if matches:
                # Take the longest match (likely the complete JSON)
                text = max(matches, key=len)
        
        # Method 3: Handle inline code blocks
        if text.startswith("`") and text.endswith("`"):
            text = text[1:-1].strip()
        
        # Method 4: If the response contains "error" but isn't JSON, make it JSON
        if "cannot analyze" in text.lower() or "unable to analyze" in text.lower():
            if not text.startswith('{'):
                return json.dumps({"error": text})
        
        # Final cleanup
        text = text.strip()
        
        # Validate it's likely JSON
        if not (text.startswith('{') or text.startswith('[')):
            logger.warning(
                "cleaned_text_not_json",
                original=original_text[:200],
                cleaned=text[:200]
            )
        
        return text
    
    @staticmethod
    def _extract_chat_text(response: Any) -> str:
        """Extract text content from an OpenAI chat completion response."""
        choices = getattr(response, "choices", [])
        if not choices:
            raise ValueError("Vision model returned no choices")
        message = choices[0].message
        content = getattr(message, "content", None)
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            pieces: List[str] = []
            for part in content:
                part_type = getattr(part, "type", None) or part.get("type")
                if part_type in {"text", "output_text"}:
                    value = getattr(part, "text", None) or part.get("text")
                    if value:
                        pieces.append(value)
            text = "".join(pieces)
        else:
            text = ""

        text = (text or "").strip()
        if not text:
            raise ValueError("Vision model returned empty content")
        return text


@dataclass
class PosterAnalysisResult:
    content_id: Optional[int]
    poster_img_url: Optional[str]
    analysis: Optional[Dict[str, Any]]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_id": self.content_id,
            "poster_img_url": self.poster_img_url,
            "analysis": self.analysis,
            "error": self.error,
        }


class PosterAnalysisPipeline:
    """Coordinates fetching poster URLs and sending them to the analyzer."""

    def __init__(
        self,
        service: ContentService,
        analyzer: SafeZoneAnalyzer,
        config: Optional[DatabricksConfig] = None,
    ) -> None:
        self.service = service
        self.analyzer = analyzer
        self.config = config or get_config()
        self.cache = get_analysis_cache()
        self.monitor = get_analysis_monitor()

    def run(
        self,
        limit: Optional[int],
        batch_size: int = 100,
        include_inactive: bool = False,
        allow_null_urls: bool = False,
        download_images: bool = True,
        download_timeout: int = 20,
        use_fallback: bool = True,
    ) -> List[PosterAnalysisResult]:
        """
        Analyze poster images and return structured responses.
        
        Args:
            limit: Maximum number of posters to analyze
            batch_size: Number of posters to fetch per database query
            include_inactive: Whether to include inactive content
            allow_null_urls: Whether to allow null poster URLs
            download_images: Whether to download images to base64 (fixes HTTP issues)
            download_timeout: Timeout for image downloads in seconds
            use_fallback: Whether to use fallback strategies if primary analysis fails
        """
        results: List[PosterAnalysisResult] = []
        iterator = self.service.iter_poster_images(
            batch_size=batch_size,
            only_active=not include_inactive,
            require_url=not allow_null_urls,
            max_items=limit,
        )

        total_processed = 0
        download_failures = 0
        analysis_failures = 0
        
        for poster in iterator:
            if not poster.poster_img_url:
                continue
                
            total_processed += 1
            original_url = poster.poster_img_url
            request_start_time = self.monitor.record_request_start()
            
            # Check cache first
            cached_analysis = self.cache.get(poster.content_id, original_url)
            if cached_analysis is not None:
                results.append(
                    PosterAnalysisResult(
                        content_id=poster.content_id,
                        poster_img_url=original_url,
                        analysis=cached_analysis,
                    )
                )
                logger.info(
                    "poster_analysis_cache_hit",
                    content_id=poster.content_id,
                )
                self.monitor.record_request_end(
                    start_time=request_start_time,
                    success=True,
                    cache_hit=True,
                )
                continue
            
            # Apply rate limiting before making API call
            self.cache.wait_if_needed()
            
            try:
                # Download image to base64 if enabled (recommended for HTTP URLs)
                if download_images:
                    try:
                        download_start = time.time()
                        image_data = _download_image_to_base64(
                            original_url, 
                            timeout=download_timeout
                        )
                        download_duration_ms = (time.time() - download_start) * 1000
                        self.monitor.record_download_duration(download_duration_ms)
                        logger.info(
                            "image_ready_for_analysis",
                            content_id=poster.content_id,
                            method="download_base64",
                            download_ms=download_duration_ms,
                        )
                    except ImageDownloadError as exc:
                        download_failures += 1
                        logger.error(
                            "image_download_failed",
                            content_id=poster.content_id,
                            url=original_url,
                            error=str(exc),
                        )
                        results.append(
                            PosterAnalysisResult(
                                content_id=poster.content_id,
                                poster_img_url=original_url,
                                analysis=None,
                                error=f"Image download failed: {exc}",
                            )
                        )
                        self.monitor.record_request_end(
                            start_time=request_start_time,
                            success=False,
                            error_type="ImageDownloadError",
                            error_message=str(exc),
                        )
                        continue
                else:
                    # Use URL directly (may fail for HTTP URLs with OpenAI)
                    image_data = original_url
                    logger.info(
                        "image_ready_for_analysis",
                        content_id=poster.content_id,
                        method="direct_url",
                    )
                
                # Analyze the image
                self.cache.record_request()  # Record for rate limiting
                api_start = time.time()
                
                # Use fallback method if enabled
                if use_fallback:
                    analysis = self.analyzer.analyze_with_fallback(image_data)
                else:
                    analysis = self.analyzer.analyze(image_data)
                    
                api_duration_ms = (time.time() - api_start) * 1000
                self.monitor.record_api_duration(api_duration_ms)
                
                # Cache the successful result
                self.cache.put(poster.content_id, original_url, analysis)
                
                results.append(
                    PosterAnalysisResult(
                        content_id=poster.content_id,
                        poster_img_url=original_url,
                        analysis=analysis,
                    )
                )
                logger.info(
                    "poster_analysis_success",
                    content_id=poster.content_id,
                    api_ms=api_duration_ms,
                )
                self.monitor.record_request_end(
                    start_time=request_start_time,
                    success=True,
                    cache_hit=False,
                )
                
            except (VisionAPIError, ResponseParsingError) as exc:
                analysis_failures += 1
                logger.error(
                    "poster_analysis_failed",
                    content_id=poster.content_id,
                    poster_url=original_url,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                results.append(
                    PosterAnalysisResult(
                        content_id=poster.content_id,
                        poster_img_url=original_url,
                        analysis=None,
                        error=str(exc),
                    )
                )
                self.monitor.record_request_end(
                    start_time=request_start_time,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            except Exception as exc:  # pragma: no cover - unexpected errors
                analysis_failures += 1
                logger.error(
                    "poster_analysis_unexpected_error",
                    content_id=poster.content_id,
                    poster_url=original_url,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                results.append(
                    PosterAnalysisResult(
                        content_id=poster.content_id,
                        poster_img_url=original_url,
                        analysis=None,
                        error=f"Unexpected error: {exc}",
                    )
                )
                self.monitor.record_request_end(
                    start_time=request_start_time,
                    success=False,
                    error_type="UnexpectedError",
                    error_message=str(exc),
                )
                
        # Log summary statistics
        successful_results = [r for r in results if r.analysis is not None]
        cache_stats = self.cache.get_stats()
        monitor_stats = self.monitor.get_health_status()
        
        logger.info(
            "poster_analysis_batch_complete",
            total_processed=total_processed,
            successful=len(successful_results),
            download_failures=download_failures,
            analysis_failures=analysis_failures,
            cache_hits=total_processed - download_failures - analysis_failures - len(successful_results) + sum(1 for r in successful_results if hasattr(r, '_from_cache')),
            cache_size=cache_stats['size'],
            cache_enabled=cache_stats['enabled'],
            monitor_health=monitor_stats['status'],
            monitor_alerts=monitor_stats['alerts'],
        )
        
        return results

