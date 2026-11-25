# Phase 1 findings

Portal UI checks were intentionally skipped. This file records only observations from the API smoke calls and local integration work; it does not claim broad product coverage.

## What worked well

- Moss-hosted inference worked with the project ID and project key. The minimal prompt returned the requested text.
- Moss retrieval accepted the 100-document synthetic corpus, created `mossbench-synth-100`, and returned results for a Celery retry query.
- The Tasks API completed a public Python documentation lookup. The task result included a page title and description; reported model usage was $0.004377.
- The Python SDK exposes async clients for inference, retrieval, and Tasks, with useful task status, usage, and timestamp fields.

## Bugs and important integration findings

- **Fixed: CLI falsely reported index creation success.** Moss SDK methods are async; the initial adapter did not await `create_index` or `close`, so it printed success while the coroutine was never run. The adapter and CLI now await create, load, query, and close. The corrected indexing call completed successfully.
- **Fixed: Tasks result extraction used the wrong field.** Task text is in `task.result.output_text`; `task.result.output` is for structured output. The smoke task was retrieved again and its actual text was added to `results/phase1-task.jsonl`.
- **Tasks runtime minimum:** the API rejected a 30-second limit before task creation; minimum accepted runtime was 60 seconds.
- **Tasks model catalog differs from inference:** `moss/fastlane-1` was rejected for Tasks. `moss-fast` was accepted and completed the smoke run.
- **Credential naming:** the project key is `MOSS_PROJECT_KEY`. The config still accepts the earlier `MOSS_API_KEY` name as a backward-compatible fallback.

## Evidence

- `results/phase1-inference.jsonl` — successful inference smoke call.
- `results/phase1-task.jsonl` — completed task, output, timestamps, usage, and configured limits.
- The retrieval index exists in the Moss project as `mossbench-synth-100`; this confirms a single smoke index build, not scale behavior.

## Limits of these findings

- One smoke request per API surface is not a reliability or performance study.
- The task model cost limit is not a guarantee that total task billing is capped at that amount.
- Portal workflows and live API error-contract cases remain untested.

## Phase 2: first retrieval benchmark

The seeded 100-document corpus contains repeated versions of ten synthetic fact topics. Query labels include every document about the target topic; Recall@K is the fraction of those relevant documents found in the first K ranks. This is a controlled synthetic benchmark, not a comparison with a local FAISS/Chroma baseline.

- Run: 50 labeled queries, 2 measured repetitions each (100 measurements), 1 warmup per query, already-built `mossbench-synth-100` index.
- Query dataset SHA-256: `b635075619ad35ba1264cff8bb80f08cfb33cdb827ae55157a0c44ad0d18b561`.
- Overall query latency: p50 14.669 ms, p95 19.173 ms, exploratory p99 20.862 ms. Successful throughput: 68.99 queries/s for this sequential run.
- Exact-term queries: Recall@1 0.10, Recall@5 0.50, Recall@10 1.00; MRR 1.00.
- Paraphrase queries: Recall@1 0.096, Recall@5 0.478, Recall@10 0.959; MRR 0.963.
- Held-out subset: exact Recall@10 1.00 (n=6); paraphrase Recall@10 0.971 (n=14). The held-out sample is small and not statistically conclusive.
- An earlier calculation treated Recall@K as a binary hit rate. It was corrected to the standard relevant-retrieved / relevant-total fraction and the benchmark was rerun; only corrected values above are retained.

Raw measurements and summary are in `results/phase2-retrieval/retrieval.jsonl` and `results/phase2-retrieval/retrieval-summary.json`.

## Phase 2: local keyword baseline and RAG pilot

- Offline BM25 baseline ran on the same 50 questions and 100-document corpus. Evaluation exact-term Recall@1/5/10 was 0.092/0.469/0.946 (MRR 0.949); paraphrase Recall@1/5/10 was 0.063/0.322/0.652 (MRR 0.671). Local per-query latency was p50 1.397 ms and p95 1.703 ms. This baseline uses a small standard-library BM25 implementation, not FAISS/Chroma or a production-tuned index.
- Against the same fact labels, Moss retrieval had evaluation exact Recall@1/5/10 0.100/0.500/1.000 (MRR 1.000) and paraphrase 0.096/0.478/0.959 (MRR 0.963), with p50 14.669 ms and p95 19.173 ms in the earlier warmed sequential run. These are small synthetic results; the corpus repeats ten facts, so they should not be generalized to real technical docs.
- A three-question pilot called Moss inference in LLM-only, explicit-context, and hosted-retrieval modes (9 paid calls). Manual spot-check: all three modes answered the three questions correctly; the two retrieval modes stayed close to the supplied synthetic facts. This is only a pilot, not a general accuracy estimate. Pilot summaries and outputs are in `results/phase2-rag/`.
- RAG pilot token counts and latency were captured. The Responses usage object does not report dollar cost; no dollar estimate is recorded. Hosted-retrieval requests used the named index and `retrieve=True`; the baseline explicitly used `retrieve=False`.

### Corpus correction and current offline scale baseline

The original corpus generator repeated each of ten answer facts across every corpus size. That made the relevant-document set grow with corpus size and made Recall@K fall mechanically. The original Moss-vs-BM25 comparison and RAG pilot above use that first corpus revision; they are historical and should not be treated as the current cross-size benchmark. Their query dataset hash was `b635075619ad35ba1264cff8bb80f08cfb33cdb827ae55157a0c44ad0d18b561`.

