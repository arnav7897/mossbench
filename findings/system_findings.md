# Phase 4 · End-to-end verification

## What I tested

I asked what transaction isolation level PostgreSQL uses by default. Moss loaded the documentation index and retrieved five passages. Fastlane read them and answered. A separate Moss browser task opened the official manual and returned the answer with an exact supporting sentence. I also ran the same question through the public `mossbench ask` command.

## What went well

| Stage | What I expected | What I observed |
|---|---|---|
| Retrieve | Find the sentence that establishes the default | The first of five passages contained it. Loading the index and searching took 6.481 seconds. |
| Answer | Use that sentence to name the level | Fastlane returned “Read Committed.” The CLI also identified passage 1 and printed its document ID and source URL. |
| Verify | Find the fact independently on the official site | The browser returned the expected level and matching sentence. All three stages took 23.194 seconds together. Browser model usage was $0.004758. |

## Recommendations

Make it easy to tell where a wrong answer originated. A developer needs the question, the passages actually given to the model, its answer and the verification result. The runtime here includes index loading and browser work. The inference response supplied no dollar charge for that stage.

## How I’d fix it

I added a reusable question command that prints the retrieved passage IDs and source URLs after the answer. The separate verification script checks the answer against a known source sentence and records each stage independently. I’d extend that check to the questions already missed in the official-doc benchmark, starting with Celery rate-limit scope.

[Verified run](../reports/evidence/system-workflow.json) · [Reproduction script](../datasets/check_system_workflow.py) · [CLI setup and commands](../README.md)
