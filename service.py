"""High-level service for querying content info."""
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import structlog
from cachetools import TTLCache, cached

from config import DatabricksConfig, get_config
from exceptions import ContentNotFoundError
from models import ContentInfo, PosterImage
from repository import ContentRepository
from sot_repository import SOTRepository, EligibleTitle

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


class EligibleTitlesService:
    """Service for managing eligible titles from Sources of Truth."""
    
    def __init__(
        self, 
        repository: Optional[SOTRepository] = None,
        config: Optional[DatabricksConfig] = None
    ) -> None:
        self.repository = repository or SOTRepository()
        self.config = config or get_config()
        # Build cache with TTL from config
        cache_ttl_seconds = getattr(self.config, 'sot_cache_ttl_hours', 1) * 3600
        self._cache = TTLCache(maxsize=100, ttl=cache_ttl_seconds)
    
    @cached(cache=lambda self: self._cache, key=lambda self, days_back, sot_types: f"titles_{days_back}_{sot_types}")
    def fetch_eligible_titles(
        self,
        days_back: int = 7,
        sot_types: Optional[List[str]] = None,
    ) -> List[EligibleTitle]:
        """
        Fetch eligible titles with caching.
        
        Args:
            days_back: Number of days to look back
            sot_types: Filter by specific SOT types
            
        Returns:
            List of eligible titles
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(
            "fetching_eligible_titles_service",
            days_back=days_back,
            sot_types=sot_types,
        )
        
        return self.repository.get_eligible_titles(
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
        )
    
    def get_eligible_poster_images(
        self,
        days_back: int = 7,
        sot_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[EligibleTitle]:
        """
        Get eligible titles that have poster images.
        
        Returns:
            List of eligible titles with poster URLs
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        titles = self.repository.get_eligible_titles_with_content(
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
            limit=limit,
        )
        
        # Filter to only those with poster URLs
        return [t for t in titles if t.poster_img_url]
    
    def iter_eligible_poster_images(
        self,
        days_back: int = 7,
        sot_types: Optional[List[str]] = None,
        batch_size: int = 500,
        max_items: Optional[int] = None,
    ) -> Iterable[EligibleTitle]:
        """
        Stream eligible titles with poster images.
        
        Yields:
            EligibleTitle objects with poster URLs
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        return self.repository.iter_eligible_titles_with_content(
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
            batch_size=batch_size,
            max_items=max_items,
        )
    
    def count_eligible_titles(
        self,
        days_back: int = 7,
    ) -> Dict[str, int]:
        """
        Get count of eligible titles by SOT type.
        
        Returns:
            Dictionary mapping SOT name to count
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        return self.repository.count_eligible_titles_by_sot(
            start_date=start_date,
            end_date=end_date,
        )
    
    def get_eligible_program_ids(
        self,
        days_back: int = 7,
        sot_types: Optional[List[str]] = None,
    ) -> List[int]:
        """
        Get just the program IDs of eligible titles.
        
        Returns:
            List of program IDs
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        return self.repository.get_eligible_program_ids(
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
        )
    
    def clear_cache(self) -> None:
        """Clear the eligible titles cache."""
        self._cache.clear()
        logger.info("eligible_titles_cache_cleared")

