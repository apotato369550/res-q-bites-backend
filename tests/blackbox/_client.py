"""
tests/blackbox/_client.py
Shared foundation for black-box (live-server) test scripts.

Usage from a script in the same directory:
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from _client import Run, BASE_URL, SEEDED_LGU, SEEDED_ADMIN, new_run_id, unique_email, auth_header
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"

SEEDED_LGU = ("lgu.lahug@resqbites.org", "lgu12345")
SEEDED_ADMIN = ("admin@resqbites.org", "admin12345")

# Project root is two parents up from this file (tests/blackbox/_client.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Free functions
# ---------------------------------------------------------------------------

def new_run_id() -> str:
    """Return an 8-hex-char random run identifier."""
    return uuid4().hex[:8]


def unique_email(prefix: str, run_id: str) -> str:
    """Return a unique per-run test email address.

    Uses the reserved-for-examples ``example.com`` domain; ``.local`` and other
    special-use TLDs are rejected by Pydantic's email validator.
    """
    return f"{prefix}+{run_id}@example.com"


def auth_header(token: str) -> dict:
    """Return the Authorization header dict for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _redact_token(value):
    """Redact token values in dicts; leave everything else as-is."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "token" and isinstance(v, str):
                out[k] = "<redacted>"
            elif isinstance(v, str) and len(v) > 200:
                out[k] = v[:200] + "...<truncated>"
            else:
                out[k] = v
        return out
    return value


def _safe_response_excerpt(response: httpx.Response):
    """Extract a safe, trimmed excerpt from the response body."""
    try:
        body = response.json()
        if isinstance(body, dict):
            return _redact_token(body)
        elif isinstance(body, list):
            return body[:3]
        else:
            return body
    except Exception:
        return response.text[:200]


def _safe_request_body(json_body):
    """Return the request body dict with 'token' values redacted."""
    if json_body is None:
        return None
    if isinstance(json_body, dict):
        out = {}
        for k, v in json_body.items():
            if k == "token" and isinstance(v, str):
                out[k] = "<redacted>"
            else:
                out[k] = v
        return out
    return json_body


# ---------------------------------------------------------------------------
# Run recorder
# ---------------------------------------------------------------------------

class Run:
    """
    Recorder for a single black-box test run.

    Parameters
    ----------
    test_name : str
        Short identifier for the test (used in logs and filenames).
    results_subfolder : str
        Subfolder under results/ where the JSON log is written, e.g. "auth_results".

    Workflow
    --------
        run = Run("auth", "auth_results")
        r = run.call("POST", "/auth/signup", expect=200, json={...})
        token = r.json()["token"]
        run.check("token present", bool(token))
        sys.exit(run.finish())
    """

    def __init__(self, test_name: str, results_subfolder: str) -> None:
        self.run_id: str = new_run_id()
        self.test_name: str = test_name
        self.results_subfolder: str = results_subfolder
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.steps: list = []
        self.failure: dict | None = None

        self._client = httpx.Client(base_url=BASE_URL, timeout=10.0)

        # Reachability check — if /health is unreachable or non-200, bail immediately.
        try:
            health = self._client.get("/health")
            reachable = health.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            reachable = False

        if not reachable:
            self._write_log(result="UNREACHABLE")
            self._client.close()
            print(f"Server unreachable at {BASE_URL} — is uvicorn running?")
            sys.exit(2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(
        self,
        method: str,
        path: str,
        *,
        expect: int,
        token: str | None = None,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """
        Perform an HTTP request, record the step, and return the response.

        The response is always returned even when the status does not match
        `expect`, so callers can inspect bodies mid-flow.
        """
        headers = auth_header(token) if token is not None else {}

        response = self._client.request(
            method,
            path,
            headers=headers,
            json=json,
            params=params,
        )

        status_code = response.status_code
        ok = status_code == expect

        step = {
            "name": f"{method} {path}",
            "method": method,
            "path": path,
            "expected": expect,
            "status_code": status_code,
            "ok": ok,
            "request": _safe_request_body(json),
            "response_excerpt": _safe_response_excerpt(response),
        }
        self.steps.append(step)

        if not ok and self.failure is None:
            self.failure = {
                "step": step["name"],
                "reason": f"expected {expect}, got {status_code}",
            }

        return response

    def check(self, name: str, condition: bool, detail: str | None = None) -> None:
        """Record a non-HTTP assertion step."""
        ok = bool(condition)
        step = {
            "name": name,
            "type": "check",
            "ok": ok,
            "detail": detail,
        }
        self.steps.append(step)

        if not ok and self.failure is None:
            self.failure = {
                "step": name,
                "reason": detail or "check failed",
            }

    def finish(self) -> int:
        """
        Write the JSON log, close the HTTP client, print a summary, and
        return an exit code: 0 for PASS, 1 for FAIL.
        """
        finished_at = datetime.now(timezone.utc).isoformat()
        result = "PASS" if self.failure is None else "FAIL"

        logpath = self._write_log(result=result, finished_at=finished_at)
        self._client.close()

        print(f"[{result}] {self.test_name} run={self.run_id} -> {logpath}")
        return 0 if result == "PASS" else 1

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_log(
        self,
        result: str,
        finished_at: str | None = None,
    ) -> Path:
        """Serialize and write the run log; return the file path."""
        if finished_at is None:
            finished_at = datetime.now(timezone.utc).isoformat()

        # Build a filesystem-safe timestamp from started_at
        ts_safe = self.started_at.replace(":", "-").replace("+", "+")
        # Strip microseconds and timezone offset for brevity: 2026-06-24T13-22-05
        ts_prefix = ts_safe[:19]

        results_dir = _PROJECT_ROOT / "results" / self.results_subfolder
        results_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{ts_prefix}_{self.run_id}.json"
        logpath = results_dir / filename

        payload = {
            "run_id": self.run_id,
            "test": self.test_name,
            "base_url": BASE_URL,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "result": result,
            "steps": self.steps,
            "failure": self.failure,
        }

        with open(logpath, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        return logpath
