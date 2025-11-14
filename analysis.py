"""Poster safe-zone analysis pipeline backed by vision models."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import structlog

from config import DatabricksConfig, get_config
from models import PosterImage
from service import ContentService

logger = structlog.get_logger(__name__)

SAFE_ZONE_PROMPT = """Task Overview:
You are an expert visual analysis model. You will analyze a movie poster image and evaluate whether any key visual or textual elements appear inside designated "safe zones."

Safe Zones Definition:

Top Safe Zone: A rectangle centered horizontally that spans 60% of the poster width and 10% of the height, flush with the top edge (assumes 9:16 aspect ratio).

Bottom Safe Zone: A rectangle centered horizontally that spans 60% of the poster width and 10% of the height, flush with the bottom edge.
These regions should ideally remain clear of important text or faces (think of a horizontal "red band" occupying the middle 60% of the width near the edges).

Output Format (JSON):

{
  "top_safe_zone": {
    "contains_key_elements": true,
    "confidence": 90,
    "justification": "The movie title text is clearly visible within the top safe zone."
  },
  "bottom_safe_zone": {
    "contains_key_elements": false,
    "confidence": 95,
    "justification": "No text or faces appear in the bottom safe zone; only part of the subject's clothing and background are visible."
  }
}


Judging Criteria:

For each safe zone (top and bottom):

Key Element Definition:
Only the following count as key elements:

Text (e.g., title, credits, taglines, logos, or any readable overlayed words)

Human faces or significant parts of faces (eyes, mouth, full facial profile)

Ignore non-textual decorative elements, background colors, props, or clothing.

Confidence Scoring (0–100):

90–100: Very clear detection or absence of key elements.

60–89: Partial visibility or uncertain boundary.

0–59: Minimal or no relevant elements detected.

Justification:
Write 1–3 concise sentences explaining what you observed and how it affects your judgment.

Instructions for the Model:

Analyze the uploaded poster image visually.

Examine only the top and bottom safe zones (each 10% of total height).

Identify whether text or human faces appear in these regions.

Ignore all other objects or background details.

Return only the JSON result (no extra commentary).
"""


class VisionProviderError(Exception):
    """Raised when no supported vision provider is configured."""


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

    def analyze(self, image_url: str) -> Dict[str, Any]:
        """Send the poster URL to the configured model and parse JSON output."""
        if not image_url:
            raise ValueError("image_url must be provided")

        if self.provider == "openai":
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": self.prompt},
                            {"type": "input_image", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=0,
                max_output_tokens=1024,
            )
        else:  # pragma: no cover
            raise VisionProviderError(f"Unsupported provider: {self.provider}")

        text = self._extract_text(response)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("vision_non_json_output", output=text)
            raise ValueError("Vision model returned non-JSON output") from exc
        return parsed

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract concatenated text content from OpenAI Responses API."""
        chunks: List[str] = []
        for output in getattr(response, "output", []):
            for content in getattr(output, "content", []):
                if getattr(content, "type", None) in {"output_text", "text"}:
                    chunks.append(getattr(content, "text", ""))
        if not chunks:
            raise ValueError("Vision model returned no text output")
        return "".join(chunks).strip()


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

    def run(
        self,
        limit: Optional[int],
        batch_size: int = 100,
        include_inactive: bool = False,
        allow_null_urls: bool = False,
    ) -> List[PosterAnalysisResult]:
        """Analyze poster images and return structured responses."""
        results: List[PosterAnalysisResult] = []
        iterator = self.service.iter_poster_images(
            batch_size=batch_size,
            only_active=not include_inactive,
            require_url=not allow_null_urls,
            max_items=limit,
        )

        for poster in iterator:
            if not poster.poster_img_url:
                continue
            try:
                analysis = self.analyzer.analyze(poster.poster_img_url)
                results.append(
                    PosterAnalysisResult(
                        content_id=poster.content_id,
                        poster_img_url=poster.poster_img_url,
                        analysis=analysis,
                    )
                )
            except Exception as exc:  # pragma: no cover - we log and continue
                logger.error(
                    "poster_analysis_failed",
                    content_id=poster.content_id,
                    poster_url=poster.poster_img_url,
                    error=str(exc),
                )
                results.append(
                    PosterAnalysisResult(
                        content_id=poster.content_id,
                        poster_img_url=poster.poster_img_url,
                        analysis=None,
                        error=str(exc),
                    )
                )
        return results

