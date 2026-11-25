"""Probe Responses JSON Schema output support using the OpenAI-compatible shape."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


SCHEMA = {
    "type": "object", "properties": {
        "status": {"type": "string", "enum": ["ready"]},
        "count": {"type": "integer"},
    },
    "required": ["status", "count"], "additionalProperties": False,
}


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0, timeout=30)
    report = {"model": config.moss_model, "schema": SCHEMA, "status": "error"}
    try:
        response = await client.responses.create(
            model=config.moss_model,
            input="Return status ready and count 3.",
            instructions="Return the requested fields.",
            text={"format": {"type": "json_schema", "name": "probe_result", "schema": SCHEMA, "strict": True}},
            retrieve=False, cache=False, max_output_tokens=48, max_retries=0, timeout=30,
        )
        report.update({
            "status": "success", "response_status": response.status,
            "output_text": response.output_text,
            "input_tokens": response.usage.input_tokens if response.usage else None,
            "output_tokens": response.usage.output_tokens if response.usage else None,
        })
        try:
            parsed = json.loads(response.output_text)
            report["valid_json"] = isinstance(parsed, dict)
            report["schema_fields_valid"] = (
                set(parsed) == {"status", "count"}
                and parsed.get("status") == "ready"
                and isinstance(parsed.get("count"), int)
                and not isinstance(parsed.get("count"), bool)
            )
        except (json.JSONDecodeError, TypeError):
            report["valid_json"] = False
            report["schema_fields_valid"] = False
    except Exception as exc:
        report.update({
            "error_type": type(exc).__name__, "error_code": getattr(exc, "code", None),
            "http_status": getattr(exc, "status", None),
        })
    finally:
        await client.close()
        report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
        out = Path("results/phase2-structured-output")
        out.mkdir(parents=True, exist_ok=True)
        (out / "structured-output.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in {"schema", "output_text"}}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
