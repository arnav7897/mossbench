"""Build shareable aggregate evidence from local result files; omit raw answers and IDs."""

import json
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "evidence"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values, percent):
    values = sorted(values)
    return values[max(0, (len(values) * percent + 99) // 100 - 1)] if values else None


def retrieval_metrics(rows):
    return {
        "n": len(rows),
        **{
            name: round(statistics.mean(row[key] for row in rows), 6)
            for name, key in (("recall_at_1", "recall_at_1"), ("recall_at_5", "recall_at_5"),
                              ("recall_at_10", "recall_at_10"), ("mrr", "reciprocal_rank"))
        },
    }


def export_retrieval():
    rows = read_jsonl(ROOT / "results/phase2-real-modes/retrieval.jsonl")
    bm25 = read_jsonl(ROOT / "results/phase2-real-bm25/keyword.jsonl")
    summary = json.loads((ROOT / "results/phase2-real-modes/retrieval-summary.json").read_text())
    manifest = json.loads((ROOT / "datasets/real_docs/sources.json").read_text())
    modes = defaultdict(list)
    for row in rows:
        modes[row["mode"]].append(row)
    result = {
        "index": summary["index"], "query_count": summary["query_count"],
        "query_sha256": summary["query_sha256"], "source_pages": manifest["parent_page_count"],
        "chunks": manifest["document_count"], "corpus_sha256": manifest["corpus_sha256"],
        "chunk_size_chars": manifest["chunk_size_chars"],
        "chunk_overlap_chars": manifest["chunk_overlap_chars"],
        "warmups_per_query_per_mode": summary["warmups_per_query"],
        "repeats_per_query_per_mode": summary["repeats"], "sequential": True, "modes": {},
    }
    for name, group in sorted(modes.items()):
        evaluation = [row for row in group if row["split"] == "evaluation"]
        held_out = [row for row in group if row["split"] == "held_out"]
        result["modes"][name] = {
            "alpha": group[0]["alpha"], "n": len(group),
            "latency_ms": {f"p{p}": percentile([row["latency_ms"] for row in group], p) for p in (50, 95, 99)},
            "evaluation": retrieval_metrics(evaluation),
            "evaluation_by_category": {
                category: retrieval_metrics([row for row in evaluation if row["category"] == category])
                for category in ("exact", "paraphrase")
            },
            "held_out": retrieval_metrics(held_out),
            "held_out_by_category": {
                category: retrieval_metrics([row for row in held_out if row["category"] == category])
                for category in ("exact", "paraphrase")
            },
        }
    result["overall_all_modes"] = {
        "measurements": summary["n"], "latency_ms": summary["latency_ms"],
        "successful_queries_per_second": round(summary["successful_qps"], 3),
    }
    latencies = [row["latency_ms"] for row in bm25]
    result["local_bm25"] = {
        "n": len(bm25), "latency_ms": {"p50": statistics.median(latencies), "p95": percentile(latencies, 95)},
        "evaluation": retrieval_metrics([row for row in bm25 if row["split"] == "evaluation"]),
        "evaluation_by_category": {
            category: retrieval_metrics([row for row in bm25 if row["split"] == "evaluation" and row["category"] == category])
            for category in ("exact", "paraphrase")
        },
        "held_out": retrieval_metrics([row for row in bm25 if row["split"] == "held_out"]),
    }
    (OUT / "phase2-real-retrieval.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_rag():
    rows = read_jsonl(ROOT / "results/phase2-real-rag/rag.jsonl")
    summary = json.loads((ROOT / "results/phase2-real-rag/rag-summary.json").read_text())
    misses = {
        "llm_only": ["rd-006", "rd-011", "rd-013", "rd-014", "rd-016", "rd-027", "rd-028", "rd-036", "rd-040"],
        "manual_rag": ["rd-002", "rd-004", "rd-006", "rd-013", "rd-016", "rd-017", "rd-018", "rd-019", "rd-023", "rd-030"],
        "hosted_rag": ["rd-002", "rd-004", "rd-013", "rd-017", "rd-018", "rd-019", "rd-023", "rd-030"],
    }
    result = {
        "model": summary["model"], "index": summary["index"], "query_count": summary["query_count"],
        "query_sha256": summary["dataset_sha256"],
        "all_requests_successful": all(row["status"] == "success" for row in rows),
        "nonempty_answers": all(bool((row.get("answer") or "").strip()) for row in rows),
        "output_cap_hits": sum(row.get("output_tokens") == row.get("max_output_tokens") for row in rows),
        "manual_source_grounded_review": {
            "correct": {mode: summary["query_count"] - len(ids) for mode, ids in misses.items()},
            "incorrect_question_ids": misses,
            "criteria": "Main fact accurate; material contradictions count incorrect; abstention on supported questions counts incorrect.",
            "hosted_retrieval_provenance_available": False,
        },
        "modes": {mode["mode"]: {key: mode[key] for key in ("n", "latency_ms_p50", "latency_ms_p95", "input_tokens", "output_tokens")} for mode in summary["modes"]},
        "dollar_cost_per_call": None,
        "note": "No dollar estimate inferred from token usage.",
    }
    (OUT / "phase2-real-rag.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_contracts():
    checks = json.loads((ROOT / "results/phase2-real-retrieval-contracts.json").read_text())["checks"]
    result = {
        "metadata_filter": {"passed": checks["metadata_filter"]["passed"], "result_count": checks["metadata_filter"]["result_count"], "all_results_matched_filter": all(topic == "redis" for topic in checks["metadata_filter"]["topics"])},
        "empty_query": checks["empty_query"]["outcome"],
        "empty_results": {"passed": checks["empty_results"]["passed"], "result_count": checks["empty_results"]["result_count"]},
        "fresh_client_reload": {"passed": checks["fresh_client_reload"]["passed"], "top_five_stable": checks["fresh_client_reload"]["before_ids"] == checks["fresh_client_reload"]["after_ids"]},
        "duplicate_id_upsert": {"passed": checks["duplicate_id_upsert"]["passed"], "one_document_after_upsert": checks["duplicate_id_upsert"]["matching_documents"] == 1, "revised_text_visible": checks["duplicate_id_upsert"]["updated_text_visible"]},
        "delete_visibility": {"passed": checks["delete_visibility"]["passed"], "no_document_remains": checks["delete_visibility"]["remaining_documents"] == 0, "absent_from_search": not checks["delete_visibility"]["probe_in_search"]},
        "multi_index_isolation": "not tested; no dedicated index slot",
    }
    (OUT / "phase2-retrieval-contracts.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_tasks():
    smoke = json.loads((ROOT / "results/phase3-tasks/tasks-summary.json").read_text())
    edge = read_jsonl(ROOT / "results/phase3-edgecases/edgecases.jsonl")
    result = {
        "smoke": smoke,
        "lifecycle": {
            "invalid_id": "not_found_error", "active_cancel_terminal_status": "cancelled",
            "completed_cancel_status": "completed", "fresh_client_resume_same_task": True,
            "artifact_bytes": 79, "artifact_sha256": "28847ccf09b63f34ddb4fd1d7236bc9e9d30eb48f5d5b07bcd6cd579e0f8b190",
            "premature_artifact_access": "task_not_finished",
        },
        "edge_cases": {
            "30_second_runtime": "rejected before task creation", "observed_runtime_range_seconds": "60-7200",
            "model_cost_limit_usd": 0.01, "reported_model_usage_cost_usd": 0.006023,
            "same_idempotency_key_same_task": any(row.get("test_id") == "T13" and row.get("same_task_id") for row in edge),
            "cancel_poll_race_terminal_status": next((row["terminal_status"] for row in edge if row.get("test_id") == "T10-race"), None),
        },
        "cost_note": "TaskUsage cost is model usage only; browser/total billing may differ. These are single observations, not reliability estimates.",
    }
    (OUT / "phase3-task-evidence.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_bm25_scale():
    result = {"baseline": "local standard-library BM25", "query_count": 50, "corpora": {}}
    for size in (100, 1000, 10000):
        summary = json.loads((ROOT / f"results/phase2-bm25-scale-{size}/keyword-summary.json").read_text())
        result["corpora"][str(size)] = {
            "documents": size,
            "measurements": summary["n"],
            "corpus_sha256": summary["corpus_sha256"],
            "query_sha256": summary["queries_sha256"],
            "latency_ms": {"p50": summary["latency_ms_p50"], "p95": summary["latency_ms_p95"]},
            "evaluation_exact": summary["groups"]["evaluation_exact"],
            "evaluation_paraphrase": summary["groups"]["evaluation_paraphrase"],
            "held_out_exact": summary["groups"]["held_out_exact"],
            "held_out_paraphrase": summary["groups"]["held_out_paraphrase"],
        }
    result["note"] = "Offline only; timings are local BM25 end-to-end query measurements on this machine, not comparable to Moss cloud latency. The synthetic corpora contain the same 10 fact documents plus unrelated decoys."
    (OUT / "phase2-bm25-scale.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_hard_negatives():
    raw = json.loads((ROOT / "results/phase2-hard-negatives/hard-negatives.json").read_text())
    supported = next(case for case in raw["cases"] if case["supported_parent"])
    unsupported = [case for case in raw["cases"] if not case["supported_parent"]]
    result = {
        "index": raw["index"],
        "supported_control": {
            "count": 1,
            "correct_parent_ranked_first": bool(supported["results"] and supported["results"][0]["parent_id"] == supported["supported_parent"]),
            "top_parent": supported["results"][0]["parent_id"] if supported["results"] else None,
            "top_score": supported["results"][0]["score"] if supported["results"] else None,
        },
        "unsupported_questions": [{
            "count": len(case["results"]),
            "top_parent": case["results"][0]["parent_id"] if case["results"] else None,
            "top_score": case["results"][0]["score"] if case["results"] else None,
            "top_five_parents": [row["parent_id"] for row in case["results"]],
        } for case in unsupported],
        "note": "Four retrieval-only observations (one supported control and three manually labeled unsupported questions). Returned scores are not calibrated confidence or proof that the passage answers the query; no abstention rate is inferred.",
    }
    (OUT / "phase2-hard-negatives.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_contradictions():
    raw = json.loads((ROOT / "results/phase2-contradictions/contradictions.json").read_text())
    retrieved_ids = {row["id"] for row in raw.get("retrieved", [])}
    answer = raw.get("answer", "").lower()
    result = {
        "index": raw["index"],
        "retrieved_both_conflicting_passages": {"passed": {"mossbench-contradiction-a", "mossbench-contradiction-b"} <= retrieved_ids},
        "request_succeeded": raw.get("status") == "success",
        "cleanup_verified": raw.get("cleanup_verified") is True,
        "answer_acknowledged_conflict": "conflicting" in answer and "5 attempts" in answer and "9 attempts" in answer,
        "answer_latency_ms": raw.get("latency_ms"),
        "input_tokens": raw.get("input_tokens"),
        "output_tokens": raw.get("output_tokens"),
        "note": "One controlled temporary-fixture run. The answer cited both contradictory passages; this does not establish a general contradiction-detection rate.",
    }
    (OUT / "phase2-contradictions.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_streaming():
    raw = json.loads((ROOT / "results/phase2-streaming/streaming.json").read_text())
    result = {key: raw[key] for key in (
        "model", "event_types", "first_text_delta_ms", "end_to_end_ms",
        "stream_matches_final", "completed_event_seen", "usage", "status",
    )}
    result["note"] = "One retrieval-free stream. This checks event order and text assembly only; early disconnect, stream error handling, and comparison with a non-stream response were not tested."
    (OUT / "phase2-streaming.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_concurrency():
    raw = json.loads((ROOT / "results/phase2-inference-concurrency/concurrency.json").read_text())
    rows = raw["results"]
    result = {
        "model": raw["model"], "calls_per_level": raw["calls_per_level"],
        "cache": raw["cache"], "sdk_retries": raw["sdk_retries"],
        "levels": [],
        "note": "Single back-to-back sweep. Concurrency 5 produced rate-limit responses; throughput is successful calls / level wall time. Not a stable documented quota or a saturation test.",
    }
    for summary in raw["summaries"]:
        group = [row for row in rows if row["concurrency"] == summary["concurrency"]]
        result["levels"].append({
            key: summary[key] for key in (
                "concurrency", "attempted", "successes", "failures", "wall_seconds",
                "successful_requests_per_second", "latency_ms_p50", "latency_ms_p95",
                "input_tokens", "output_tokens",
            )
        } | {"error_counts": {
            f"{row.get('http_status')}:{row.get('error_code')}": sum(
                1 for failed in group if failed.get("status") == "error"
                and failed.get("http_status") == row.get("http_status")
                and failed.get("error_code") == row.get("error_code")
            )
            for row in group if row.get("status") == "error"
        }})
    (OUT / "phase2-inference-concurrency.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_function_tool():
    raw = json.loads((ROOT / "results/phase2-function-tool/function-tool.json").read_text())
    result = {
        key: raw.get(key) for key in (
            "model", "status", "tool_name", "function_call_count", "local_tool_executed",
            "tool_returned_fixture_record", "final_mentions_shipped", "first_usage", "second_usage", "end_to_end_ms",
        )
    }
    result["note"] = "One deterministic local-fixture function call and one follow-up response. Tool argument errors, unknown IDs, and tool failure handling were not tested."
    (OUT / "phase2-function-tool.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_sdk_vs_http():
    raw = json.loads((ROOT / "results/phase2-sdk-vs-http/comparison.json").read_text())
    result = {
        "model": raw["model"], "retrieve": raw["retrieve"], "cache": raw["cache"],
        "sdk": {key: raw["sdk"].get(key) for key in ("status", "latency_ms", "input_tokens", "output_tokens")},
        "raw_http": {key: raw["raw_http"].get(key) for key in ("http_status", "response_status", "latency_ms", "input_tokens", "output_tokens")},
        "text_matches": raw["text_matches"], "usage_matches": raw["usage_matches"],
        "note": "One sequential pair of calls. The latency difference is exploratory and not a stable client-overhead estimate.",
    }
    (OUT / "phase2-sdk-vs-http.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_structured_output():
    raw = json.loads((ROOT / "results/phase2-structured-output/structured-output.json").read_text())
    result = {key: raw.get(key) for key in (
        "model", "status", "response_status", "input_tokens", "output_tokens", "valid_json", "schema_fields_valid",
    )}
    result["schema"] = "object with status enum and integer count; no additional properties"
    result["note"] = "One request and one small schema; not a broad JSON Schema conformance test."
    (OUT / "phase2-structured-output.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_cache_usage():
    raw = json.loads((ROOT / "results/phase2-cache/cache.json").read_text())
    result = {
        "model": raw["model"], "cache_enabled": raw["cache_enabled"],
        "retrieve": raw["retrieve"], "calls": raw["calls"], "note": raw["note"],
    }
    (OUT / "phase2-cache.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_retrieval_rss():
    raw = json.loads((ROOT / "results/phase2-retrieval-rss/rss.json").read_text())
    result = {key: raw[key] for key in (
        "index", "rss_before_client_kib", "rss_after_load_kib", "rss_after_query_kib",
        "rss_after_close_kib", "rss_delta_after_load_kib", "rss_delta_after_close_kib",
        "load_ms", "query_ms", "result_count",
    )}
    result["note"] = "Single Linux process observation with Moss/Python imports already resident; RSS includes SDK, loaded index, Python allocator, and other process state. Not isolated index memory or a repeated measurement."
    (OUT / "phase2-retrieval-rss.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_retrieval_selection():
    raw = json.loads((ROOT / "results/phase2-retrieval-selection/selection.json").read_text())
    result = {
        "model": raw["model"],
        "cases": [{key: case.get(key) for key in (
            "case", "status", "latency_ms", "nonempty_output", "input_tokens", "output_tokens",
            "error_type", "error_code", "http_status",
        )} for case in raw["cases"]],
        "note": "The nonexistent index selection returned 403 permission_error; this does not distinguish absence from access control. No index was created or modified.",
    }
    (OUT / "phase2-retrieval-selection.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def export_retrieval_timing_header():
    raw = json.loads((ROOT / "results/phase2-retrieval-timing-header/header.json").read_text())
    result = {key: raw.get(key) for key in (
        "model", "index", "http_status", "retrieve_ms_header_present", "retrieve_ms_header",
        "completed_event_seen", "response_status", "input_tokens", "output_tokens", "end_to_end_ms",
    )}
    result["note"] = "One request. The service returned X-Moss-Retrieve-Ms; this single response does not establish header stability or timing accuracy."
    (OUT / "phase2-retrieval-timing-header.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    export_retrieval()
    export_rag()
    export_contracts()
    export_tasks()
    export_bm25_scale()
    export_hard_negatives()
    export_contradictions()
    export_streaming()
    export_concurrency()
    export_function_tool()
    export_sdk_vs_http()
    export_structured_output()
    export_cache_usage()
    export_retrieval_rss()
    export_retrieval_selection()
    export_retrieval_timing_header()
    for path in sorted(OUT.glob("*.json")):
        print(path)


if __name__ == "__main__":
    main()
