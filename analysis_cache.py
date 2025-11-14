"""Cache and rate limiting for poster analysis results."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog
from cachetools import TTLCache, cached

from config import DatabricksConfig, get_config

logger = structlog.get_logger(__name__)


@dataclass
class CachedAnalysisResult:
    """Cached result with metadata."""
    content_id: int
    poster_url: str
    analysis: Dict[str, Any]
    cached_at: datetime
    
    def is_expired(self, hours: int) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() - self.cached_at > timedelta(hours=hours)


class AnalysisCache:
    """Cache for poster analysis results with rate limiting."""
    
    def __init__(self, config: Optional[DatabricksConfig] = None):
        self.config = config or get_config()
        self.enabled = self.config.enable_analysis_cache
        
        # TTL cache for results
        ttl_seconds = self.config.cache_expiry_hours * 3600
        max_size = self.config.cache_max_size
        self._cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        
        # Rate limiting
        self.requests_per_minute = self.config.vision_requests_per_minute
        self.request_delay_ms = self.config.vision_request_delay_ms
        self._last_request_time = 0.0
        self._request_times = []  # Rolling window of request times
        
        logger.info(
            "analysis_cache_initialized",
            enabled=self.enabled,
            max_size=max_size,
            ttl_hours=self.config.cache_expiry_hours,
            rate_limit_rpm=self.requests_per_minute,
        )
    
    def _make_cache_key(self, content_id: int, poster_url: str) -> str:
        """Create cache key from content ID and poster URL."""
        # Include URL in key since same content might have different posters
        data = f"{content_id}:{poster_url}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, content_id: int, poster_url: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result if available and not expired."""
        if not self.enabled:
            return None
            
        key = self._make_cache_key(content_id, poster_url)
        cached_result = self._cache.get(key)
        
        if cached_result:
            logger.info(
                "cache_hit",
                content_id=content_id,
                cache_key=key,
            )
            return cached_result['analysis']
        
        return None
    
    def put(self, content_id: int, poster_url: str, analysis: Dict[str, Any]) -> None:
        """Store analysis result in cache."""
        if not self.enabled:
            return
            
        key = self._make_cache_key(content_id, poster_url)
        self._cache[key] = {
            'content_id': content_id,
            'poster_url': poster_url,
            'analysis': analysis,
            'cached_at': datetime.now().isoformat(),
        }
        
        logger.info(
            "cache_stored",
            content_id=content_id,
            cache_key=key,
        )
    
    def should_rate_limit(self) -> bool:
        """Check if we should rate limit based on recent requests."""
        if self.requests_per_minute <= 0:
            return False  # No rate limiting
            
        current_time = time.time()
        
        # Clean up old request times (outside 1-minute window)
        cutoff_time = current_time - 60.0
        self._request_times = [t for t in self._request_times if t > cutoff_time]
        
        # Check if we've exceeded rate limit
        if len(self._request_times) >= self.requests_per_minute:
            logger.warning(
                "rate_limit_reached",
                requests_in_window=len(self._request_times),
                limit=self.requests_per_minute,
            )
            return True
        
        # Check minimum delay between requests
        if self.request_delay_ms > 0:
            time_since_last = (current_time - self._last_request_time) * 1000
            if time_since_last < self.request_delay_ms:
                return True
        
        return False
    
    def record_request(self) -> None:
        """Record that a request was made for rate limiting."""
        current_time = time.time()
        self._request_times.append(current_time)
        self._last_request_time = current_time
    
    def wait_if_needed(self) -> None:
        """Wait if rate limiting requires it."""
        if not self.should_rate_limit():
            return
            
        # Calculate how long to wait
        if self.request_delay_ms > 0:
            # Wait for minimum delay
            time_since_last = (time.time() - self._last_request_time) * 1000
            if time_since_last < self.request_delay_ms:
                wait_ms = self.request_delay_ms - time_since_last
                logger.info(
                    "rate_limit_delay",
                    wait_ms=wait_ms,
                    reason="minimum_delay",
                )
                time.sleep(wait_ms / 1000.0)
        
        # If we're at the per-minute limit, wait until the oldest request expires
        if len(self._request_times) >= self.requests_per_minute:
            oldest_request = min(self._request_times)
            wait_seconds = 60.0 - (time.time() - oldest_request) + 0.1
            if wait_seconds > 0:
                logger.info(
                    "rate_limit_delay",
                    wait_seconds=wait_seconds,
                    reason="per_minute_limit",
                )
                time.sleep(wait_seconds)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'enabled': self.enabled,
            'size': len(self._cache),
            'max_size': self._cache.maxsize,
            'ttl_hours': self.config.cache_expiry_hours,
            'requests_per_minute': self.requests_per_minute,
            'recent_requests': len(self._request_times),
        }


# Global cache instance
_cache: Optional[AnalysisCache] = None


def get_analysis_cache() -> AnalysisCache:
    """Get or create the global analysis cache."""
    global _cache
    if _cache is None:
        _cache = AnalysisCache()
    return _cache