The generator now keeps one canonical document per answer fact and fills larger sizes with deterministic unrelated distractors. The current query hash is `5dbed76da054e5ae5ecaab39b5c6f474885f7d6cff0f279eb66e727d1880de37`. Offline BM25 was rerun at 100, 1,000, and 10,000 documents:

| Corpus size | p50 local query latency | p95 local query latency | Evaluation exact R@1 | Evaluation paraphrase R@1 | Evaluation paraphrase R@10 |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.776 ms | 0.951 ms | 0.923 | 0.593 | 1.000 |
| 1,000 | 14.402 ms | 17.394 ms | 0.923 | 0.593 | 1.000 |
| 10,000 | 134.142 ms | 180.414 ms | 0.923 | 0.593 | 1.000 |

Each size uses 50 queries; the same 10 are held out. Exact evaluation R@5 and R@10, and paraphrase R@5 and R@10, were 1.000 at each size. These results are offline lexical-baseline measurements only. A new Moss index is needed to compare Moss retrieval fairly against this corrected corpus; existing `mossbench-synth-100` was built from the superseded corpus revision.

An attempt to create `mossbench-synth-100-v2` from the corrected 100-document corpus was rejected by Moss with `The project's usage limit has been reached; billing must be updated before it can be used.` The new index was not created. At that point, the cause was unknown.

Follow-up diagnostic: the SDK surfaced the index-build rejection as `MossError` code `UNAUTHORIZED`. A read-only `list_indexes()` call succeeded and returned three ready indexes; a separate retrieval-disabled inference request also completed with 93 total tokens. A one-document index probe returned the same `UNAUTHORIZED` usage-limit message. This narrows the observed issue to cloud index creation/mutation rather than invalid credentials or a general inference outage. It does not reveal whether the cause is exhausted credit, a project spend cap, a paused project state, or a product-side restriction; the account usage/billing details are not exposed by these SDK responses.

The existing `mossbench-synth-100` index remains queryable: the user's Celery retry search returned the known passage at rank 2 and repeated copies at ranks 1 and 3 (IDs `synthetic-00011`, `synthetic-00001`, and `synthetic-00061`). Their `Reference note` text confirms this cloud index contains the superseded repeated-fact corpus, not the corrected distractor corpus now used by the offline baselines.

## Phase 2: plan-limit diagnosis and corrected Moss retrieval run

The dashboard showed a Developer plan limit of three indexes per project; read-only `list_indexes()` returned three indexes. Index creation was rejected at that limit, while inference and index listing worked. Account billing details are intentionally omitted from this shareable finding.

Instead of deleting an index, the corrected 100-document corpus was upserted in place into the MossBench test index using matching IDs. That succeeded without taking another index slot. The corrected benchmark then ran 50 queries twice, one warmup per query, against the updated index:

- Query SHA-256: `5dbed76da054e5ae5ecaab39b5c6f474885f7d6cff0f279eb66e727d1880de37`.
- Overall latency p50 8.616 ms, p95 11.085 ms, exploratory p99 15.620 ms; sequential successful throughput 110.72 queries/s.
- Evaluation exact queries: Recall@1/5/10 = 1.000/1.000/1.000, MRR 1.000 (n=26 repeated measurements).
- Evaluation paraphrases: Recall@1/5/10 = 0.963/1.000/1.000, MRR 0.981 (n=54).
- Held-out exact and paraphrase queries both had Recall@10 1.000 (n=6 and n=14 repeated measurements respectively); this held-out set remains small.
- Compared with BM25 on the same corrected 100-document data, Moss had higher Recall@1/MRR for paraphrases (0.963/0.981 vs. 0.593/0.712); BM25 had lower p50 query latency (0.776 ms vs. 8.616 ms). Moss's latency includes SDK/query embedding work; the offline baseline is lexical scoring in Python, so latency is not an equivalent engine-to-engine comparison.

Corrected Moss raw and summary results are in `results/phase2-retrieval-corrected/`; corrected local baselines are in `results/phase2-keyword-100/`, `results/phase2-keyword-1000/`, and `results/phase2-keyword-10000/`.

The full 50-question/three-mode run was completed. A first pass used a 160-token ceiling and had many LLM-only responses reach that ceiling; it is retained in `results/phase2-rag-full/` as superseded evidence. The suite was rerun with a concise-answer instruction and 128-token cap; none of its 150 responses hit the cap. Latency, token usage, and manual adjudication are documented in `results/phase2-rag-concise/`. Accuracy on supported questions: LLM-only 43/49, manual RAG 48/49, hosted RAG 49/49. The query-set mismatch for FastAPI query parameters is documented separately; hosted provenance and dollar cost remain unavailable.

## Phase 3 Tasks smoke evaluation

Ran five bounded Tasks: one structured extraction, one unreachable URL, and three repeats of the extraction goal. All five reached terminal `completed`; all four structured outputs passed local schema checks; the unreachable URL task reported failure honestly; the repeated outputs had consistent titles and source URLs. Reported model usage cost totaled $0.030056; task/browser total cost may differ. Median client-observed duration was 18.467 seconds, and median start-to-finish interval from API timestamps was 16.279 seconds. Full records and limitations are documented in `results/phase3-tasks/`. Broader lifecycle cases (cancel, artifacts, restart/resume, invalid IDs/config) remain to be evaluated.
