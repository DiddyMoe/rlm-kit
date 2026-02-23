from __future__ import annotations

from pathlib import Path

import pytest

from rlm.mcp_gateway.tools.file_cache import FileMetadataCache, get_file_cache


class TestFileMetadataCache:
    def test_get_metadata_cache_miss_returns_none(self, tmp_path: Path) -> None:
        cache = FileMetadataCache()
        unknown_file = tmp_path / "missing.txt"

        assert cache.get_metadata(unknown_file) is None

    def test_set_metadata_then_get_metadata_round_trip(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a.txt"
        file_path.write_text("hello\nworld\n", encoding="utf-8")

        cache = FileMetadataCache()
        cache.set_metadata(file_path, size=12, file_hash="abc123", lines=2)

        result = cache.get_metadata(file_path)

        assert result is not None
        assert result["size"] == 12
        assert result["hash"] == "abc123"
        assert result["lines"] == 2

    def test_ttl_expiry_invalidates_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        file_path = tmp_path / "ttl.txt"
        file_path.write_text("x", encoding="utf-8")
        cache = FileMetadataCache(ttl_seconds=10.0)

        now = 1000.0
        monkeypatch.setattr("rlm.mcp_gateway.tools.file_cache.time.time", lambda: now)
        cache.set_metadata(file_path)

        now = 1011.0
        assert cache.get_metadata(file_path) is None

    def test_max_size_eviction_removes_oldest_entry(self, tmp_path: Path) -> None:
        first = tmp_path / "first.txt"
        second = tmp_path / "second.txt"
        first.write_text("1", encoding="utf-8")
        second.write_text("2", encoding="utf-8")

        cache = FileMetadataCache(max_size=1)
        cache.set_metadata(first)
        cache.set_metadata(second)

        assert cache.get_metadata(first) is None
        assert cache.get_metadata(second) is not None

    def test_invalidate_removes_specific_entry(self, tmp_path: Path) -> None:
        file_path = tmp_path / "invalidate.txt"
        file_path.write_text("abc", encoding="utf-8")

        cache = FileMetadataCache()
        cache.set_metadata(file_path)
        cache.invalidate(file_path)

        assert cache.get_metadata(file_path) is None

    def test_clear_resets_all_entries(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("a", encoding="utf-8")
        file_b.write_text("b", encoding="utf-8")

        cache = FileMetadataCache()
        cache.set_metadata(file_a)
        cache.set_metadata(file_b)

        cache.clear()

        assert cache.get_metadata(file_a) is None
        assert cache.get_metadata(file_b) is None

    def test_get_stats_tracks_hit_miss_and_eviction_counts(self, tmp_path: Path) -> None:
        first = tmp_path / "one.txt"
        second = tmp_path / "two.txt"
        first.write_text("1", encoding="utf-8")
        second.write_text("2", encoding="utf-8")

        cache = FileMetadataCache(max_size=1)
        assert cache.get_metadata(first) is None

        cache.set_metadata(first)
        assert cache.get_metadata(first) is not None

        cache.set_metadata(second)
        stats = cache.get_stats()

        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["evictions"] >= 1

    def test_get_or_compute_metadata_uses_cache_on_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        file_path = tmp_path / "compute.txt"
        file_path.write_text("line1\nline2\n", encoding="utf-8")

        call_count = {"hash": 0, "lines": 0}

        def fake_hash(path: Path) -> str:
            call_count["hash"] += 1
            return "h"

        def fake_lines(path: Path) -> int:
            call_count["lines"] += 1
            return 2

        monkeypatch.setattr("rlm.mcp_gateway.tools.file_cache.file_hash", fake_hash)
        monkeypatch.setattr("rlm.mcp_gateway.tools.file_cache.count_lines", fake_lines)

        cache = FileMetadataCache(ttl_seconds=60.0)
        first = cache.get_or_compute_metadata(file_path, include_hash=True, include_lines=True)
        second = cache.get_or_compute_metadata(file_path, include_hash=True, include_lines=True)

        assert first == second
        assert call_count["hash"] == 1
        assert call_count["lines"] == 1

    def test_file_modification_invalidates_cache_entry(self, tmp_path: Path) -> None:
        file_path = tmp_path / "mtime.txt"
        file_path.write_text("v1", encoding="utf-8")

        cache = FileMetadataCache(ttl_seconds=60.0)
        cache.set_metadata(file_path)

        file_path.write_text("v2-updated", encoding="utf-8")

        assert cache.get_metadata(file_path) is None


class TestFileCacheSingleton:
    def test_get_file_cache_returns_singleton_instance(self) -> None:
        first = get_file_cache()
        second = get_file_cache()

        assert first is second
