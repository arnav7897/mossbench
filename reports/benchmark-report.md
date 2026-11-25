# MossBench benchmark report

**Run date:** 2026-11-25

**SDK/runtime:** Moss Python SDK 1.26.0, Python 3.12.3, model `moss/fastlane-1` for inference

**Data:** 18 official documentation pages, 618 passages (1,200 characters, 200 overlap), 40 labeled questions. Query SHA-256: `e80af5b85a5013383eb3a6355a9e377d43a33e79a9dc825748438c6eb33aa09b`. Corpus SHA-256: `258e6d94fc66700e91caa84a94800dfe284493437fe893036207d7f2d7d83023`.

## Executive summary

Moss retrieval gave better paraphrase top-rank quality than local BM25 on this small documentation set. The documented default hybrid setting (`alpha=0.8`) reached evaluation Recall@1 0.813 and Recall@10 1.000, with p50/p95 latency of 9.184/11.689 ms across 120 measurements. Moss keyword-only and the local BM25 baseline were faster in the measured setup, but had lower paraphrase Recall@1. All 40 questions found their relevant parent page by top 10 across the default hybrid run.

Retrieval recall did not translate directly into answer quality: LLM-only, manual RAG, and hosted RAG scored 31/40, 30/40, and 32/40, respectively, in a source-grounded manual review. Hosted RAG's one-answer lead is small and its source provenance was unavailable, so it is not strong evidence of a general accuracy advantage.

## Retrieval comparison

Each Moss configuration ran 40 questions × 3 measured repetitions, plus one warmup per question. The 8 held-out questions are reported separately; they are too few for a stable generalization claim. Latency is the measured `MossClient.query` call and includes its local query embedding and search path; it is not a server-only vector timing. All measurements were sequential.

| Retrieval mode | Evaluation R@1 | R@5 | R@10 | MRR | p50 | p95 | n |
|---|---:|---:|---:|---:|---:|---:|---:|
| Moss semantic (`alpha=1`) | 0.750 | 0.969 | 1.000 | 0.838 | 9.139 ms | 11.706 ms | 120 |
| Moss keyword (`alpha=0`) | 0.750 | 0.969 | 0.969 | 0.831 | 0.851 ms | 1.189 ms | 120 |
| Moss hybrid (`alpha=0.5`) | 0.813 | 1.000 | 1.000 | 0.893 | 9.249 ms | 11.938 ms | 120 |
| Moss default hybrid (`alpha=0.8`) | 0.813 | 0.969 | 1.000 | 0.882 | 9.184 ms | 11.689 ms | 120 |
| Local BM25, same 618 input chunks | 0.688 | 0.938 | 1.000 | 0.794 | 15.124 ms | 16.342 ms | 40 |

At evaluation R@1, alpha 0.5 and 0.8 tied. Alpha 0.5 had slightly better R@5 and MRR; the sample is not sufficient to claim an optimal setting. Moss keyword mode was faster than BM25 in this run. These latency numbers compare the end-to-end query paths as implemented here, not equivalent server hardware or a standalone vector kernel. Moss's documented alpha meanings and default are in its [hybrid search guide](https://docs.moss.dev/docs/integrate/hybrid-search.md) and [Python QueryOptions reference](https://docs.moss.dev/docs/reference/python/interfaces/QueryOptions.md).

Aggregate successful throughput was 132.291 queries/s across all four Moss modes and their measured calls. This is not a per-mode QPS comparison; per-mode throughput was not calculated.

### Held-out results

There are four exact and four paraphrase questions in the held-out split. For all four Moss modes, R@5 and R@10 were 1.000 for both categories. Exact R@1 was 0.750. Paraphrase R@1 was 1.000. Local BM25 had R@1 1.000 on both held-out categories. These results have n=4 per category and should be treated as exploratory.

### Retrieval contract checks

The sanitized check summary at [`reports/evidence/phase2-retrieval-contracts.json`](evidence/phase2-retrieval-contracts.json) records:

- Metadata filter `topic = redis`: 10 returned results, all tagged `redis`.
- Empty query: returned an empty result set without an exception.
- No-match query with a high score floor: returned zero results.
- Fresh-client reload: same top-five result IDs before and after reload.
- Upsert of one temporary ID twice: exactly one stored document; revised text was visible and ranked first.
- Delete visibility: the probe was absent from document retrieval and search after deletion.

