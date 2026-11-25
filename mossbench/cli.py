import argparse
import asyncio

from .config import load_config
from .clients.retrieval import RetrievalClient
from .clients.tasks import TasksClient
from .benchmarks.retrieval import run as run_retrieval_benchmark
from .benchmarks.rag import run as run_rag_benchmark, run_abstention
from .benchmarks.keyword import run as run_keyword_benchmark
from .benchmarks.tasks import run as run_tasks_benchmark
from .benchmarks.task_lifecycle import run as run_task_lifecycle
from .benchmarks.task_edgecases import run as run_task_edgecases
from .benchmarks.task_remaining import run as run_remaining_task_scenarios
from .metrics import write_report
from .state import Ledger
from .telemetry import RequestLogger, start_timer


def main():
    parser = argparse.ArgumentParser(prog="mossbench")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="create a Moss cloud index from a JSONL corpus")
    ingest.add_argument("--index", required=True)
    ingest.add_argument("--corpus", required=True)
    update_index = commands.add_parser("update-index", help="upsert JSONL documents into an existing Moss index")
    update_index.add_argument("--index", required=True)
    update_index.add_argument("--corpus", required=True)
    search = commands.add_parser("search", help="load a Moss cloud index and query it")
    search.add_argument("--index", required=True)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("query")
    ask = commands.add_parser("ask", help="answer a question using passages from your selected index")
    ask.add_argument("--index", required=True)
    ask.add_argument("--top-k", type=int, choices=range(1, 11), default=5)
    ask.add_argument("query")
    commands.add_parser("benchmark", help="use a specific benchmark-* command")
    research = commands.add_parser("research", help="submit or manage a Moss browser task")
    research_ops = research.add_subparsers(dest="research_op", required=True)
    submit = research_ops.add_parser("submit")
    submit.add_argument("--goal", required=True)
    submit.add_argument("--url", required=True)
    submit.add_argument("--max-runtime", type=int, default=60)
    submit.add_argument("--max-model-cost", type=float, default=0.25)
    for op in ("status", "cancel", "resume"):
        command = research_ops.add_parser(op)
        command.add_argument("task_id")
    smoke = commands.add_parser("smoke-inference", help="make one Moss-hosted inference call without retrieval")
    smoke.add_argument("prompt", help="short prompt for the smoke call")
    tasks_smoke = commands.add_parser("smoke-task", help="run one bounded public-docs browser task")
    tasks_smoke.add_argument("--max-cost-usd", type=float, default=0.25)
    retrieval_bench = commands.add_parser("benchmark-retrieval", help="benchmark labeled queries against a loaded Moss index")
    retrieval_bench.add_argument("--index", required=True)
    retrieval_bench.add_argument("--queries", default="datasets/generated/queries.jsonl")
    retrieval_bench.add_argument("--repeats", type=int, default=2)
    retrieval_bench.add_argument("--warmups", type=int, default=1)
    retrieval_bench.add_argument("--alphas", type=float, nargs="+", default=[1.0],
                                 help="1 semantic, 0 keyword, values between them hybrid")
    retrieval_bench.add_argument("--output-dir", default="results/phase2-retrieval")
    rag_bench = commands.add_parser("benchmark-rag", help="compare Moss inference with and without retrieval")
    rag_bench.add_argument("--index", required=True)
    rag_bench.add_argument("--queries", default="datasets/generated/queries.jsonl")
    rag_bench.add_argument("--limit", type=int)
    rag_bench.add_argument("--output-dir", default="results/phase2-rag")
    abstention = commands.add_parser("benchmark-abstention", help="probe unsupported-answer abstention with and without retrieved context")
    abstention.add_argument("--index", required=True)
    abstention.add_argument("--output-dir", default="results/phase2-abstention")
    keyword_bench = commands.add_parser("benchmark-keyword", help="run the offline BM25 baseline")
    keyword_bench.add_argument("--corpus", default="datasets/generated/corpus-100.jsonl")
    keyword_bench.add_argument("--queries", default="datasets/generated/queries.jsonl")
    keyword_bench.add_argument("--output-dir", default="results/phase2-retrieval")
    task_bench = commands.add_parser("benchmark-tasks", help="run bounded Tasks API reliability scenarios")
    task_bench.add_argument("--per-task-cost", type=float, default=0.25)
    task_bench.add_argument("--output-dir", default="results/phase3-tasks")
    lifecycle = commands.add_parser("benchmark-task-lifecycle", help="check cancellation, resume, and artifacts")
    lifecycle.add_argument("--completed-task-id", required=True)
    lifecycle.add_argument("--output-dir", default="results/phase3-lifecycle")
    edgecases = commands.add_parser("benchmark-task-edgecases", help="check runtime/cost limits, idempotency, and races")
    edgecases.add_argument("--output-dir", default="results/phase3-edgecases")
    remaining_tasks = commands.add_parser("benchmark-task-remaining", help="run navigation, conflict, and injection scenarios")
    remaining_tasks.add_argument("--output-dir", default="results/phase3-remaining")
    report = commands.add_parser("report", help="summarize saved request JSONL")
    report.add_argument("input", help="JSONL request records")
    report.add_argument("--output", default="report.json", help="output JSON report")
    args = parser.parse_args()
    if args.command == "report":
        write_report(args.input, args.output)
    elif args.command == "smoke-inference":
        asyncio.run(_smoke_inference(args.prompt))
    elif args.command == "smoke-task":
        if not 0 < args.max_cost_usd <= 0.25:
            raise SystemExit("--max-cost-usd must be greater than 0 and at most 0.25")
        asyncio.run(_smoke_task(args.max_cost_usd))
    elif args.command == "benchmark-retrieval":
        config = load_config()
        if args.repeats < 1 or args.warmups < 0:
            raise SystemExit("repeats must be >= 1 and warmups must be >= 0")
        summary = asyncio.run(run_retrieval_benchmark(config.moss_project_id, config.moss_project_key,
            args.index, args.queries, args.repeats, args.warmups, args.output_dir, args.alphas))
        print(summary)
    elif args.command == "benchmark-rag":
        config = load_config()
        if args.limit is not None and args.limit < 1:
            raise SystemExit("limit must be >= 1")
        summary = asyncio.run(run_rag_benchmark(config.moss_project_id, config.moss_project_key,
            config.moss_model, args.index, args.queries, args.output_dir, args.limit))
        print(summary)
    elif args.command == "benchmark-abstention":
        config = load_config()
        if not config.moss_project_id or not config.moss_project_key:
            raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
        rows = asyncio.run(run_abstention(config.moss_project_id, config.moss_project_key,
            config.moss_model, args.index, args.output_dir))
        print(f"Completed {len(rows)} unsupported-answer probes")
    elif args.command == "benchmark-keyword":
        print(run_keyword_benchmark(args.corpus, args.queries, args.output_dir))
    elif args.command == "benchmark-tasks":
        config = load_config()
        if not config.moss_project_id or not config.moss_project_key:
            raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
        if not 0 < args.per_task_cost <= 0.25:
            raise SystemExit("per-task model cost must be greater than 0 and at most 0.25")
        print(asyncio.run(run_tasks_benchmark(config.moss_project_id, config.moss_project_key,
            args.output_dir, args.per_task_cost)))
    elif args.command == "benchmark-task-lifecycle":
        config = load_config()
        print(asyncio.run(run_task_lifecycle(config.moss_project_id, config.moss_project_key,
            args.completed_task_id, args.output_dir)))
    elif args.command == "benchmark-task-edgecases":
        config = load_config()
        print(asyncio.run(run_task_edgecases(config.moss_project_id, config.moss_project_key, args.output_dir)))
    elif args.command == "benchmark-task-remaining":
        config = load_config()
        print(asyncio.run(run_remaining_task_scenarios(config.moss_project_id, config.moss_project_key, args.output_dir)))
    elif args.command == "research":
        config = load_config()
        if not config.moss_project_id or not config.moss_project_key:
            raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
        if args.research_op == "submit" and (not 60 <= args.max_runtime <= 7200 or not 0 < args.max_model_cost <= 0.25):
            raise SystemExit("runtime must be 60-7200 seconds; max model cost must be > 0 and <= 0.25")
        asyncio.run(_research_command(args, config))
    elif args.command in {"ingest", "update-index", "search", "ask"}:
        config = load_config()
        if not config.moss_project_id or not config.moss_project_key:
            raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
        asyncio.run(_retrieval_command(args, config))
    else:
        parser.error(f"{args.command} is not available until the Moss API adapters are configured")


