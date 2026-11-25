# Portal Review Notes

Use the product-area reports `portal_findings.md`, `inference_api_findings.md`, and `tasks_api_findings.md`, and the summary at `../reports/one-pager.md`.

Authenticated, manual Playwright review, 2026-11-25. Scope: read-only account views plus one controlled browser task (1 minute, $0.05 configured spend cap) to verify task lifecycle. Existing indexes and project settings were not changed. No API key was created.

## Confirmed flows

- Configure > Connect switches among Python, TypeScript, and cURL examples. Configure > Context offers retrieval on/off and all-indexes or selected-index modes. A temporary selection of the existing `mossbench-synth-100` index was discarded; nothing was saved.
- Task creation accepts model, goal, URL, time limit, and spend limit. The bounded Python documentation title task completed in 22 seconds, used 3 steps, and reported the correct page title. Its task detail showed spend at the configured `$0.05` maximum and 31,784 tokens. This demonstrates the UI task workflow and its displayed cap; it does not prove enforcement under concurrent tasks or at the API boundary.
- Analytics and Logs & Traces render after a short SPA transition delay. Inference analytics showed 683 requests, 100% success, 46 ms first-token metric, $0.34 spend, and 489 ms p50 / 1,376 ms p95 end-to-end latency for the displayed 30-day range.
- Retrieval analytics showed 2,106 text queries, 198 retrievals, 8 session minutes, 2.8 MB storage, and 3 indexes. Index-event history loaded 17 entries.
- Usage showed a cycle total of $2.09. Billing showed Developer plan, $7.91 current credit balance, auto-reload off, 1/1 project and 3 indexes per project. Values are a point-in-time dashboard view and may change with activity.
- Logs & Traces request list showed 683 requests, 46 ms first-token p50, 113 ms p95, 0% errors, and 0.1% reply cache. The table loaded and the Index events tab showed index changes.
- Team view showed one owner and that inviting requires an upgrade. Invoices showed a current-cycle $0.00 entry. Profile, project settings, and these views rendered without changing values.

## Issues and follow-up

- Clicking Analytics, Logs & Traces, Usage, Settings, Billing, Invoices, Profile, and Team often produced an immediate stale snapshot from the previous route; a subsequent snapshot showed the correct page. This may be normal delayed SPA rendering, but it makes fast automation snapshots flaky. Wait for a route-specific heading or stable page marker before asserting.
- Analytics’ 2,106 retrieval queries and 198 retrievals are distinct metrics. Do not describe them as equivalent counts. The Usage page likewise separates 2,106 text queries from 198 retrievals.
- Account-wide counts and task totals include prior project activity; they cannot be attributed to this test run. The bounded test’s own task detail is the evidence for its cap and completion.
- Index creation entry points were unavailable because the project already used its 3-index limit; they route to plan comparison. No upload or crawl was attempted.
- API-key creation was not completed. The automatic approval review rejected a persistent security-sensitive key creation even though the key would have been intended for cleanup. Do not work around that block. Ask for explicit targeted authorization if key creation remains required.

## Not exercised

No project deletion, existing-key revocation, credit purchase, auto-reload activation, payment method addition, invoice-email update, profile/security changes, invite, index mutation, or extra paid task was performed. Duplicate submission, runtime enforcement under races, and API-level spend enforcement remain untested.