No second MossBench cloud index was available under the project's three-index plan limit, so multi-index isolation was not tested. The temporary mutation probe was removed and cleanup verified.

## RAG and inference

The 40 supported questions were run once per mode. All 120 requests succeeded, returned nonempty text, and stayed below the 128-token output cap. Review criteria: answer the labeled fact accurately, do not add a material contradiction, and count abstention on these answerable questions as incorrect. For the even-sized 40-call groups, p50 is the runner's upper middle observation (sorted index 20); p95 uses nearest-rank.

| Mode | Correct | p50 | p95 | Input tokens | Output tokens |
|---|---:|---:|---:|---:|---:|
| LLM-only (`retrieve=False`) | 31/40 (77.5%) | 551.644 ms | 915.347 ms | 6,073 | 2,272 |
| Manual RAG (top-three Moss passages in prompt) | 30/40 (75.0%) | 590.886 ms | 756.876 ms | 44,365 | 2,003 |
| Hosted RAG (`retrieve=True`) | 32/40 (80.0%) | 622.351 ms | 832.153 ms | 36,752 | 2,134 |

The answer-by-answer review of all 120 outputs found these incorrect question IDs, recorded in the sanitized [`RAG evidence`](evidence/phase2-real-rag.json). Manual RAG abstained on several facts because its top three returned passages did not contain the answer section; hosted RAG had the same coverage gap on several questions. Both RAG modes incorrectly called Celery rate limits global by default (`rd-017`). This is a clear retrieval/generation quality issue on the measured question, not proof of a general provider defect.

No dollar cost is derived from token counts. Moss response usage provided token counts but no per-call dollar charge. Hosted retrieval source passages/citations were not present in these saved responses, so provenance cannot be verified. Additional smoke checks for streaming, function tools, structured output, cache usage, raw HTTP versus SDK, and concurrency are reported separately below; they are not broad reliability or performance suites.

### Unsupported-answer abstention probe

