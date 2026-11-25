"""Exercise ordinary Responses API validation and a client-initiated stream close."""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from mossbench.config import load_config


URL = "https://inference.moss.dev/v1/responses"
OUTPUT = Path("reports/evidence/inference-contracts.json")


def observe(client, headers, content, close_early):
    result = {}
    with client.stream("POST", URL, headers=headers, content=content) as response:
        result["http_status"] = response.status_code
        if response.is_error:
            raw = response.read()
            try:
                error = json.loads(raw).get("error", {})
            except (ValueError, AttributeError):
                error = {}
            if isinstance(error, dict):
                for key in ("type", "code"):
                    value = error.get(key)
                    if isinstance(value, str) and re.fullmatch(r"[a-z_]{1,64}", value):
                        result["error_" + key] = value
            return result

        result.update(received_delta=False, completed=False, closed_after_delta=False)
        text = []
        for line in response.iter_lines():
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            event = json.loads(line[5:])
            if event.get("type") == "response.output_text.delta" and event.get("delta"):
                result["received_delta"] = True
                if close_early:
                    result["closed_after_delta"] = True
                    break
                text.append(event["delta"])
            if event.get("type") == "response.completed":
                result["completed"] = True
        if result["completed"]:
            result["exact_answer"] = "".join(text).strip() == "OK"
    return result


def main():
    cfg = load_config()
    if not cfg.moss_project_id or not cfg.moss_project_key:
        raise SystemExit("Configure project credentials first.")
    auth = f"Bearer {cfg.moss_project_id}:{cfg.moss_project_key}"
    body = {"model": cfg.moss_model, "input": "Return exactly OK.", "stream": True,
            "max_output_tokens": 16}
    cases = [
        ("missing_auth", None, body, "Reject without credentials"),
        ("invalid_auth", "Bearer mossbench-invalid:mossbench-invalid", body, "Reject dummy credentials"),
        ("malformed_json", auth, b"{", "Reject syntactically invalid JSON"),
        ("unknown_model", auth, {**body, "model": "mossbench/unknown-model"}, "Reject unknown model"),
        ("unknown_option", auth, {**body, "mossbench_unknown_option": True}, "Reject or explicitly flag unknown option"),
        ("client_disconnect", auth, {**body, "input": "List the numbers from 1 to 30.", "max_output_tokens": 64},
         "Client receives text then closes stream before completion"),
        ("fresh_request", auth, body, "Complete a separate request and return OK"),
    ]
    report = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(), "model": cfg.moss_model,
              "endpoint": URL, "retrieve": False, "cache": False, "automatic_retries": 0, "checks": []}
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        for name, credential, payload, expected in cases:
            headers = {"Content-Type": "application/json", "Accept": "text/event-stream",
                       "X-Moss-Retrieve": "off", "X-Moss-Cache": "off"}
            if credential:
                headers["Authorization"] = credential
            content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            start = time.monotonic()
            try:
                observed = observe(client, headers, content, name == "client_disconnect")
            except (httpx.RequestError, ValueError) as exc:
                observed = {"client_error": type(exc).__name__}
            observed["elapsed_ms"] = round((time.monotonic() - start) * 1000, 2)
            report["checks"].append({"case": name, "expected": expected, "observed": observed})
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["checks"], indent=2))


if __name__ == "__main__":
    main()
