"""In-memory caching utilities."""
from typing import Callable, Dict, Hashable, Tuple

from cachetools import TTLCache

from config import get_config


def _build_cache() -> TTLCache:
    try:
        config = get_config()
        maxsize = config.cache_max_size
        ttl = config.cache_ttl_seconds
    except Exception:
        maxsize = 1000
        ttl = 300
    return TTLCache(maxsize=maxsize, ttl=ttl)


_cache = _build_cache()


def cache_key(func: Callable, args: Tuple, kwargs: Dict) -> Hashable:
    """Default cache key builder."""
    return (func.__name__, args, tuple(sorted(kwargs.items())))


def memoize(func: Callable):
    """Simple decorator to memoize function results in TTL cache."""

    def wrapper(*args, **kwargs):
        key = cache_key(func, args, kwargs)
        if key in _cache:
            return _cache[key]
        result = func(*args, **kwargs)
        _cache[key] = result
        return result

    return wrapper

