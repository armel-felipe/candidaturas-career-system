from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
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
        """Enforce cell filesystem capabilities, including spawned threads.

        Python's audit hook is process-wide, while the active capability is
        inherited explicitly by every ``threading.Thread`` started by a
        guarded handler.  Foreign-application reads and all unauthorized
        mutations are rejected before the OS operation.  Subprocesses are
        fail-closed except for the small, reviewed command set used by the
        production cell pipeline.
        """
        previous = getattr(_ACTIVE_CAPABILITY, "state", None)
        if previous is not None:
            raise RuntimeError("cell capability guards cannot be nested")
        state = _CapabilityGuardState(capability=self)
        _ACTIVE_CAPABILITY.state = state
        clean_exit = False
        try:
            yield self
            clean_exit = True
        finally:
            for child in tuple(state.child_threads):
                child.join(timeout=30)
                if child.is_alive():
                    state.failures.append(
                        CapabilityViolation(
                            "cell capability child thread did not terminate"
                        )
                    )
            _ACTIVE_CAPABILITY.state = previous
            if clean_exit and state.failures:
                raise state.failures[0]

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


@dataclass
class _CapabilityGuardState:
    capability: CapabilitySet
    child_threads: list[threading.Thread] = field(default_factory=list)
    failures: list[CapabilityViolation] = field(default_factory=list)


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
    state = getattr(_ACTIVE_CAPABILITY, "state", None)
    if state is None:
        return
    capability = state.capability
    targets: tuple[object, ...] = ()
    if event == "open" and args:
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        if _write_open(mode, flags):
            targets = (args[0],)
            operation = "write"
        else:
            targets = (args[0],)
            operation = "read"
    elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.truncate"}:
        targets = args[:1]
        operation = "write"
    elif event in {"os.rename", "os.replace"}:
        targets = args[:2]
        operation = "write"
    elif event == "subprocess.Popen":
        _audit_subprocess(capability, args)
        return
    if not targets:
        return
    for target in targets:
        if isinstance(target, int):
            if event == "open":
                # ``subprocess`` wraps its newly-created anonymous pipes with
                # ``open(fd, ...)`` after the command itself passed the strict
                # subprocess allowlist. Handlers receive no ambient file
                # descriptors, so these pipe wrappers do not expand path access.
                continue
            raise CapabilityViolation(
                "cell capability cannot authorize descriptor-based file mutation"
            )
        if isinstance(target, (str, bytes, os.PathLike)):
            try:
                if event == "os.mkdir":
                    capability.assert_directory_creatable(Path(target))
                elif operation == "read":
                    resolved = Path(target).resolve()
                    applications_root = capability.application_root.parent
                    if _is_within(resolved, applications_root):
                        try:
                            capability.assert_readable(resolved)
                        except CapabilityViolation:
                            capability.assert_writable(resolved)
                else:
                    capability.assert_writable(Path(target))
            except CapabilityViolation as exc:
                _record_violation(capability, Path(target), event)
                raise


def _audit_subprocess(capability: CapabilitySet, args: tuple[object, ...]) -> None:
    executable = str(args[0]) if args else ""
    command = args[1] if len(args) > 1 else ()
    cwd = Path(str(args[2])).resolve() if len(args) > 2 and args[2] else Path.cwd()
    parts = [str(item) for item in command] if isinstance(command, (list, tuple)) else []
    approved_scripts = {
        "scripts/docx/generate_custom_cv.js",
        "scripts/docx/validate_docx.py",
        "scripts/register_keywords.py",
        "scripts/deliver_artifact.py",
    }
    script = ""
    for part in parts[1:3]:
        candidate = Path(part)
        try:
            relative = candidate.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            try:
                relative = (cwd / candidate).resolve().relative_to(Path.cwd().resolve())
            except ValueError:
                continue
        normalized = relative.as_posix()
        if normalized in approved_scripts:
            script = normalized
            break
    if not script:
        foreign_target = next(
            (
                Path(part).resolve()
                for part in parts
                if part.startswith("/")
                and _is_within(Path(part).resolve(), capability.application_root.parent)
                and not _is_within(Path(part).resolve(), capability.application_root)
            ),
            Path(executable or "subprocess"),
        )
        _record_violation(capability, foreign_target, "subprocess.Popen")
        raise CapabilityViolation(
            f"cell capability does not authorize subprocess: {executable or command}"
        )
    for part in parts:
        if part.startswith("-") or not (part.startswith("/") or "/" in part):
            continue
        target = Path(part)
        target = target.resolve() if target.is_absolute() else (cwd / target).resolve()
        if _is_within(target, capability.application_root.parent) and not (
            any(_is_within(target, allowed) for allowed in capability.read_paths)
            or any(_is_within(target, allowed) for allowed in capability.write_paths)
        ):
            _record_violation(capability, target, "subprocess.Popen")
            raise CapabilityViolation(
                f"cell capability subprocess path is not allowed: {target}"
            )


def _record_violation(
    capability: CapabilitySet, target: Path, event: str
) -> None:
    with _VIOLATION_LOCK:
        _VIOLATIONS.append(
            {
                "application_root": str(capability.application_root),
                "target": str(Path(target).resolve()),
                "event": event,
            }
        )


_ORIGINAL_THREAD_START = threading.Thread.start


def _capability_thread_start(thread: threading.Thread, *args, **kwargs):
    parent_state = getattr(_ACTIVE_CAPABILITY, "state", None)
    if parent_state is not None:
        original_run = thread.run

        def guarded_run(*run_args, **run_kwargs):
            previous = getattr(_ACTIVE_CAPABILITY, "state", None)
            _ACTIVE_CAPABILITY.state = parent_state
            try:
                return original_run(*run_args, **run_kwargs)
            except CapabilityViolation as exc:
                parent_state.failures.append(exc)
                return None
            finally:
                _ACTIVE_CAPABILITY.state = previous

        thread.run = guarded_run
        parent_state.child_threads.append(thread)
    return _ORIGINAL_THREAD_START(thread, *args, **kwargs)


threading.Thread.start = _capability_thread_start


sys.addaudithook(_audit_cell_writes)
