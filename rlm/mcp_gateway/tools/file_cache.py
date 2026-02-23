"""LRU cache for file metadata to optimize filesystem operations.

Caches file size, hash, line count, and modification time to avoid
repeated stat() calls in local IDE mode.
"""

import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from rlm.mcp_gateway.tools.helpers import count_lines, file_hash


class FileMetadataCache:
    """LRU cache for file metadata."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 60.0) -> None:
        """Initialize file metadata cache.

        Args:
            max_size: Maximum number of files to cache
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _is_stale(self, entry: dict[str, Any]) -> bool:
        """Check if cache entry is stale.

        Args:
            entry: Cache entry dictionary

        Returns:
            True if entry is stale, False otherwise
        """
        if "cached_at" not in entry:
            return True
        age = time.time() - entry["cached_at"]
        return age > self.ttl_seconds

    def _cache_key_for(self, file_path: Path) -> str:
        return str(file_path.resolve())

    def _build_metadata_from_entry(
        self,
        entry: dict[str, Any],
        include_hash: bool,
        include_lines: bool,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "size": entry.get("size"),
            "mtime": entry.get("mtime"),
        }
        if include_hash and "hash" in entry:
            metadata["hash"] = entry["hash"]
        if include_lines and "lines" in entry:
            metadata["lines"] = entry["lines"]
        return metadata

    def _compute_metadata(
        self,
        file_path: Path,
        include_hash: bool,
        include_lines: bool,
        max_size_for_hash: int,
    ) -> dict[str, Any]:
        try:
            stat = file_path.stat()
            size = stat.st_size
            metadata: dict[str, Any] = {
                "size": size,
                "mtime": stat.st_mtime,
            }

            should_compute_expensive = size < max_size_for_hash
            if include_hash:
                metadata["hash"] = file_hash(file_path) if should_compute_expensive else None
            if include_lines:
                metadata["lines"] = count_lines(file_path) if should_compute_expensive else None
            return metadata
        except (OSError, FileNotFoundError) as e:
            raise FileNotFoundError(f"File not found or inaccessible: {file_path}") from e

    def _check_file_modified(self, file_path: Path, cached_mtime: float, cached_size: int) -> bool:
        """Check if file has been modified since cache entry.

        Args:
            file_path: Path to file
            cached_mtime: Cached modification time

        Returns:
            True if file was modified, False otherwise
        """
        try:
            stat = file_path.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size
            return current_mtime != cached_mtime or current_size != cached_size
        except (OSError, FileNotFoundError):
            return True  # Treat errors as modified (invalidate cache)

    def get_metadata(
        self,
        file_path: Path,
        include_hash: bool = True,
        include_lines: bool = True,
    ) -> dict[str, Any] | None:
        """Get cached file metadata.

        Args:
            file_path: Path to file
            include_hash: Whether to include file hash
            include_lines: Whether to include line count

        Returns:
            Metadata dictionary or None if not cached or stale
        """
        cache_key = self._cache_key_for(file_path)
        entry = self._cache.get(cache_key)
        if entry is None:
            self._misses += 1
            return None
        if self._is_stale(entry):
            del self._cache[cache_key]
            self._misses += 1
            return None

        mtime = entry.get("mtime")
        size = entry.get("size")
        if isinstance(mtime, (int, float)) and isinstance(size, int):
            if self._check_file_modified(file_path, float(mtime), size):
                del self._cache[cache_key]
                self._misses += 1
                return None

        self._cache.move_to_end(cache_key)
        self._hits += 1
        return self._build_metadata_from_entry(entry, include_hash, include_lines)

    def set_metadata(
        self,
        file_path: Path,
        size: int | None = None,
        file_hash: str | None = None,
        lines: int | None = None,
    ) -> None:
        """Cache file metadata.

        Args:
            file_path: Path to file
            size: File size in bytes
            file_hash: File hash
            lines: Line count
        """
        cache_key = str(file_path.resolve())

        try:
            stat = file_path.stat()
            mtime = stat.st_mtime
            if size is None:
                size = stat.st_size
        except (OSError, FileNotFoundError):
            # Can't cache if file doesn't exist
            return

        # Remove old entry if exists
        if cache_key in self._cache:
            del self._cache[cache_key]

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Remove oldest (first item)
            self._evictions += 1

        # Create cache entry
        entry: dict[str, Any] = {
            "size": size,
            "mtime": mtime,
            "cached_at": time.time(),
        }

        if file_hash is not None:
            entry["hash"] = file_hash

        if lines is not None:
            entry["lines"] = lines

        self._cache[cache_key] = entry

    def get_or_compute_metadata(
        self,
        file_path: Path,
        include_hash: bool = True,
        include_lines: bool = True,
        max_size_for_hash: int = 1024 * 1024,  # 1MB
    ) -> dict[str, Any]:
        """Get cached metadata or compute and cache it.

        Args:
            file_path: Path to file
            include_hash: Whether to include file hash
            include_lines: Whether to include line count
            max_size_for_hash: Maximum file size to compute hash for

        Returns:
            Metadata dictionary with size, hash (optional), lines (optional), mtime
        """
        cached = self.get_metadata(file_path, include_hash, include_lines)
        if cached is not None:
            return cached

        metadata = self._compute_metadata(file_path, include_hash, include_lines, max_size_for_hash)
        self.set_metadata(
            file_path,
            size=metadata.get("size") if isinstance(metadata.get("size"), int) else None,
            file_hash=metadata.get("hash") if isinstance(metadata.get("hash"), str) else None,
            lines=metadata.get("lines") if isinstance(metadata.get("lines"), int) else None,
        )
        return metadata

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def invalidate(self, file_path: Path) -> None:
        """Invalidate cache entry for a specific file.

        Args:
            file_path: Path to file
        """
        cache_key = str(file_path.resolve())
        if cache_key in self._cache:
            del self._cache[cache_key]

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }


# Global cache instance (shared across tools)
_global_cache: FileMetadataCache | None = None


def get_file_cache() -> FileMetadataCache:
    """Get or create global file metadata cache.

    Returns:
        Global FileMetadataCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = FileMetadataCache(max_size=1000, ttl_seconds=60.0)
    return _global_cache
