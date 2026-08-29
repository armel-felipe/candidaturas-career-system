from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

from career.paths import CAREER_STATE
from career.services.application_context import active_profile_application
from career.services.database import Database
from career.services.hermes_session_ledger import HermesSessionLedger


class HermesSessionBridgeError(RuntimeError):
    """Raised when the pipeline cannot safely address a Hermes profile."""


Transport = Callable[[str, str, Mapping[str, str], dict[str, Any] | None, float], Any]


class HermesSessionBridge:
    """Authenticated, allowlisted adapter between applications-v2 and Hermes.

    The bridge is deliberately synchronous because the applications heartbeat
    is synchronous. It performs a read-only CAS preflight, then sends the
    mutation with a stable idempotency key. Ambiguous mutations are persisted
    as ``pending_verification`` instead of being guessed as successful.
    """

    ALLOWED_PROFILES = frozenset({"vagas_bot_01", "vagas_bot_02"})
    DEFAULT_TIMEOUT_SECONDS = 8.0

    def __init__(
        self,
        *,
        root: Path | None = None,
        mode: str = "disabled",
        endpoints: Mapping[str, str] | None = None,
        api_keys: Mapping[str, str] | None = None,
        binding_profile_ids: Mapping[str, str] | None = None,
        transport: Transport | None = None,
        binding_loader: Callable[[str], Mapping[str, Any] | None] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        normalized_mode = str(mode or "disabled").strip().lower()
        if normalized_mode not in {"disabled", "dry_run", "live"}:
            raise HermesSessionBridgeError(
                "hermes session boundary mode must be disabled, dry_run, or live"
            )
        self.root = Path(root or CAREER_STATE)
        self.mode = normalized_mode
        self._endpoints = {str(key): str(value).strip() for key, value in (endpoints or {}).items()}
        self._api_keys = {str(key): str(value).strip() for key, value in (api_keys or {}).items()}
        self._binding_profile_ids = {
            str(key): str(value).strip()
            for key, value in (binding_profile_ids or {}).items()
        }
        self._transport = transport or self._default_transport
        self._binding_loader = binding_loader or self._load_active_binding
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise HermesSessionBridgeError("timeout_seconds must be positive")

    def _validate_profile(self, profile_id: str) -> str:
        profile_id = str(profile_id or "").strip()
        if profile_id not in self.ALLOWED_PROFILES:
            raise HermesSessionBridgeError(f"unsupported profile_id: {profile_id or '<empty>'}")
        return profile_id

    def endpoint_for_profile(self, profile_id: str) -> str:
        profile_id = self._validate_profile(profile_id)
        endpoint = self._endpoints.get(profile_id)
        if not endpoint:
            suffix = profile_id.upper()
            endpoint = str(os.environ.get(f"HERMES_GATEWAY_URL_{suffix}") or "").strip()
        if not endpoint:
            raise HermesSessionBridgeError(
                f"no Hermes gateway endpoint configured for {profile_id}"
            )
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HermesSessionBridgeError(f"invalid Hermes gateway endpoint for {profile_id}")
        if parsed.username or parsed.password:
            raise HermesSessionBridgeError("gateway endpoint must not contain credentials")
        return endpoint

    def api_key_for_profile(self, profile_id: str) -> str:
        profile_id = self._validate_profile(profile_id)
        key = self._api_keys.get(profile_id)
        if not key:
            suffix = profile_id.upper()
            key = str(os.environ.get(f"HERMES_GATEWAY_API_KEY_{suffix}") or "").strip()
        if not key:
            raise HermesSessionBridgeError(f"no Hermes gateway API key configured for {profile_id}")
        return key

    def ledger_for_application(self, application_id: str) -> HermesSessionLedger:
        application_id = str(application_id or "").strip()
        if not application_id:
            raise HermesSessionBridgeError("application_id must not be empty")
        return HermesSessionLedger(
            self.root / "applications_v2" / application_id / "hermes_session_ledger.json",
            application_id,
        )

    def observe_current_session(
        self,
        application_id: str,
        profile_id: str,
        session_key: str,
    ) -> dict[str, Any]:
        """Read the current binding without writing the ledger or mutating Hermes."""
        application_id = str(application_id or "").strip()
        session_key = str(session_key or "").strip()
        profile_id = self._validate_profile(profile_id)
        if not application_id or not session_key:
            raise HermesSessionBridgeError("application_id and session_key are required")
        if self.mode == "disabled":
            return {
                "status": "disabled",
                "application_id": application_id,
                "profile_id": profile_id,
                "session_key": session_key,
            }
        self._assert_active_binding(application_id, profile_id)
        endpoint = self.endpoint_for_profile(profile_id)
        api_key = self.api_key_for_profile(profile_id)
        current_session_id, error = self._read_current_session(
            endpoint, api_key, session_key, profile_id
        )
        if current_session_id is None:
            return {
                "status": "pending_verification",
                "application_id": application_id,
                "profile_id": profile_id,
                "session_key": session_key,
                "error": error,
            }
        return {
            "status": "ok",
            "application_id": application_id,
            "profile_id": profile_id,
            "session_key": session_key,
            "current_session_id": current_session_id,
        }

    def reset_for_application(
        self,
        application_id: str,
        profile_id: str,
        session_key: str,
        run_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self._boundary(
            operation="reset",
            application_id=application_id,
            profile_id=profile_id,
            session_key=session_key,
            run_id=run_id,
            reason=reason,
            target_session_id=None,
        )

    def resume_for_application(
        self,
        application_id: str,
        target_session_id: str,
        run_id: str,
        reason: str,
        *,
        profile_id: str | None = None,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        if not profile_id or not session_key:
            binding = self.ledger_for_application(application_id).current_binding()
            if binding is not None:
                profile_id = profile_id or binding.get("profile_id")
                session_key = session_key or binding.get("session_key")
        if not profile_id or not session_key:
            raise HermesSessionBridgeError(
                "resume requires an existing ledger binding or explicit profile/session binding"
            )
        return self._boundary(
            operation="resume",
            application_id=application_id,
            profile_id=profile_id,
            session_key=session_key,
            run_id=run_id,
            reason=reason,
            target_session_id=target_session_id,
        )

    def _boundary(
        self,
        *,
        operation: str,
        application_id: str,
        profile_id: str,
        session_key: str,
        run_id: str,
        reason: str,
        target_session_id: str | None,
    ) -> dict[str, Any]:
        if operation not in {"reset", "resume"}:
            raise HermesSessionBridgeError("unsupported boundary operation")
        application_id = str(application_id or "").strip()
        session_key = str(session_key or "").strip()
        run_id = str(run_id or "").strip()
        reason = str(reason or "pipeline").strip()
        if not application_id or not session_key or not run_id or not reason:
            raise HermesSessionBridgeError(
                "application_id, session_key, run_id, and reason are required"
            )
        profile_id = self._validate_profile(profile_id)
        if operation == "resume" and not str(target_session_id or "").strip():
            raise HermesSessionBridgeError("target_session_id is required for resume")

        if self.mode == "disabled":
            return {
                "status": "disabled",
                "operation": operation,
                "application_id": application_id,
                "profile_id": profile_id,
                "session_key": session_key,
                "run_id": run_id,
                "reason": reason,
            }

        self._assert_active_binding(application_id, profile_id)
        ledger = self.ledger_for_application(application_id)
        handoff_path = ledger.path.with_name("hermes_handoff.json")
        if not handoff_path.exists():
            return {
                "status": "handoff_required",
                "operation": operation,
                "application_id": application_id,
                "profile_id": profile_id,
                "session_key": session_key,
                "run_id": run_id,
                "reason": reason,
                "error": "validated handoff must exist before a session boundary",
            }
        binding = ledger.current_binding()
        if binding is not None and (
            binding["profile_id"] != profile_id or binding["session_key"] != session_key
        ):
            return {
                "status": "binding_conflict",
                "operation": operation,
                "application_id": application_id,
                "profile_id": profile_id,
                "session_key": session_key,
                "run_id": run_id,
                "reason": reason,
                "error": "session ledger binding does not match requested profile/chat",
            }
        if operation == "resume":
            resumability = ledger.resumability(str(target_session_id))
            if not resumability.get("allowed"):
                return {
                    "status": "not_resumable",
                    "operation": operation,
                    "application_id": application_id,
                    "profile_id": profile_id,
                    "session_key": session_key,
                    "target_session_id": str(target_session_id),
                    "reason": resumability.get("reason"),
                }
        endpoint = self.endpoint_for_profile(profile_id)
        api_key = self.api_key_for_profile(profile_id)
        idempotency_key = f"{run_id}:{operation}"
        current_session_id, status_result = self._read_current_session(
            endpoint, api_key, session_key, profile_id
        )
        if current_session_id is None:
            return {
                "status": "pending_verification",
                "operation": operation,
                "application_id": application_id,
                "profile_id": profile_id,
                "session_key": session_key,
                "run_id": run_id,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "error": status_result,
            }

        if self.mode == "dry_run":
            if operation == "reset":
                record = ledger.record_reset(
                    profile_id=profile_id,
                    session_key=session_key,
                    old_session_id=current_session_id,
                    new_session_id=current_session_id,
                    run_id=run_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    status="dry_run",
                )
            else:
                record = ledger.record_resume(
                    profile_id=profile_id,
                    session_key=session_key,
                    old_session_id=current_session_id,
                    target_session_id=str(target_session_id),
                    run_id=run_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    status="dry_run",
                )
            return {
                **record,
                "status": "dry_run",
                "gateway_status": "not_called",
            }

        payload = {
            "operation": operation,
            "session_key": session_key,
            "expected_session_id": current_session_id,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        if operation == "resume":
            payload["target_session_id"] = str(target_session_id)
        response_status, response = self._mutate_with_idempotency_retry(
            endpoint, api_key, payload, profile_id
        )
        gateway_status = str(response.get("status") or "")
        if gateway_status in {"conflict", "invalid_binding", "invalid_target"} or response_status == 409:
            return {
                **response,
                "status": "gateway_conflict",
                "application_id": application_id,
                "profile_id": profile_id,
                "idempotency_key": idempotency_key,
            }
        if gateway_status not in {"reset", "resumed", "already_applied"}:
            pending = self._record_pending(
                ledger,
                operation=operation,
                profile_id=profile_id,
                session_key=session_key,
                current_session_id=current_session_id,
                target_session_id=target_session_id,
                run_id=run_id,
                reason=reason,
                idempotency_key=idempotency_key,
            )
            return {
                **pending,
                "status": "pending_verification",
                "gateway_status": gateway_status or f"http_{response_status}",
            }

        new_session_id = str(response.get("new_session_id") or "").strip()
        if not new_session_id:
            new_session_id = str(target_session_id or current_session_id).strip()
        if operation == "reset":
            record = ledger.record_reset(
                profile_id=profile_id,
                session_key=session_key,
                old_session_id=current_session_id,
                new_session_id=new_session_id,
                run_id=run_id,
                reason=reason,
                idempotency_key=idempotency_key,
                status=gateway_status,
            )
        else:
            record = ledger.record_resume(
                profile_id=profile_id,
                session_key=session_key,
                old_session_id=current_session_id,
                target_session_id=new_session_id,
                run_id=run_id,
                reason=reason,
                idempotency_key=idempotency_key,
                status=gateway_status,
            )
        return self._attach_handoff_summary(
            application_id,
            {**response, **record, "status": gateway_status},
        )

    def _attach_handoff_summary(
        self,
        application_id: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        handoff_path = self.root / "applications_v2" / application_id / "hermes_handoff.json"
        if not handoff_path.exists():
            return response
        try:
            with handoff_path.open("r", encoding="utf-8") as handle:
                handoff = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return response
        if not isinstance(handoff, dict):
            return response
        response.update(
            {
                "application_id": application_id,
                "stage": handoff.get("stage"),
                "handoff_path": str(handoff_path),
            }
        )
        return response

    def _assert_active_binding(self, application_id: str, profile_id: str) -> None:
        binding_profile_id = self._binding_profile_id(profile_id)
        binding = self._binding_loader(binding_profile_id)
        if not binding or str(binding.get("application_id") or "") != application_id:
            raise HermesSessionBridgeError(
                f"profile {profile_id} is not actively bound to application {application_id}"
            )

    def _binding_profile_id(self, profile_id: str) -> str:
        profile_id = self._validate_profile(profile_id)
        mapped = self._binding_profile_ids.get(profile_id)
        if mapped:
            return mapped
        suffix = profile_id.upper()
        return str(
            os.environ.get(f"CAREER_HERMES_BINDING_PROFILE_ID_{suffix}")
            or profile_id
        ).strip()

    @staticmethod
    def _load_active_binding(profile_id: str) -> Mapping[str, Any] | None:
        database = Database()
        try:
            database.init_schema()
            return active_profile_application(database, profile_id)
        finally:
            database.close()

    def _read_current_session(
        self,
        endpoint: str,
        api_key: str,
        session_key: str,
        profile_id: str,
    ) -> tuple[str | None, str | None]:
        query = urllib.parse.urlencode({"session_key": session_key})
        url = f"{endpoint}?{query}"
        last_error = "session status unavailable"
        for _attempt in range(2):
            try:
                response_status, response = self._request("GET", url, api_key, profile_id, None)
            except (TimeoutError, socket.timeout, OSError) as exc:
                last_error = str(exc) or exc.__class__.__name__
                continue
            except HermesSessionBridgeError as exc:
                return None, str(exc)
            current_session_id = str(response.get("current_session_id") or "").strip()
            if response_status == 200 and response.get("status") == "ok" and current_session_id:
                return current_session_id, None
            last_error = str(response.get("error") or f"invalid session status response ({response_status})")
            if response_status < 500 and response_status != 429:
                break
        return None, last_error

    def _mutate_with_idempotency_retry(
        self,
        endpoint: str,
        api_key: str,
        payload: dict[str, Any],
        profile_id: str,
    ) -> tuple[int, dict[str, Any]]:
        last_error: str | None = None
        for _attempt in range(2):
            try:
                return self._request("POST", endpoint, api_key, profile_id, payload)
            except (TimeoutError, socket.timeout, OSError) as exc:
                last_error = str(exc) or exc.__class__.__name__
            except HermesSessionBridgeError as exc:
                last_error = str(exc)
                break
        return 599, {"status": "timeout", "error": last_error or "mutation timed out"}

    def _record_pending(
        self,
        ledger: HermesSessionLedger,
        *,
        operation: str,
        profile_id: str,
        session_key: str,
        current_session_id: str,
        target_session_id: str | None,
        run_id: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if operation == "reset":
            return ledger.record_reset(
                profile_id=profile_id,
                session_key=session_key,
                old_session_id=current_session_id,
                new_session_id=current_session_id,
                run_id=run_id,
                reason=reason,
                idempotency_key=idempotency_key,
                status="pending_verification",
            )
        return ledger.record_resume(
            profile_id=profile_id,
            session_key=session_key,
            old_session_id=current_session_id,
            target_session_id=str(target_session_id),
            run_id=run_id,
            reason=reason,
            idempotency_key=idempotency_key,
            status="pending_verification",
        )

    def _request(
        self,
        method: str,
        url: str,
        api_key: str,
        profile_id: str,
        payload: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        raw = self._transport(
            method,
            url,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Hermes-Profile": profile_id,
            },
            payload,
            self.timeout_seconds,
        )
        if isinstance(raw, tuple) and len(raw) == 2:
            response_status, response = raw
            return int(response_status), self._payload_dict(response)
        response = self._payload_dict(raw)
        response_status = int(response.pop("_http_status", 200))
        return response_status, response

    @staticmethod
    def _payload_dict(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise HermesSessionBridgeError("gateway returned a malformed JSON response")
        return dict(payload)

    @staticmethod
    def _default_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> tuple[int, dict[str, Any]]:
        encoded = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=encoded, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return int(response.status), json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"error": body or str(exc)}
            return int(exc.code), payload
