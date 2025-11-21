"""
Cache Manager for LLM Response Caching.

Features:
- In-memory and disk-based caching
- TTL (Time To Live) support
- LRU eviction policy
- Cache statistics tracking
- Cost savings calculation
"""
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from collections import OrderedDict

from fincli.utils.logger import get_logger
from fincli.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class CacheEntry:
    """A single cache entry."""
    key: str
    response: str
    input_tokens: int
    output_tokens: int
    created_at: str
    expires_at: Optional[str] = None
    access_count: int = 0
    last_accessed: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CacheStats:
    """Cache statistics."""
    total_hits: int = 0
    total_misses: int = 0
    total_entries: int = 0
    total_evictions: int = 0
    tokens_saved: int = 0
    cost_saved_usd: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.total_hits + self.total_misses
        return self.total_hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary including computed fields."""
        data = asdict(self)
        data['hit_rate'] = self.hit_rate
        return data


class CacheManager:
    """
    Manages LLM response caching with TTL and LRU eviction.

    Features:
    - In-memory cache with OrderedDict (LRU)
    - Optional disk persistence
    - TTL-based expiration
    - Size limits (max entries and max memory)
    - Cache statistics and cost savings tracking
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_entries: int = 1000,
        enable_disk_cache: bool = False,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize cache manager.

        Args:
            ttl_seconds: Time to live for cache entries (default 1 hour)
            max_entries: Maximum number of entries (LRU eviction)
            enable_disk_cache: Enable persistent disk cache
            cache_dir: Directory for disk cache (default: .fincli_cache)
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.enable_disk_cache = enable_disk_cache
        self.cache_dir = cache_dir or Path(".fincli_cache")

        # In-memory cache (OrderedDict for LRU)
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Statistics
        self.stats = CacheStats()

        # Initialize disk cache if enabled
        if self.enable_disk_cache:
            self.cache_dir.mkdir(exist_ok=True)
            self._load_from_disk()

        logger.info(
            "cache_manager_initialized",
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
            disk_cache=enable_disk_cache
        )

    def _generate_cache_key(
        self,
        prompt: str,
        model: str,
        provider: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Generate deterministic cache key from request parameters.

        Args:
            prompt: User prompt
            model: Model name
            provider: Provider name
            system_prompt: System prompt (optional)
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional parameters to include in key

        Returns:
            SHA256 hash as cache key
        """
        # Build key components
        key_parts = [
            f"provider:{provider}",
            f"model:{model}",
            f"temp:{temperature}",
            f"max_tokens:{max_tokens}",
            f"system:{system_prompt or ''}",
            f"prompt:{prompt}",
        ]

        # Add any additional parameters
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")

        # Create deterministic hash
        key_string = "|".join(key_parts)
        cache_key = hashlib.sha256(key_string.encode()).hexdigest()

        return cache_key

    def get(
        self,
        prompt: str,
        model: str,
        provider: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs
    ) -> Optional[str]:
        """
        Get cached response if available.

        Args:
            prompt: User prompt
            model: Model name
            provider: Provider name
            system_prompt: System prompt
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional parameters

        Returns:
            Cached response or None if not found/expired
        """
        cache_key = self._generate_cache_key(
            prompt, model, provider, system_prompt,
            temperature, max_tokens, **kwargs
        )

        # Check in-memory cache
        entry = self.cache.get(cache_key)

        if entry is None:
            # Cache miss
            self.stats.total_misses += 1
            logger.debug("cache_miss", key=cache_key[:16])
            return None

        # Check expiration
        if entry.is_expired():
            # Expired entry - remove it
            del self.cache[cache_key]
            self.stats.total_misses += 1
            self.stats.total_evictions += 1
            logger.debug("cache_expired", key=cache_key[:16])
            return None

        # Cache hit - update access stats
        entry.access_count += 1
        entry.last_accessed = datetime.now().isoformat()

        # Move to end (LRU)
        self.cache.move_to_end(cache_key)

        self.stats.total_hits += 1
        self.stats.tokens_saved += entry.input_tokens + entry.output_tokens

        logger.debug(
            "cache_hit",
            key=cache_key[:16],
            access_count=entry.access_count
        )

        return entry.response

    def set(
        self,
        prompt: str,
        response: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs
    ):
        """
        Store response in cache.

        Args:
            prompt: User prompt
            response: LLM response to cache
            model: Model name
            provider: Provider name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            system_prompt: System prompt
            temperature: Temperature parameter
            max_tokens: Max tokens parameter
            **kwargs: Additional parameters
        """
        cache_key = self._generate_cache_key(
            prompt, model, provider, system_prompt,
            temperature, max_tokens, **kwargs
        )

        # Check size limit - evict oldest if needed
        if len(self.cache) >= self.max_entries:
            # Remove oldest (first item in OrderedDict)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats.total_evictions += 1
            logger.debug("cache_eviction_lru", evicted_key=oldest_key[:16])

        # Create cache entry
        now = datetime.now()
        expires_at = now + timedelta(seconds=self.ttl_seconds)

        entry = CacheEntry(
            key=cache_key,
            response=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            access_count=0,
            last_accessed=None
        )

        # Store in cache
        self.cache[cache_key] = entry
        self.stats.total_entries = len(self.cache)

        # Persist to disk if enabled
        if self.enable_disk_cache:
            self._save_entry_to_disk(cache_key, entry)

        logger.debug(
            "cache_stored",
            key=cache_key[:16],
            tokens=input_tokens + output_tokens
        )

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.stats.total_entries = 0

        if self.enable_disk_cache and self.cache_dir.exists():
            for file in self.cache_dir.glob("*.pkl"):
                file.unlink()

        logger.info("cache_cleared")

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self.stats.total_entries = len(self.cache)
        return self.stats

    def calculate_cost_savings(
        self,
        provider: str,
        model: str,
        input_cost_per_1k: float,
        output_cost_per_1k: float
    ):
        """
        Calculate cost savings from caching.

        Args:
            provider: Provider name
            model: Model name
            input_cost_per_1k: Cost per 1K input tokens
            output_cost_per_1k: Cost per 1K output tokens
        """
        total_input_tokens = 0
        total_output_tokens = 0

        for entry in self.cache.values():
            total_input_tokens += entry.input_tokens * entry.access_count
            total_output_tokens += entry.output_tokens * entry.access_count

        input_cost = (total_input_tokens / 1000.0) * input_cost_per_1k
        output_cost = (total_output_tokens / 1000.0) * output_cost_per_1k

        self.stats.cost_saved_usd = input_cost + output_cost

        logger.info(
            "cost_savings_calculated",
            provider=provider,
            model=model,
            saved_usd=self.stats.cost_saved_usd
        )

    def _save_entry_to_disk(self, key: str, entry: CacheEntry):
        """Save cache entry to disk."""
        try:
            file_path = self.cache_dir / f"{key}.pkl"
            with open(file_path, 'wb') as f:
                pickle.dump(entry, f)
        except Exception as e:
            logger.error("disk_cache_save_failed", key=key[:16], error=str(e))

    def _load_from_disk(self):
        """Load cache entries from disk."""
        if not self.cache_dir.exists():
            return

        loaded = 0
        expired = 0

        for file_path in self.cache_dir.glob("*.pkl"):
            try:
                with open(file_path, 'rb') as f:
                    entry = pickle.load(f)

                # Check expiration
                if entry.is_expired():
                    file_path.unlink()
                    expired += 1
                else:
                    self.cache[entry.key] = entry
                    loaded += 1
            except Exception as e:
                logger.error(
                    "disk_cache_load_failed",
                    file=file_path.name,
                    error=str(e)
                )

        self.stats.total_entries = len(self.cache)

        logger.info(
            "disk_cache_loaded",
            loaded=loaded,
            expired=expired,
            total=len(self.cache)
        )

    def export_stats(self, output_file: Path):
        """Export cache statistics to JSON."""
        stats_data = self.get_stats().to_dict()

        with open(output_file, 'w') as f:
            json.dump(stats_data, f, indent=2)

        logger.info("cache_stats_exported", file=str(output_file))


# Global singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(
    ttl_seconds: Optional[int] = None,
    max_entries: Optional[int] = None,
    enable_disk_cache: Optional[bool] = None
) -> CacheManager:
    """
    Get cache manager (singleton pattern).

    Args:
        ttl_seconds: Override default TTL
        max_entries: Override default max entries
        enable_disk_cache: Override disk cache setting

    Returns:
        Configured CacheManager instance
    """
    global _cache_manager

    if _cache_manager is None:
        # Get config from settings
        ttl = ttl_seconds or getattr(settings, 'cache_ttl_seconds', 3600)
        max_size = max_entries or getattr(settings, 'cache_max_entries', 1000)
        disk = enable_disk_cache if enable_disk_cache is not None else getattr(
            settings, 'cache_enable_disk', False
        )

        _cache_manager = CacheManager(
            ttl_seconds=ttl,
            max_entries=max_size,
            enable_disk_cache=disk
        )
        logger.info("cache_manager_singleton_created")

    return _cache_manager


def reset_cache_manager():
    """Reset the global cache manager instance (for testing)."""
    global _cache_manager
    _cache_manager = None
    logger.info("cache_manager_reset")
