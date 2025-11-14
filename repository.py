"""Databricks repository for content_info queries."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from cache import memoize
from config import DatabricksConfig, get_config
from connection import get_cursor
from exceptions import (
    ContentNotFoundError,
    DatabricksQueryError,
    InvalidContentIdError,
)
from models import ContentInfo, PosterImage

logger = structlog.get_logger(__name__)


def _validate_content_id(content_id: str) -> str:
    if not content_id or not content_id.strip():
        raise InvalidContentIdError("content_id cannot be empty")
    return content_id.strip()


class ContentRepository:
    """Handles SQL queries against the content_info table."""

    def __init__(self, config: Optional[DatabricksConfig] = None) -> None:
        self.config = config or get_config()

    def _base_select(self) -> str:
        return f"""
            SELECT
                content_id,
                content_name,
                is_episode,
                program_name,
                program_id,
                content_type,
                parent_id,
                import_id,
                publisher_id,
                active,
                policy,
                content_partner_id,
                gracenote_id,
                program_gracenote_id,
                duration,
                cue_points,
                credit_cue_point,
                rating,
                mpaa_rating,
                tvpg_rating,
                poster_img_url
            FROM {self.config.fully_qualified_table}
        """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(DatabricksQueryError),
        reraise=True,
    )
    def _execute(self, query: str, params: Iterable) -> List[ContentInfo]:
        try:
            with get_cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        except Exception as exc:
            logger.error("databricks_query_failed", query=query, error=str(exc))
            raise DatabricksQueryError(str(exc)) from exc

        return [ContentInfo.from_row(row) for row in rows]

    @memoize
    def get_by_id(self, content_id: str) -> List[ContentInfo]:
        """Return all records for a content_id."""
        content_id = _validate_content_id(content_id)
        query = self._base_select() + " WHERE content_id = ? ORDER BY content_id"
        records = self._execute(query, [content_id])
        if not records:
            raise ContentNotFoundError(f"No content found for id={content_id}")
        return records

    def get_batch(self, content_ids: List[str]) -> Dict[int, List[ContentInfo]]:
        """Return records for multiple content_ids."""
        cleaned_ids = [_validate_content_id(cid) for cid in content_ids]
        if not cleaned_ids:
            return {}

        placeholders = ",".join(["?"] * len(cleaned_ids))
        query = (
            self._base_select()
            + f" WHERE content_id IN ({placeholders}) ORDER BY content_id"
        )
        records = self._execute(query, cleaned_ids)

        result: Dict[int, List[ContentInfo]] = {}
        for record in records:
            result.setdefault(record.content_id, []).append(record)
        return result

    def search_by_title(self, title_keyword: str, limit: int = 25) -> List[ContentInfo]:
        """Search content by title keyword."""
        if not title_keyword or len(title_keyword.strip()) < 2:
            raise InvalidContentIdError("Provide at least 2 characters for search")
        term = f"%{title_keyword.strip()}%"
        query = (
            self._base_select()
            + " WHERE content_name ILIKE ? ORDER BY content_id DESC LIMIT ?"
        )
        return self._execute(query, [term, limit])

    def iter_poster_images(
        self,
        batch_size: int = 1000,
        only_active: bool = True,
        require_url: bool = True,
        max_items: Optional[int] = None,
    ):
        """
        Iterate over poster image URLs in batches.

        Args:
            batch_size: Number of rows per fetchmany call.
            only_active: Restrict results to active content.
            require_url: Skip rows without poster URLs.
        Yields:
            PosterImage objects.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        filters = []
        if only_active:
            filters.append("active = TRUE")
        if require_url:
            filters.append("poster_img_url IS NOT NULL")

        where_clause = ""
        if filters:
            where_clause = " WHERE " + " AND ".join(filters)

        query = (
            f"SELECT content_id, poster_img_url "
            f"FROM {self.config.fully_qualified_table}"
            f"{where_clause} ORDER BY content_id"
        )

        logger.info(
            "poster_image_stream_start",
            batch_size=batch_size,
            only_active=only_active,
            require_url=require_url,
            max_items=max_items,
        )

        yielded = 0
        with get_cursor() as cursor:
            cursor.execute(query)
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    yield PosterImage.from_row(row)
                    yielded += 1
                    if max_items is not None and yielded >= max_items:
                        logger.info("poster_image_stream_limit_reached", yielded=yielded)
                        return

        logger.info("poster_image_stream_complete")

