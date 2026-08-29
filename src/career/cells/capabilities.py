from __future__ import annotations

import os
import shutil
import sys
import threading
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections.abc import Iterable, Mapping
from pathlib import Path

from career.paths import ROOT


class CapabilityViolation(PermissionError):
    """Raised when a cell attempts file access outside its allowlist."""


_TRUSTED_EXECUTABLE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
_CANONICAL_PYTHON_EXECUTABLE = Path(sys.executable).resolve()


def canonical_subprocess_environment() -> dict[str, str]:
    """Return the exact, minimal environment accepted by cellular subprocesses."""
    environment = {
        "PATH": _TRUSTED_EXECUTABLE_PATH,
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    for name in (
        "HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "RCLONE_CONFIG",
        "RCLONE_ONEDRIVE_REMOTE",
        "RCLONE_ONEDRIVE_DELIVERY_DIR",
    ):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def canonical_node_executable() -> Path:
    executable = shutil.which("node", path=_TRUSTED_EXECUTABLE_PATH)
    if not executable:
        raise RuntimeError("canonical Node.js executable is unavailable")
    return Path(executable).resolve()


def canonical_python_executable() -> Path:
    return _CANONICAL_PYTHON_EXECUTABLE


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
    elif event in {
        "os.remove",
        "os.rmdir",
        "os.mkdir",
        "os.chmod",
        "os.chown",
        "os.truncate",
        "os.utime",
        "os.setxattr",
        "os.removexattr",
    }:
        targets = args[:1]
        operation = "write"
    elif event in {"os.rename", "os.replace"}:
        targets = args[:2]
        operation = "write"
    elif event == "os.link":
        _audit_link(capability, args, symbolic=False)
        return
    elif event == "os.symlink":
        _audit_link(capability, args, symbolic=True)
        return
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


def _absolute_executable(executable: str) -> Path | None:
    if not executable or not Path(executable).is_absolute():
        return None
    return Path(executable).resolve()


def _subprocess_path(
    capability: CapabilitySet, raw: str, cwd: Path, *, writable: bool
) -> Path:
    target = Path(raw)
    target = target.resolve() if target.is_absolute() else (cwd / target).resolve()
    if writable:
        capability.assert_writable(target)
    else:
        try:
            capability.assert_readable(target)
        except CapabilityViolation:
            capability.assert_writable(target)
    return target


def _reject_subprocess(
    capability: CapabilitySet, target: Path, message: str
) -> None:
    _record_violation(capability, target, "subprocess.Popen")
    raise CapabilityViolation(message)


def _require_canonical_environment(
    capability: CapabilitySet, executable: Path, environment: object
) -> None:
    if not isinstance(environment, Mapping) or {
        str(key): str(value) for key, value in environment.items()
    } != canonical_subprocess_environment():
        _reject_subprocess(
            capability,
            executable,
            "cell capability rejected a custom subprocess environment",
        )


def _require_option_pairs(
    capability: CapabilitySet,
    parts: list[str],
    *,
    cwd: Path,
    allowed: dict[str, str],
) -> dict[str, str]:
    tail = parts[2:]
    if len(tail) % 2:
        _reject_subprocess(
            capability,
            Path(parts[-1] or "subprocess"),
            "cell capability subprocess has an incomplete option",
        )
    parsed: dict[str, str] = {}
    for index in range(0, len(tail), 2):
        option, value = tail[index], tail[index + 1]
        if option not in allowed or option in parsed or not value:
            suspicious = value if option in allowed else option
            if "=" in suspicious:
                suspicious = suspicious.split("=", 1)[1]
            _reject_subprocess(
                capability,
                (cwd / suspicious).resolve(),
                f"cell capability subprocess option is not allowed: {option}",
            )
        kind = allowed[option]
        if kind == "read_path":
            _subprocess_path(capability, value, cwd, writable=False)
        elif kind == "write_path":
            _subprocess_path(capability, value, cwd, writable=True)
        parsed[option] = value
    return parsed


def _audit_subprocess(capability: CapabilitySet, args: tuple[object, ...]) -> None:
    executable = str(args[0]) if args else ""
    command = args[1] if len(args) > 1 else ()
    cwd = Path(str(args[2])).resolve() if len(args) > 2 and args[2] else Path.cwd()
    environment = args[3] if len(args) > 3 else None
    parts = [str(item) for item in command] if isinstance(command, (list, tuple)) else []
    resolved_executable = _absolute_executable(executable)
    if (
        len(parts) < 2
        or resolved_executable is None
    ):
        suspicious = Path(executable or "subprocess")
        for raw in reversed(parts[1:]):
            candidate = Path(raw)
            candidate = (
                candidate.resolve()
                if candidate.is_absolute()
                else (cwd / candidate).resolve()
            )
            if _is_within(candidate, capability.application_root.parent):
                suspicious = candidate
                break
        _reject_subprocess(
            capability,
            suspicious,
            f"cell capability does not authorize subprocess: {executable or command}",
        )

    script = Path(parts[1])
    script = script.resolve() if script.is_absolute() else (cwd / script).resolve()
    python_executable = canonical_python_executable()
    try:
        node_executable = canonical_node_executable()
    except RuntimeError:
        node_executable = None
    canonical_scripts = {
        "generate": (ROOT / "scripts/docx/generate_custom_cv.js").resolve(),
        "validate": (ROOT / "scripts/docx/validate_docx.py").resolve(),
        "register": (ROOT / "scripts/register_keywords.py").resolve(),
        "deliver": (ROOT / "scripts/deliver_artifact.py").resolve(),
    }

    if script == canonical_scripts["generate"] and resolved_executable == node_executable:
        parsed = _require_option_pairs(
            capability,
            parts,
            cwd=cwd,
            allowed={
                "--content": "read_path",
                "--output-dir": "write_path",
                "--application-id": "literal",
            },
        )
        if set(parsed) != {"--content", "--output-dir", "--application-id"} or parsed[
            "--application-id"
        ] != capability.application_root.name:
            _reject_subprocess(
                capability,
                script,
                "cell capability rejected the canonical CV renderer arguments",
            )
        _require_canonical_environment(capability, resolved_executable, environment)
        return

    if script == canonical_scripts["validate"] and resolved_executable == python_executable:
        if len(parts) != 3:
            _reject_subprocess(
                capability, script, "cell capability rejected DOCX validator arguments"
            )
        _subprocess_path(capability, parts[2], cwd, writable=False)
        _require_canonical_environment(capability, resolved_executable, environment)
        return

    if script == canonical_scripts["register"] and resolved_executable == python_executable:
        parsed = _require_option_pairs(
            capability,
            parts,
            cwd=cwd,
            allowed={
                "--fit-map": "read_path",
                "--cv": "read_path",
                "--registry": "write_path",
                "--translation-registry": "read_path",
                "--translation-candidates": "write_path",
            },
        )
        required = {
            "--fit-map",
            "--cv",
            "--registry",
            "--translation-registry",
            "--translation-candidates",
        }
        if set(parsed) != required:
            _reject_subprocess(
                capability,
                script,
                "cell capability requires the complete canonical keyword registration schema",
            )
        _require_canonical_environment(capability, resolved_executable, environment)
        return

    if script == canonical_scripts["deliver"] and resolved_executable == python_executable:
        parsed = _require_option_pairs(
            capability,
            parts,
            cwd=cwd,
            allowed={
                "--file": "read_path",
                "--remote": "literal",
                "--folder": "literal",
                "--report": "write_path",
                "--filename": "literal",
            },
        )
        required = {"--file", "--remote", "--folder", "--report"}
        folder = parsed.get("--folder", "")
        filename = parsed.get("--filename", "")
        if (
            not required.issubset(set(parsed))
            or not parsed.get("--remote")
            or (filename and Path(filename).name != filename)
            or (
                folder != "01_armel/Curriculos/personalizados"
                and not folder.startswith("01_armel/Curriculos/personalizados/")
            )
        ):
            _reject_subprocess(
                capability, script, "cell capability rejected delivery arguments"
            )
        _require_canonical_environment(capability, resolved_executable, environment)
        return

    _reject_subprocess(
        capability,
        script if len(parts) > 1 else Path(executable or "subprocess"),
        f"cell capability does not authorize subprocess: {executable or command}",
    )


def _audit_link(
    capability: CapabilitySet, args: tuple[object, ...], *, symbolic: bool
) -> None:
    if len(args) < 2:
        raise CapabilityViolation("cell capability cannot authorize incomplete link mutation")
    source, destination = Path(args[0]), Path(args[1])
    try:
        capability.assert_writable(destination)
        if symbolic and not source.is_absolute():
            source = destination.parent / source
        try:
            capability.assert_readable(source)
        except CapabilityViolation:
            capability.assert_writable(source)
    except CapabilityViolation:
        target = destination
        try:
            capability.assert_writable(destination)
        except CapabilityViolation:
            pass
        else:
            target = source
        _record_violation(
            capability, target, "os.symlink" if symbolic else "os.link"
        )
        raise


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
