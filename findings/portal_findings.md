# Moss Portal review

This note covers onboarding, project configuration, models, indexes, Playground, Tasks, analytics, logs, usage, billing, account settings, and the reported password-reset behavior. Tests were performed in the authenticated Developer portal. Account-wide totals below include earlier activity and are not attributed to this review alone.

## What worked well

- Navigation separates building (Configure, Playground, Models, Indexes, Tasks), observing (Analytics, Logs & Traces), and management (keys, billing, settings). This is a sensible map for a developer product.
- Configure provides Python, TypeScript, and cURL examples. Context settings expose retrieval enablement and index selection. Model discovery and Playground make it possible to try inference without first writing an integration.
- The task form exposes a goal, URL, runtime limit, and spend limit. Task history and details make status, steps, output, and spend inspectable.
- Analytics and Logs & Traces show useful operational measures. Index-event history gives a readable account of document additions and removals. Billing clearly shows the Developer plan, limits, balance, and auto-reload status.
- The interface has a consistent visual style, familiar labels, and clear sections.

## Friction and recommendations

- Playground selected `deepseek/deepseek-v4.1-flash` while Models labeled `moss/fastlane-1` as the default. Make active Playground model and project default explicit and consistent, or explain the difference.
- Retrieval defaults to all project indexes. Make active index scope conspicuous beside the prompt and in result/log detail so users can tell what data influenced a response.
- Changing Playground/index-picker state produced empty `/v1/responses` POSTs that were aborted and absent from the request log. Reproduce and ensure selection changes do not start billable inference unless the user submits.
- The index picker stayed open after selection and did not dismiss with Escape in the observed run. Support Escape/outside-click dismissal and visible focus handling.
- The project already had three indexes, so sample, upload, and crawl entry points led to plan comparison. Explain the limit at the entry point and offer a clear route to inspect/manage existing indexes.
- The account showed one team member and that inviting requires an upgrade; state plan restrictions before users reach the invite flow.
- The visual review found a coherent interface, but this was not a full accessibility audit. Keyboard interaction should be checked systematically; failure to close the picker with Escape is one concrete keyboard usability issue. Screen-reader semantics, contrast, zoom, and focus order still need dedicated checks.

## Security report from account owner

The account owner reports that a password-reset link remains usable to change the password again after it has already been used once, during its one-hour validity period. Treat this as reported, not independently reproduced. Recommended behavior is to invalidate the token atomically on first successful password change, reject subsequent use, and invalidate other outstanding reset tokens for that account. Reproduce only with a controlled test account and verify the second attempt is rejected without changing the new password.

## Evidence and limits

The authenticated review covered Configure tabs and a discarded index selection, model filters, index-cap entry points, task form/history/detail, analytics tabs, request and index-event logs, usage, billing, invoices, profile, and project/team settings. No billing or account settings were changed, keys created/revoked, users invited, projects deleted, or indexes mutated. See `reports/one-pager.md` and sanitized evidence under `reports/evidence/`.
