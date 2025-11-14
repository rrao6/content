"""High-level service for querying content info."""
from typing import Dict, Iterable, List, Optional

import structlog

from exceptions import ContentNotFoundError
from models import ContentInfo, PosterImage
from repository import ContentRepository

logger = structlog.get_logger(__name__)


class ContentService:
    """Provides business-friendly methods backed by ContentRepository."""

    def __init__(self, repository: Optional[ContentRepository] = None) -> None:
        self.repository = repository or ContentRepository()

    def get_content(self, content_id: str) -> List[ContentInfo]:
        """Return all records for a content id."""
        try:
            return self.repository.get_by_id(content_id)
        except ContentNotFoundError:
            logger.warning("content_not_found", content_id=content_id)
            raise

    def get_first_content(self, content_id: str) -> ContentInfo:
        """Return the newest record for a content id."""
        records = self.get_content(content_id)
        return records[0]

    def get_bulk_content(self, content_ids: List[str]) -> Dict[int, List[ContentInfo]]:
        """Return records grouped by content id."""
        return self.repository.get_batch(content_ids)

    def search(self, title_keyword: str, limit: int = 25) -> List[ContentInfo]:
        """Search by title keyword."""
        return self.repository.search_by_title(title_keyword, limit=limit)

    def iter_poster_images(
        self,
        batch_size: int = 1000,
        only_active: bool = True,
        require_url: bool = True,
        max_items: Optional[int] = None,
    ) -> Iterable[PosterImage]:
        """Stream poster image URLs for Gemini validation workflows."""
        return self.repository.iter_poster_images(
            batch_size=batch_size,
            only_active=only_active,
            require_url=require_url,
            max_items=max_items,
        )

