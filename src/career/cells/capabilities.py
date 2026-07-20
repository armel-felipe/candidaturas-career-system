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
        application_root: Path,
        read_paths: Iterable[Path],
        write_paths: Iterable[Path],
    ) -> None:
        self.application_root = Path(application_root).resolve()
        self.read_paths = self._validated_roots(read_paths, "read")
        self.write_paths = self._validated_roots(write_paths, "write")

    def assert_readable(self, path: Path) -> Path:
        return self._assert_allowed(path, self.read_paths, "read")

    def assert_writable(self, path: Path) -> Path:
        return self._assert_allowed(path, self.write_paths, "write")

    def _validated_roots(
        self, paths: Iterable[Path], operation: str
    ) -> tuple[Path, ...]:
        roots = tuple(Path(path).resolve() for path in paths)
        for root in roots:
            if not _is_within(root, self.application_root):
                raise CapabilityViolation(
                    f"cell {operation} capability root must be within application root: {root}"
                )
        return roots

    def _assert_allowed(
        self, path: Path, allowed_paths: tuple[Path, ...], operation: str
    ) -> Path:
        target = Path(path).resolve()
        if not _is_within(target, self.application_root):
            raise CapabilityViolation(
                f"cell capability does not allow {operation} outside application root: {target}"
            )
        if any(_is_within(target, allowed) for allowed in allowed_paths):
            return target
        raise CapabilityViolation(f"cell capability does not allow {operation}: {target}")


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True
