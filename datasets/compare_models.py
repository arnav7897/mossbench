"""Paired, retrieval-free answer selection on the checked-in official-doc questions."""

import asyncio
import hashlib
import json
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference
from mossbench.config import load_config


MODELS = ("moss/fastlane-1", "deepseek/deepseek-v4.1-flash")
QUESTIONS = Path("datasets/real_docs/queries.jsonl")
OUTPUT = Path("reports/evidence/model-comparison.json")


def items():
    rows = [json.loads(line) for line in QUESTIONS.read_text().splitlines()]
    rng = random.Random(42)
    for question in rng.sample(rows, 25):
        topic = question["relevant_ids"][0].split("-")[0]
        others = [row for row in rows if row != question and row["relevant_ids"][0].split("-")[0] == topic]
        alternatives = [question] + rng.sample(others, 3)
        rng.shuffle(alternatives)
        choices = "\n".join(f"{letter}. {row['gold_answer']}" for letter, row in zip("ABCD", alternatives))
        yield question["id"], question["query"] + "\n" + choices, "ABCD"[alternatives.index(question)]


async def main():
    cfg = load_config()
    if not (cfg.moss_project_id and cfg.moss_project_key):
        raise SystemExit("Project credentials required")
    client = MossInference(cfg.moss_project_id, cfg.moss_project_key, max_retries=0)
    rows = []
    report = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "query_sha256": hashlib.sha256(QUESTIONS.read_bytes()).hexdigest(),
              "seed": 42, "planned_per_model": 75, "rows": rows}
    errors = dict.fromkeys(MODELS, 0)
    try:
        for repeat in range(3):
            for pos, (qid, prompt, answer) in enumerate(items()):
                for model in MODELS[::1 if (pos + repeat) % 2 == 0 else -1]:
                    if errors[model] >= 3:
                        continue
                    start = time.monotonic()
                    row = {"model": model, "question": qid, "repeat": repeat + 1, "expected": answer}
                    try:
                        response = await client.responses.create(model=model, input=prompt,
                            instructions="Choose the best answer. Reply with only A, B, C or D.",
                            retrieve=False, cache=False, max_output_tokens=64, timeout=30, max_retries=0)
                        letter = (response.output_text or "").strip().upper()
                        row.update(status=response.status, selected=letter if letter in tuple("ABCD") else None,
                                   correct=letter == answer)
                        errors[model] = 0
                    except Exception as exc:
                        row.update(status="error", error=type(exc).__name__, http=getattr(exc, "status", None))
                        errors[model] += 1
                    row["ms"] = round(1000 * (time.monotonic() - start), 1)
                    rows.append(row)
                    await asyncio.sleep(0.5)
    finally:
        await client.close()
        report["summary"] = {}
        for model in MODELS:
            attempted = [row for row in rows if row["model"] == model]
            completed = [row for row in attempted if row["status"] == "completed"]
            times = sorted(row["ms"] for row in completed)
            report["summary"][model] = {"attempted": len(attempted), "completed": len(completed),
                "correct": sum(row["correct"] for row in completed),
                "p50_ms": statistics.median(times) if times else None,
                "p95_ms": times[(95 * len(times) - 1) // 100] if times else None}
        OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["summary"]))


if __name__ == "__main__":
    asyncio.run(main())