async def _smoke_inference(prompt):
    from moss import MossInference

    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
    client = MossInference(config.moss_project_id, config.moss_project_key)
    logger = RequestLogger("results/phase1-inference.jsonl")
    started = start_timer()
    try:
        response = await client.responses.create(model=config.moss_model, input=prompt)
    except Exception as exc:
        logger.record(test_id="phase1-inference-smoke", suite="inference", status="error",
                      started=started, model=config.moss_model,
                      error={"type": type(exc).__name__})
        raise
    logger.record(test_id="phase1-inference-smoke", suite="inference", status="success",
                  started=started, model=config.moss_model)
    print(response.output_text)


async def _retrieval_command(args, config):
    client = RetrievalClient(config.moss_project_id, config.moss_project_key)
    try:
        if args.command == "ingest":
            result = await client.ingest(args.index, args.corpus)
            print(f"Index ready: {args.index}; result={result}")
        elif args.command == "update-index":
            result = await client.update(args.index, args.corpus)
            print(f"Index updated: {args.index}; result={result}")
        else:
            result = await client.search(args.index, args.query, args.top_k)
            if args.command == "ask":
                await _answer_from_passages(config, args.query, result.docs)
                return
            print(f"index={result.index_name} latency_ms={result.time_taken_ms}")
            for rank, doc in enumerate(result.docs, 1):
                print(f"{rank}. id={doc.id} score={doc.score:.4f} metadata={doc.metadata}\n{doc.text}")
    finally:
        await client.close()


