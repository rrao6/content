"""Repository for fetching eligible titles from Sources of Truth."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Generator, Tuple
from dataclasses import dataclass

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import DatabricksConfig, get_config
from connection import get_cursor
from exceptions import DatabricksConnectionError, DatabricksQueryError
from sot_query import (
    get_eligible_titles_query,
    get_eligible_titles_with_content_query,
    get_eligible_titles_count_query,
)

logger = structlog.get_logger(__name__)


@dataclass
class EligibleTitle:
    """Represents an eligible title from SOT."""
    program_id: int
    sot_name: str
    content_id: Optional[int] = None
    content_name: Optional[str] = None
    content_type: Optional[str] = None
    poster_img_url: Optional[str] = None
    
    @classmethod
    def from_row(cls, row) -> "EligibleTitle":
        """Create from database row."""
        return cls(
            program_id=getattr(row, "program_id", None),
            sot_name=getattr(row, "sot_name", None),
            content_id=getattr(row, "content_id", None),
            content_name=getattr(row, "content_name", None),
            content_type=getattr(row, "content_type", None),
            poster_img_url=getattr(row, "poster_img_url", None),
        )


class SOTRepository:
    """Repository for accessing eligible titles from Sources of Truth."""
    
    def __init__(self, config: Optional[DatabricksConfig] = None):
        self.config = config or get_config()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DatabricksConnectionError),
    )
    def get_eligible_titles(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sot_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[EligibleTitle]:
        """
        Fetch eligible titles from SOTs.
        
        Args:
            start_date: Start of date range (defaults to 7 days ago)
            end_date: End of date range (defaults to today)
            sot_types: Filter by specific SOT types
            limit: Maximum number of results
            
        Returns:
            List of eligible titles
        """
        query = get_eligible_titles_query(start_date, end_date, sot_types)
        
        if limit:
            query += f" LIMIT {limit}"
        
        logger.info(
            "fetching_eligible_titles",
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
            limit=limit,
        )
        
        try:
            with get_cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                
                titles = [
                    EligibleTitle(
                        program_id=row.program_id,
                        sot_name=row.sot_name
                    )
                    for row in rows
                ]
                
                logger.info(
                    "eligible_titles_fetched",
                    count=len(titles),
                )
                
                return titles
                
        except Exception as exc:
            logger.error(
                "eligible_titles_query_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise DatabricksQueryError(f"Failed to fetch eligible titles: {exc}") from exc
    
    def get_eligible_titles_with_content(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sot_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[EligibleTitle]:
        """
        Fetch eligible titles with content info including poster URLs.
        
        Returns:
            List of eligible titles with content details
        """
        query = get_eligible_titles_with_content_query(start_date, end_date, sot_types)
        
        if limit:
            query += f" LIMIT {limit}"
        
        logger.info(
            "fetching_eligible_titles_with_content",
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
            limit=limit,
        )
        
        try:
            with get_cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                
                titles = [EligibleTitle.from_row(row) for row in rows]
                
                logger.info(
                    "eligible_titles_with_content_fetched",
                    count=len(titles),
                    with_posters=sum(1 for t in titles if t.poster_img_url),
                )
                
                return titles
                
        except Exception as exc:
            logger.error(
                "eligible_titles_content_query_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise DatabricksQueryError(f"Failed to fetch eligible titles with content: {exc}") from exc
    
    def iter_eligible_titles_with_content(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sot_types: Optional[List[str]] = None,
        batch_size: int = 500,
        max_items: Optional[int] = None,
    ) -> Generator[EligibleTitle, None, None]:
        """
        Stream eligible titles with content info in batches.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            sot_types: Filter by specific SOT types
            batch_size: Number of records per batch
            max_items: Maximum total items to yield
            
        Yields:
            EligibleTitle objects
        """
        query = get_eligible_titles_with_content_query(start_date, end_date, sot_types)
        
        logger.info(
            "streaming_eligible_titles",
            start_date=start_date,
            end_date=end_date,
            sot_types=sot_types,
            batch_size=batch_size,
            max_items=max_items,
        )
        
        try:
            with get_cursor() as cursor:
                cursor.execute(query)
                
                total_yielded = 0
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    
                    for row in rows:
                        if max_items and total_yielded >= max_items:
                            logger.info(
                                "eligible_titles_stream_limit_reached",
                                yielded=total_yielded,
                            )
                            return
                        
                        yield EligibleTitle.from_row(row)
                        total_yielded += 1
                
                logger.info(
                    "eligible_titles_stream_complete",
                    total_yielded=total_yielded,
                )
                
        except Exception as exc:
            logger.error(
                "eligible_titles_stream_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise DatabricksQueryError(f"Failed to stream eligible titles: {exc}") from exc
    
    def get_eligible_program_ids(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sot_types: Optional[List[str]] = None,
    ) -> List[int]:
        """
        Get just the program IDs for efficient filtering.
        
        Returns:
            List of program IDs
        """
        titles = self.get_eligible_titles(start_date, end_date, sot_types)
        return list(set(title.program_id for title in titles))
    
    def count_eligible_titles_by_sot(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get count of eligible titles by SOT type.
        
        Returns:
            Dictionary mapping SOT name to title count
        """
        query = get_eligible_titles_count_query(start_date, end_date)
        
        logger.info(
            "counting_eligible_titles",
            start_date=start_date,
            end_date=end_date,
        )
        
        try:
            with get_cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                
                counts = {row.sot_name: row.title_count for row in rows}
                
                logger.info(
                    "eligible_titles_counted",
                    total=sum(counts.values()),
                    by_sot=counts,
                )
                
                return counts
                
        except Exception as exc:
            logger.error(
                "eligible_titles_count_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise DatabricksQueryError(f"Failed to count eligible titles: {exc}") from exc
