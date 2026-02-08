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

    def _check_file_modified(self, file_path: Path, cached_mtime: float) -> bool:
        """Check if file has been modified since cache entry.

        Args:
            file_path: Path to file
            cached_mtime: Cached modification time

        Returns:
            True if file was modified, False otherwise
        """
        try:
            current_mtime = file_path.stat().st_mtime
            return current_mtime != cached_mtime
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
        cache_key = str(file_path.resolve())

        if cache_key not in self._cache:
            return None

        entry = self._cache[cache_key]

        # Check if stale
        if self._is_stale(entry):
            del self._cache[cache_key]
            return None

        # Check if file was modified
        if "mtime" in entry:
            if self._check_file_modified(file_path, entry["mtime"]):
                del self._cache[cache_key]
                return None

        # Move to end (LRU)
        self._cache.move_to_end(cache_key)

        # Return metadata (filter based on requested fields)
        metadata: dict[str, Any] = {
            "size": entry.get("size"),
            "mtime": entry.get("mtime"),
        }

        if include_hash and "hash" in entry:
            metadata["hash"] = entry["hash"]

        if include_lines and "lines" in entry:
            metadata["lines"] = entry["lines"]

        return metadata

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
        # Try cache first
        cached = self.get_metadata(file_path, include_hash, include_lines)
        if cached is not None:
            return cached

        # Compute metadata
        try:
            stat = file_path.stat()
            size = stat.st_size
            mtime = stat.st_mtime

            metadata: dict[str, Any] = {
                "size": size,
                "mtime": mtime,
            }

            # Compute hash if requested and file is small enough
            if include_hash and size < max_size_for_hash:
                file_hash_value = file_hash(file_path)
                metadata["hash"] = file_hash_value
            elif include_hash:
                metadata["hash"] = None

            # Compute line count if requested and file is small enough
            if include_lines and size < max_size_for_hash:
                lines = count_lines(file_path)
                metadata["lines"] = lines
            elif include_lines:
                metadata["lines"] = None

            # Cache the result
            self.set_metadata(
                file_path,
                size=size,
                file_hash=metadata.get("hash"),
                lines=metadata.get("lines"),
            )

            return metadata
        except (OSError, FileNotFoundError) as e:
            raise FileNotFoundError(f"File not found or inaccessible: {file_path}") from e

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
