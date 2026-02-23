import tempfile
from pathlib import Path

from rlm.mcp_gateway.validation import PathValidator


class TestPathValidator:
    def test_rejects_path_traversal(self) -> None:
        valid, error = PathValidator.validate_path("../secrets.txt", ["/tmp"])
        assert valid is False
        assert error is not None

    def test_rejects_path_outside_allowed_root(self) -> None:
        valid, error = PathValidator.validate_path("/etc/passwd", ["/tmp"])
        assert valid is False
        assert error is not None
        assert "outside allowed roots" in error

    def test_accepts_path_within_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as root_str:
            root = Path(root_str)
            file_path = root / "data.txt"
            file_path.write_text("hello")

            valid, error = PathValidator.validate_path(str(file_path), [str(root)])
            assert valid is True
            assert error is None

    def test_detects_restricted_patterns(self) -> None:
        assert PathValidator.is_restricted_path("/project/.git/config") is True
        assert PathValidator.is_restricted_path("/project/node_modules/pkg/index.js") is True

    @staticmethod
    def _restricted_path(pattern: str) -> str:
        if pattern.startswith("."):
            return f"/project/{pattern}/artifact.txt"
        return f"/project/{pattern}/artifact.txt"

    def test_detects_all_restricted_patterns(self) -> None:
        for pattern in PathValidator.RESTRICTED_PATTERNS:
            assert PathValidator.is_restricted_path(self._restricted_path(pattern)) is True

    def test_non_restricted_path_is_allowed(self) -> None:
        assert PathValidator.is_restricted_path("/project/src/main.py") is False

    def test_rejects_symlink_escaping_allowed_root(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root_dir,
            tempfile.TemporaryDirectory() as outside_dir,
        ):
            root = Path(root_dir)
            outside_file = Path(outside_dir) / "secret.txt"
            outside_file.write_text("secret")

            symlink_path = root / "escape_link"
            symlink_path.symlink_to(outside_file)

            valid, error = PathValidator.validate_path(str(symlink_path), [str(root)])
            assert valid is False
            assert error is not None
            assert "outside allowed roots" in error
