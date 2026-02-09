"""
Cache module for WordAI
Handles Redis caching for community books, categories, and trending data
"""

from src.cache.redis_client import RedisCacheClient, get_cache_client
from src.cache.cache_warmup import run_cache_warmup

__all__ = ["RedisCacheClient", "get_cache_client", "run_cache_warmup"]
