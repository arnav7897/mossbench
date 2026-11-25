# Moss review — one-page draft

*Draft for the candidate to edit into their own voice before submission.*

**Repository:** Local Git history is ready; public GitHub publication is pending authorization.

I evaluated Moss retrieval, hosted inference, and browser Tasks through a small Python CLI and saved the raw measurements so the results can be reproduced. I used official FastAPI, Celery, Redis, and PostgreSQL documentation, alongside the synthetic corpus used for controlled checks.

**Retrieval.** On 618 chunks and 40 labeled questions, Moss's default hybrid setting (`alpha=0.8`) found the relevant source page within the top 10 for every query. Evaluation Recall@1 was 0.813; p50/p95 query latency was 9.184/11.689 ms across 120 measured calls. The alpha 0.5 hybrid setting had the same Recall@1 and slightly better top-five recall in this sample. Moss keyword-only mode was faster than this local BM25 implementation (0.851 vs. 15.124 ms p50); this does not establish a general speed advantage because the measured query paths differ.

**Inference.** I compared LLM-only, manual RAG, and hosted RAG on the same 40 answerable questions. Manual source-grounded review scored them 31/40, 30/40, and 32/40. All 120 requests succeeded, but hosted RAG's one-answer lead is too small to generalize, and the saved responses did not show which hosted passages were used. Both RAG modes gave the wrong scope for Celery task rate limits. Moss's response usage showed tokens but not dollar charges, so I did not estimate cost from tokens.

**Tasks.** Bounded public-doc tasks completed, including structured extraction, an unreachable URL that was reported honestly, cancellation, resume using the same task ID, artifact download with checksum, runtime/model-cost limits, duplicate submission with an idempotency key, and a cancel/poll race. Model usage costs were available for some tasks; total browser/task billing was not guaranteed by those values.

**What I would improve.** I would expose retrieved passage IDs and source text in hosted RAG responses, add per-response cost reconciliation, and return stage-specific diagnostics when a web-source crawl fails. A bounded FastAPI crawl failed with `CRAWL_FAILED`, while direct fetching of the same public page succeeded. I also fixed a local SDK integration error where async index methods were not awaited.

**Coverage.** Portal UI/Playwright testing was intentionally skipped. A two-question unsupported-answer probe produced abstentions in both LLM-only and manual RAG, but is too small to estimate general behavior. I also ran basic streaming, function-tool, structured-output, cache-usage, SDK/raw HTTP, and 1/2/5 concurrency smoke checks; the concurrency run returned 429s at higher levels. These are small observations, not broad suites. Memory/RSS, multi-index isolation, early stream disconnect, and tool failure paths remain untested. The detailed metrics, raw outputs, and limitations are in [`benchmark-report.md`](benchmark-report.md).
