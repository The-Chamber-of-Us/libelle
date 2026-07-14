# Reviewer State Labels

This document defines reviewer-facing labels for the backend-derived state
fields exposed by `/snapshot`. It translates the v0.4 trust-contract enums into
dashboard copy without changing backend logic.

Use the explicit state fields as the source of truth. Do not infer pipeline
health from blank payload fields, and do not reinterpret these labels as new
backend states.

## Display Principles

- Degraded records must remain reviewer-visible. A failed parser, failed
  resolver, missing upstream result, unavailable error source, or broken
  pipeline should change the label and severity, not hide the submission.
- Labels should preserve uncertainty. Avoid copy that implies a result is
  complete when a stage has not run, failed, or could not be checked.
- Parser and resolver failures should be named directly so reviewers understand
  why automated enrichment may be missing.
- `normal` means the state is expected and does not require reviewer concern.
  `warning` means the record is usable but automated enrichment or diagnostics
  are incomplete. `blocking` means the automated pipeline state is failed or
  contradictory and should be investigated, while the record still remains
  visible.

## `submission_health_state`

| State | Reviewer label | One-sentence meaning | Severity | Keep visible | UI hint |
| --- | --- | --- | --- | --- | --- |
| `complete` | Complete | The submission, parser output, and resolver output are all available. | normal | Yes | Use a success badge such as `Complete`. |
| `partial_success` | Partially processed | The resume was parsed, but resolver output has not been produced yet. | warning | Yes | Use a warning badge and tooltip: `Parsed; resolver not yet complete.` |
| `no_resume_ok` | No resume provided | The submitter did not provide a resume, so automated resume parsing and resolving were intentionally skipped. | normal | Yes | Use a neutral badge; avoid implying that data is missing unexpectedly. |
| `parser_failed` | Parser failed | The resume parser failed, so parsed and resolved resume details may be unavailable. | blocking | Yes | Use an error badge; surface parser failure detail when available. |
| `resolver_failed` | Resolver failed | The resume was parsed, but skill resolution failed or could not finish. | blocking | Yes | Use an error badge; keep parsed fields visible and mark resolved fields as unavailable. |
| `pending_processing` | Processing pending | The submission exists, but resume upload, parsing, or downstream processing has not completed. | warning | Yes | Use a pending badge or spinner only if live refresh is active; otherwise use static copy. |
| `broken_pipeline` | Pipeline needs review | Backend state is missing, unknown, or contradictory, so automated health cannot be trusted. | blocking | Yes | Use a strong warning badge and route to operational diagnostics. |

## `parsed.parser_result_state`

| State | Reviewer label | One-sentence meaning | Severity | Keep visible | UI hint |
| --- | --- | --- | --- | --- | --- |
| `not_yet_run` | Parser not run | The parser has not produced a result for this submission yet. | warning | Yes | Show parsed fields as pending or unavailable, not as empty facts. |
| `failed` | Parser failed | The parser attempted to run and failed. | blocking | Yes | Use error styling and show the latest parser error summary if present. |
| `skipped` | Parser skipped | Parsing was intentionally skipped, usually because no resume was provided. | normal | Yes | Use neutral copy and avoid prompting reviewers to wait for parser output. |
| `empty_success` | Parsed with no extracted details | The parser completed successfully but did not return usable parsed details. | warning | Yes | Use a warning or muted badge; tooltip: `Parser ran but returned no extracted resume details.` |
| `available` | Parsed details available | Parser output is available for reviewer inspection. | normal | Yes | Show parsed fields normally with any confidence score available. |

## `resolved.resolver_result_state`

| State | Reviewer label | One-sentence meaning | Severity | Keep visible | UI hint |
| --- | --- | --- | --- | --- | --- |
| `not_yet_run` | Resolver not run | The resolver has not produced a result for this submission yet. | warning | Yes | Show resolved skills as pending or unavailable, not as confirmed zero matches. |
| `failed` | Resolver failed | The resolver attempted to run and failed. | blocking | Yes | Use error styling and show the latest resolver error summary if present. |
| `unavailable_upstream` | Resolver unavailable | The resolver could not run because required upstream parser output was missing, skipped, or failed. | warning | Yes | Tooltip: `Resolver depends on parser output that is not available.` |
| `empty_success` | Resolved with no matches | The resolver completed successfully but did not find matching normalized skills. | normal | Yes | Use neutral copy such as `No resolved skill matches`; do not label this as a failure. |
| `available` | Resolved skills available | Resolver output is available for reviewer inspection. | normal | Yes | Show resolved skill matches and coverage score when present. |

## `errors.error_state`

| State | Reviewer label | One-sentence meaning | Severity | Keep visible | UI hint |
| --- | --- | --- | --- | --- | --- |
| `none` | No pipeline errors | The error source was checked and no matching error rows were found. | normal | Yes | Do not show an error badge. |
| `present` | Pipeline error recorded | One or more matching pipeline error rows exist for this submission. | blocking | Yes | Show an error badge and latest error summary, stage, and code when available. |
| `unavailable` | Error status unavailable | The error source could not be checked, so absence of errors is not confirmed. | warning | Yes | Use cautious copy such as `Could not check pipeline errors.` |

## Frontend Usage Notes

- Prefer the top-level `submission_health_state` for the primary record badge.
- Use the nested parser, resolver, and error labels for field-level badges,
  tooltips, filters, or diagnostic panels.
- A `warning` or `blocking` state does not mean the reviewer should lose access
  to the submission. The dashboard should keep the record in the normal review
  flow while clearly marking what automated data is incomplete or unreliable.
- If multiple badges are shown, do not collapse parser and resolver failures
  into a generic failure label. Reviewers should be able to tell which stage
  failed without knowing the internal state machine.
