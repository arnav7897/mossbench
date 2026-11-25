"""Summarize saved MossBench JSONL request records without fabricating data."""

import json
import math
from collections import defaultdict
from pathlib import Path


def percentile(values, percentile):
    """Return the nearest-rank percentile (1-based), or None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile / 100 * len(ordered)) - 1)]


def load_records(path):
    records = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(record, dict) or not all(k in record for k in ("suite", "status")):
                raise ValueError(f"line {line_number} must be an object with suite and status")
            records.append(record)
    return records


def summarize(records):
    groups = defaultdict(list)
    for record in records:
        groups[(record["suite"], record.get("mode", "default"), record.get("source", "live"))].append(record)
    result = []
    for (suite, mode, source), rows in sorted(groups.items()):
        successful = [r for r in rows if r["status"] == "success"]
        latencies = [r["latency_ms"] for r in successful if isinstance(r.get("latency_ms"), (int, float))]
        result.append({
            "suite": suite, "mode": mode, "source": source,
            "total": len(rows), "success": len(successful), "failure": len(rows) - len(successful),
            "latency_samples": len(latencies),
            "latency_ms_p50": percentile(latencies, 50),
            "latency_ms_p95": percentile(latencies, 95),
            "latency_ms_p99": percentile(latencies, 99),
        })
    return result


def write_report(input_path, output_path):
    report = {"input": str(input_path), "groups": summarize(load_records(input_path))}
    Path(output_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
