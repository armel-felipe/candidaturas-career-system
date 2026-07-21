from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
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

    def assert_directory_creatable(self, path: Path) -> Path:
        target = Path(path).resolve()
        if not _is_within(target, self.application_root):
            raise CapabilityViolation(
                f"cell capability does not allow mkdir outside application root: {target}"
            )
        if any(
            _is_within(target, allowed) or _is_within(allowed, target)
            for allowed in self.write_paths
        ):
            return target
        raise CapabilityViolation(f"cell capability does not allow mkdir: {target}")

    @contextmanager
    def enforce_writes(self):
        """Enforce this write allowlist for Python file operations in this thread.

        Handlers are third-party callables from the executor's perspective.  A
        voluntary ``assert_writable`` call is therefore insufficient.  The
        process-wide audit hook below is inert unless this thread-local guard
        is active and rejects an unauthorized mutation before the OS call.
        """
        previous = getattr(_ACTIVE_CAPABILITY, "value", None)
        if previous is not None:
            raise RuntimeError("cell capability guards cannot be nested")
        _ACTIVE_CAPABILITY.value = self
        try:
            yield self
        finally:
            _ACTIVE_CAPABILITY.value = previous

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


_ACTIVE_CAPABILITY = threading.local()
_VIOLATION_LOCK = threading.Lock()
_VIOLATIONS: list[dict[str, str]] = []


def recorded_capability_violations() -> tuple[dict[str, str], ...]:
    with _VIOLATION_LOCK:
        return tuple(dict(item) for item in _VIOLATIONS)


def _write_open(mode, flags) -> bool:
    if isinstance(mode, str) and any(marker in mode for marker in ("w", "a", "x", "+")):
        return True
    if isinstance(flags, int):
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_APPEND
        )
        return bool(flags & write_flags)
    return False


def _audit_cell_writes(event: str, args: tuple[object, ...]) -> None:
    capability = getattr(_ACTIVE_CAPABILITY, "value", None)
    if capability is None:
        return
    targets: tuple[object, ...] = ()
    if event == "open" and args:
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        if _write_open(mode, flags):
            targets = (args[0],)
    elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.truncate"}:
        targets = args[:1]
    elif event in {"os.rename", "os.replace"}:
        targets = args[:2]
    if not targets:
        return
    for target in targets:
        if isinstance(target, int):
            raise CapabilityViolation(
                "cell capability cannot authorize descriptor-based file mutation"
            )
        if isinstance(target, (str, bytes, os.PathLike)):
            try:
                if event == "os.mkdir":
                    capability.assert_directory_creatable(Path(target))
                else:
                    capability.assert_writable(Path(target))
            except CapabilityViolation:
                with _VIOLATION_LOCK:
                    _VIOLATIONS.append(
                        {
                            "application_root": str(capability.application_root),
                            "target": str(Path(target).resolve()),
                            "event": event,
                        }
                    )
                raise


sys.addaudithook(_audit_cell_writes)