After the answerable-question run, a separate four-call probe tested two unsupported questions (a production credential and a staff member's personal contact details) through LLM-only and manual-RAG paths. All four answers abstained without supplying the requested secret or personal data; both manual-RAG answers explicitly said the retrieved context did not contain it. This is only two questions in one run, not a broad safety or abstention estimate. Raw responses remain in ignored `results/phase2-abstention/abstention.jsonl`; sanitized outcomes are in [`reports/evidence/phase2-abstention.json`](evidence/phase2-abstention.json). Reproduce with `.venv/bin/mossbench benchmark-abstention --index mossbench-synth-100 --output-dir results/phase2-abstention`.

## Local BM25 scale sweep

The same 50 synthetic queries were run once against deterministic 100-, 1,000-, and 10,000-document corpora. Each corpus contains the same 10 labeled fact documents plus unrelated decoys. Evaluation ranking metrics remained constant while per-query time increased with corpus size:

| Documents | Evaluation R@1 exact (n=13) | Evaluation R@1 paraphrase (n=27) | Evaluation R@10 | p50 | p95 |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.923 | 0.593 | 1.000 | 0.330 ms | 0.667 ms |
| 1,000 | 0.923 | 0.593 | 1.000 | 3.178 ms | 4.506 ms |
| 10,000 | 0.923 | 0.593 | 1.000 | 38.810 ms | 49.547 ms |

These are local standard-library BM25 timings on this machine, not Moss cloud comparisons. The relevance passages are identical at every scale; added documents are unrelated, so the stable recall is expected and does not show robustness to hard negatives. Sanitized details and corpus hashes are in [`reports/evidence/phase2-bm25-scale.json`](evidence/phase2-bm25-scale.json); raw measurements remain under ignored `results/phase2-bm25-scale-*`.

## Unsupported retrieval probe

A supported FastAPI body-validation control ranked its labeled page first. Three manually labeled unsupported questions still returned top-five candidates: the unsupported FastAPI administrator-password question returned a FastAPI response-model page (top score 0.403); an unrelated employee-ownership question returned PostgreSQL vacuuming material (0.186); and the unsupported Redis connection-timeout question returned Celery worker material (0.734). These are four read-only queries on one index. Scores are not calibrated confidence and candidate retrieval alone does not establish answer hallucination; this indicates why RAG should verify passage support and abstain. Raw results and the reproduction script are local; sanitized aggregates are in [`reports/evidence/phase2-hard-negatives.json`](evidence/phase2-hard-negatives.json).

## Contradictory-document probe

Two temporary, explicitly fictional fixture passages claimed different Celery retry limits (5 and 9). Both appeared in the retrieved context, and the model stated that the documents conflicted and cited both values. Cleanup of both fixture IDs was verified. This is one controlled run and does not estimate general contradiction handling. Reproduce with `.venv/bin/python datasets/check_contradictions.py`; sanitized evidence is in [`reports/evidence/phase2-contradictions.json`](evidence/phase2-contradictions.json), while raw response text stays in ignored `results/phase2-contradictions/`.

## Streaming smoke check

One retrieval-free response emitted the expected lifecycle through `response.completed`; concatenated text deltas matched `get_final_response().output_text`. The first text delta arrived at 539.457 ms and the full response completed at 542.133 ms. This is a single observation, not a latency estimate. Early disconnect, stream errors, and stream-vs-nonstream equivalence remain untested. Reproduce with `.venv/bin/python datasets/check_streaming.py`; sanitized events and timings are in [`reports/evidence/phase2-streaming.json`](evidence/phase2-streaming.json), while the text is retained locally under ignored `results/phase2-streaming/`.

## Inference concurrency smoke sweep

Ten retrieval-free, uncached calls were issued at each concurrency level (1, 2, 5), with SDK retries disabled and 8 output tokens allowed per call. Level 1 completed 10/10 (p50 251.621 ms; successful throughput 2.897/s), level 2 completed 8/10 (p50 257.981 ms; 6.354/s), and level 5 completed 1/10 (p50 265.206 ms; 1.331/s). The 11 failures were all HTTP 429 `rate_limit_exceeded`. Levels ran back-to-back in one sweep; these observations do not establish a stable quota or predict behavior after a cooldown. Reproduce with `.venv/bin/python datasets/check_inference_concurrency.py`; full per-call records are local under ignored `results/phase2-inference-concurrency/`, and sanitized summaries are in [`reports/evidence/phase2-inference-concurrency.json`](evidence/phase2-inference-concurrency.json).

## Function-tool smoke check

One forced `order_lookup` function call used a deterministic local fixture (`MOSS-001` → shipped, ETA `2026-11-27`). The client executed the returned call and sent its result back; the follow-up response mentioned the returned shipped status. This verifies the basic function-call round trip only. Invalid arguments, unknown orders, tool errors, and parallel calls remain untested. Reproduce with `.venv/bin/python datasets/check_function_tool.py`; sanitized outcome and token counts are in [`reports/evidence/phase2-function-tool.json`](evidence/phase2-function-tool.json). The raw answer remains under ignored `results/phase2-function-tool/`.

## SDK vs raw HTTP

Equivalent retrieval-free, uncached requests were sent sequentially through the Moss SDK and directly to `/v1/responses`, with matching model, prompt, instructions, output cap, SSE mode, and Moss headers. Both completed with identical text and usage (127 input, 3 output tokens). Observed latency was 878.540 ms via SDK and 410.111 ms via raw HTTP in this pair; this is exploratory, not a stable client-overhead estimate. Reproduce with `.venv/bin/python datasets/check_sdk_vs_http.py`; sanitized values are in [`reports/evidence/phase2-sdk-vs-http.json`](evidence/phase2-sdk-vs-http.json), with full local output in ignored `results/phase2-sdk-vs-http/`.

## Structured-output smoke check

One retrieval-free call using the Responses `text.format` JSON Schema form completed. The output parsed as JSON and passed local checks for the required `status="ready"` enum, integer `count`, and exact object keys. This is one simple schema and does not establish broader schema-feature support. Reproduce with `.venv/bin/python datasets/check_structured_output.py`; the raw answer is local under ignored `results/phase2-structured-output/`, and the sanitized validation summary is in [`reports/evidence/phase2-structured-output.json`](evidence/phase2-structured-output.json).

## Cache-usage probe

Three sequential retrieval-free requests compared two identical prompts with a unique-prefix prompt. All outputs matched the requested short response. The first identical call reported 143 input/0 cached tokens at 425.459 ms; the second reported 0 input/0 cached tokens at 68.239 ms; the unique-prefix call reported 144 input/0 cached tokens at 138.578 ms. The response usage did not report cached tokens for any call, so the latency and zero-input observation are not treated as proof of a cache hit. Reproduce with `.venv/bin/python datasets/check_cache_usage.py`; sanitized usage is in [`reports/evidence/phase2-cache.json`](evidence/phase2-cache.json), and raw output is under ignored `results/phase2-cache/`.

## Tasks API evidence

The existing Phase 3 evidence covered five bounded public-doc tasks, cancellation, resuming the same task ID through a fresh client, artifact availability/checksum, runtime and model-cost limits, duplicate submission using one idempotency key, and a cancel/poll race. All five initial smoke tasks reached terminal `completed`; the unreachable URL produced an honest failure rather than fabricated facts. These observations are single runs, not a reliability estimate. Model usage cost is recorded separately from total browser/task billing.

- Sanitized aggregates: [`reports/evidence/phase3-task-evidence.json`](evidence/phase3-task-evidence.json).
- Full records are retained locally under `results/phase3-*`; raw task IDs and outputs are excluded from the public bundle.

## Ranked findings and actions

1. **High — improve answer-passage coverage and expose provenance.** Top-10 parent-page recall was perfect, but the top-three RAG context missed supported facts, and hosted source passages were not saved. A passage-level result/citation contract would make this diagnosable. See [`findings/phase4.md`](../findings/phase4.md#f1-rag-coverage-and-provenance).
2. **High — review incorrect Celery rate-limit claim.** Both RAG modes reported global limits for `rd-017`, contrary to the source page. Add an explicit evidence/abstention check for configuration-scope questions. This is confirmed in this sample, not a general error-rate claim.
3. **Medium — investigate the hosted web-source crawl failure.** One bounded FastAPI crawl returned `CRAWL_FAILED`; direct public-page fetching succeeded and uploaded text worked. Root cause remains unconfirmed.
4. **Medium — add inference cost visibility.** Per-call dollar charge was unavailable in the response object. Keep billing figures explicitly unknown rather than extrapolating from tokens.
5. **Fixed locally — await async retrieval SDK methods.** The initial adapter printed index success while an async create coroutine was never awaited. The adapter now awaits SDK mutations and close.
6. **Fixed locally — validate Tasks runtime bounds.** The API reports a 60–7,200 second range. The CLI and Tasks client now reject values outside it before submission; CLI calls with 30 and 7,201 seconds were verified to stop locally.

## Reproduction

The exact commands, source manifest, and dataset integrity checks are in [`README.md`](../README.md). Public-safe outputs: [`reports/evidence/phase2-real-retrieval.json`](evidence/phase2-real-retrieval.json), [`reports/evidence/phase2-real-rag.json`](evidence/phase2-real-rag.json), [`reports/evidence/phase2-retrieval-contracts.json`](evidence/phase2-retrieval-contracts.json), and [`reports/evidence/phase3-task-evidence.json`](evidence/phase3-task-evidence.json). Full raw results remain in the local ignored `results/` tree.

## Not measured / known limits

- Portal UI / Playwright was explicitly skipped.
- No FAISS or Chroma comparison, Moss cloud scale sweep, or memory/RSS measurement. Concurrency was sampled only in one short 10-call-per-level run; no sustained load or post-cooldown repeat was run. The local BM25 scale sweep is synthetic and includes only unrelated decoys.
- The contradictory-document result is a single controlled smoke check. The four-query unsupported retrieval probe and two-question abstention probe are also too small to estimate general behavior.
- No multi-index isolation test because the only new-project test index slot was unavailable; unrelated user indexes were not queried.
- Streaming, tool calling, structured output, cache usage, and SDK/raw HTTP each received one small smoke comparison; stream disconnect/errors, tool error cases, complex schemas, cache-hit attribution, and broader transport equivalence remain untested. Long-context and inference error-contract suites were not run.
- Six offline unit tests cover metric percentiles/grouping and Tasks runtime/cost validation. Live and offline measurements are saved separately; no mocked result is included in the live benchmark evidence.
- The account dashboard and Portal workflows were not inspected in this phase. No current balance or total billing claim is made.
