# Phase 3 · Browser tasks, recovery and limits

## What I tested

I submitted bounded public-documentation tasks, validated structured output, downloaded an artifact, resumed polling in a fresh client and submitted the same request twice with an idempotency key. I measured cancellation and ran two independent tasks at the same time with different limits.

## What went well

| Check | What I expected | What I observed |
|---|---|---|
| Idempotency and recovery | Get back to the original job | Two creates with the same key returned the same ID. A fresh client resumed polling the original task. |
| Cancellation | Reach a terminal state after cancelling | Active cancellation reached observed terminal status in 3.968 s. A concurrent cancel and poll saw running followed by cancelled. Cancelling an already completed job preserved its state. |
| Validation | Reject invalid configuration and IDs | A 30-second runtime and a $0.001 model limit were rejected. An invalid task ID returned `not_found_error`. |
| Output | Return the requested fields and an intact file | All four extraction results passed schema validation. A downloaded 79-byte artifact matched the declared size and contained the expected Python docs title and URL. Early access returned `task_not_finished`. |
| Unreachable page | Accurately report reachability | The browser reported the site was unreachable. This satisfied the specific goal. |
| Runtime cutoff | A 90-second monitoring goal should hit its 60-second limit | The task failed with `time_limit`. Moss timestamps spanned 61.234 s. The polling client observed the result at 63.835 s. |
| Concurrent jobs | Each job respects its own settings | Two service runs overlapped for 30.376 s. One completed in 58.169 s within its 60 s limit. The other stopped with `budget_exceeded`. |

## Recommendations

Explain at the spend control that model calls already in flight can finish and bill. This is how Moss documents the limit. [Moss Tasks limits](https://docs.moss.dev/docs/inference/tasks.md) In the overlapping run, the service echoed the requested $0.01 model limit and reported $0.017258 in model usage, $0.007258 above it. A separate shorter task stayed below the same cap at $0.006023. These figures come from the task's usage field. Final billed charges were unavailable. Five initial tasks reached terminal completion and four had schemas to validate. Each count describes its own check.

## How I’d fix it

For an optional strict cap, I’d reserve its maximum allowed cost against the remaining budget before starting a step and constrain its output allowance. If the remaining balance cannot fund the step, stop and return partial results. Show the requested limit, measured model spend, terminal reason and any separate browser charges together.

[Task lifecycle, schemas and artifact hash](../reports/evidence/phase3-task-evidence.json) · [Timing, limit and concurrency records](../reports/evidence/task-limit-checks.json) · [Limit-check script](../datasets/check_task_limits.py)
