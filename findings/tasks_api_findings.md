# Moss Tasks API review

## What was exercised

- Reviewed task history and opened completed-task details.
- Submitted one bounded task through the Portal: open the Python 3 documentation home page and return only its title; runtime cap 1 minute, spend cap $0.05.
- Verified the terminal result against the public page title and inspected steps, duration, token usage, and displayed spend.
- Reviewed a prior task using `example.invalid`; its details reported the site was unreachable, despite the task being marked Succeeded.

## Results and feedback

- The controlled task completed in 22 seconds, used 3 steps, and returned `Python 3.15.2 documentation`. Its detail reported $0.050 of the configured $0.05 cap and 31,784 tokens. The cap was reached exactly in the UI. This proves one bounded task path, not that every resource charge is capped or that the API enforces limits under concurrency.
- Goal, URL, model, time limit, and spend limit are available in the form; task history/details expose a useful audit trail. Keep configured limits and actual cost together, including when a task fails or is cancelled.
- A task labeled Succeeded even though its target site was unreachable can confuse runner completion with goal success. Distinguish execution completion from verified goal outcome, or clearly label partial/unfulfilled results.
- History showed 13 tasks before the controlled run; the broader Usage dashboard later showed 14 tasks. These are account-level views, not a benchmark success rate. Success stats excluded cancelled tasks in the observed history view, so denominators should be explicit.

## What was not tested

Runtime enforcement, spend overshoot, cancellation timing, duplicate submission/idempotency, simultaneous-task races, polling recovery, malformed task parameters/IDs, schema validation, and artifact integrity remain untested. These need controlled, low-cost tests with separate expected and observed outcomes. Do not report the single successful task as a reliability rate.
