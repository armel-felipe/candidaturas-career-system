from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class CapabilityViolation(PermissionError):
    """Raised when a cell attempts file access outside its allowlist."""


class CapabilitySet:
    """Resolved read and write allowlists for one cell execution."""

    def __init__(
        self,
        *,
        read_paths: Iterable[Path],
        write_paths: Iterable[Path],
    ) -> None:
        self.read_paths = tuple(Path(path).resolve() for path in read_paths)
        self.write_paths = tuple(Path(path).resolve() for path in write_paths)

    def assert_readable(self, path: Path) -> Path:
        return self._assert_allowed(path, self.read_paths, "read")

    def assert_writable(self, path: Path) -> Path:
        return self._assert_allowed(path, self.write_paths, "write")

    @staticmethod
    def _assert_allowed(path: Path, allowed_paths: tuple[Path, ...], operation: str) -> Path:
        target = Path(path).resolve()
        if any(_is_within(target, allowed) for allowed in allowed_paths):
            return target
        raise CapabilityViolation(f"cell capability does not allow {operation}: {target}")


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True