async def _answer_from_passages(config, question, documents):
    from moss import MossInference

    if not documents:
        print("No passages found in this index.")
        return
    passages = "\n\n".join(f"[{n}] {doc.text}" for n, doc in enumerate(documents, 1))
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0)
    try:
        response = await client.responses.create(
            model=config.moss_model, input=f"Passages:\n{passages}\n\nQuestion: {question}",
            instructions="Answer from the supplied passages. Cite passage numbers. If the passages lack the answer, say so.",
            retrieve=False, cache=False, max_output_tokens=256)
        if response.status != "completed" or not (response.output_text or "").strip():
            raise SystemExit(f"No complete answer received (response status: {response.status}).")
        print(response.output_text)
        print("\nRetrieved passages")
        for n, doc in enumerate(documents, 1):
            print(f"[{n}] {doc.id} {(doc.metadata or {}).get('source_url', '')}".rstrip())
    finally:
        await client.close()


async def _smoke_task(max_cost_usd):
    import time
    from datetime import datetime, timezone

    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
    client = TasksClient(config.moss_project_id, config.moss_project_key)
    ledger = Ledger()
    started = time.monotonic()
    try:
        created, task = await client.run_smoke(
            "Visit https://docs.python.org/3/ and report the page title plus one sentence describing the site.",
            model="moss-fast", max_cost_usd=max_cost_usd)
        ledger.save_task(created.id, task.status)
        record = {
            "task_id": created.id, "status": task.status,
            "created_at": created.created_at, "started_at": task.started_at,
            "finished_at": task.finished_at,
            "observed_duration_seconds": round(time.monotonic() - started, 3),
            "model": task.model, "limits": task.limits,
            "result": {
                "text": getattr(getattr(task, "result", None), "output_text", None),
                "structured": getattr(getattr(task, "result", None), "output", None),
            },
            "verification": str(task.verification) if task.verification else None,
            "usage": str(task.usage) if task.usage else None,
            "error": {"type": type(task.error).__name__} if task.error else None,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        logger = RequestLogger("results/phase1-task.jsonl")
        logger.record(test_id="phase1-task-smoke", suite="tasks", status=task.status,
                      started=started, model=task.model, task_id=created.id,
                      task_result=record)
        print(record)
    finally:
        await client.close()


async def _research_command(args, config):
    client = TasksClient(config.moss_project_id, config.moss_project_key)
    ledger = Ledger()
    try:
        if args.research_op == "submit":
            task = await client.submit(args.goal, args.url, max_runtime_seconds=args.max_runtime,
                                       max_cost_usd=args.max_model_cost)
            ledger.save_task(task.id, task.status)
        elif args.research_op == "status":
            task = await client.retrieve(args.task_id)
            ledger.save_task(task.id, task.status)
        elif args.research_op == "cancel":
            task = await client.cancel(args.task_id)
            ledger.save_task(task.id, task.status)
        else:
            task = await client.wait(args.task_id)
            ledger.save_task(task.id, task.status)
        result = task.result
        print({"task_id": task.id, "status": task.status,
               "created_at": task.created_at, "started_at": task.started_at,
               "finished_at": task.finished_at,
               "result": {"output": getattr(result, "output", None),
                          "output_text": getattr(result, "output_text", None)} if result else None,
               "error": {"type": type(task.error).__name__} if task.error else None,
               "usage": str(task.usage) if task.usage else None,
               "limits": task.limits})
    finally:
        await client.close()
