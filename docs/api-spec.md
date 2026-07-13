# Libelle API Specification

This document defines how the Libelle frontend and backend communicate. It is the single source of truth for request and response formats.

## Base URL
* **Local:** `http://127.0.0.1:8000`
* **Production:** `https://libelle.io` 
*(Note: In production, API routes are proxied via NGINX. Admin/Setup routes may be protected upstream by Cloudflare Zero Trust in production).*

---

## General Rules & Auth

* **Format:** All responses are in JSON.
* **Client Auth:** Public volunteer intake endpoints are currently **open** (no user login required).
* **Backend Auth:** The backend internally uses two Google authentication methods for infrastructure access:
  * **Google Drive:** Uses OAuth user consent (bootstrapped via `/authorize` to create `token.json`).
  * **Google Sheets:** Google Sheets: Uses a service account credential, typically configured via GOOGLE_CREDENTIALS..
* **Uploads:** File upload is handled via `multipart/form-data`.
* **CORS:** Restricted to approved origins.

---

## Dashboard Ops Write Auth

Dashboard read endpoints may be available locally without reviewer identity, but ops write endpoints require an authenticated internal actor:

* `POST /ops/update`
* `POST /submissions/{submission_id}/ops`
* `PATCH /submissions/{submission_id}/ops`

In deployed environments, the actor is derived from Cloudflare Access headers supplied by the protected access layer, preferably `cf-access-authenticated-user-email`, or from the `email` claim in `cf-access-jwt-assertion`. If no actor can be derived, these endpoints return `401` with `INTERNAL_ACTOR_REQUIRED`. Write payload actor fields such as `updated_by` or `actor_email` are ignored; the backend-derived actor is the only value used for `ops.updated_by` and `ops_events.actor_email`.

For local UI testing, see [Local Dashboard Write Testing](local-dev-dashboard-writes.md).

---

## Public Endpoints

### `GET /health`
Used by the frontend to confirm the backend is online before allowing form submission. 
*(Note: The route is `/health`, not `/api/health`).*

**Request**
```http
GET /health
```
Response – 200 OK

```json
{
  "status": "ok",
  "service": "libelle-backend",
  "timestamp": "2026-04-04T19:15:25Z"
}
```

### `GET /snapshot`

Returns the reviewer-facing derived read model. `/snapshot` is never a source of truth and is assembled from the `submissions`, `parser_results`, `ops`, and `errors` tabs at read time.

Each snapshot record always includes these top-level domains:

| Field | Required | Nullable | Meaning |
| ----- | -------- | -------- | ------- |
| `submission_id` | Yes | No | Stable submission identifier. |
| `submission_health_state` | Yes | No | Backend-derived health enum: `complete`, `partial_success`, `no_resume_ok`, `parser_failed`, `resolver_failed`, `pending_processing`, or `broken_pipeline`. |
| `raw` | Yes | No | Intake/submission fields. Missing sheet values are represented as `""`. |
| `parsed` | Yes | No | Parser read model. Always present, even when the parser has not run or failed. |
| `resolved` | Yes | No | Resolver read model. Always present, even when resolver output is unavailable. |
| `ops` | Yes | No | Reviewer workflow state. Defaults to `status: "new"` when no ops row exists. |
| `errors` | Yes | No | Latest error summary. Always present; raw error details are not exposed. |

Missing top-level domains are invalid. Current nested domains are objects, never `null`; empty values inside a domain do not mean the domain is absent. Missing nested fields are invalid unless the response model documents a default.

Partial pipeline states are explicit:

| Domain | Field | Values | Semantics |
| ------ | ----- | ------ | --------- |
| `parsed` | `parser_state` | `pending`, `complete` | Legacy dashboard state retained for compatibility. |
| `parsed` | `parser_result_state` | `not_yet_run`, `failed`, `skipped`, `empty_success`, `available` | Distinguishes parser not run, parser failed, intentionally skipped, successful empty output, and successful non-empty output. |
| `resolved` | `resolver_state` | `not_run`, `resolved`, `zero_matches` | Legacy dashboard state retained for compatibility. |
| `resolved` | `resolver_result_state` | `not_yet_run`, `failed`, `unavailable_upstream`, `empty_success`, `available` | Distinguishes resolver not run, resolver failed, unavailable because parser output is missing/failed, successful empty output, and successful non-empty output. |
| `errors` | `error_state` | `none`, `present`, `unavailable` | Distinguishes no matching error rows, one or more matching error rows, and an unavailable error source. |

Legacy parser/resolver payload fields such as `parsed_skills_raw`, `resolved_skill_ids`, and `unknown_skills` are sheet-backed strings. A blank string means no stored value for that field. JSON array strings such as `"[]"` mean the stage ran and stored an empty list; consumers should use the explicit result-state fields rather than infer pipeline state from these strings.

Date/time fields are strings. `raw.created_at` and `parsed.created_at` use the timestamp format stored by their source row, normally ISO-like `YYYY-MM-DDTHH:MM:SS`; `ops.updated_at` may use the existing UTC sheet format `MM-DD-YYYY HH:MM:SS UTC`. Blank string means no timestamp is available for that nested domain.

Confidence fields retain backward-compatible string values in `parsed.parser_confidence` and `resolved.resolver_coverage`. Numeric siblings `parsed.parser_confidence_score` and `resolved.resolver_coverage_score` are `number | null` and, when present, are bounded from `0.0` to `1.0`.

### `POST /api/upload`
Uploads a resume and submits a volunteer application.

**Purpose**
1. Validates the submitted form.
2. Uploads the PDF resume to Google Drive.
3. Creates a base row in the master Google Sheet.
4. Returns submission confirmation and the Drive URL to the frontend.

**Request**
* **Method:** `POST`
* **Content-Type:** `multipart/form-data`

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `file` | File (PDF) | No* | Resume PDF (*required) |
| `full_name` | String | ✅ Yes | User full name |
| `email` | String | ✅ Yes | Contact email |
| `location` | String | ✅ Yes | City/Region |
| `interests` | String/Array | ✅ Yes | Areas of interest (array preferred, CSV accepted) |
| `availability` | String | ✅ Yes | Hours per week |
| `experience_level`| String | ✅ Yes | Beginner / Mid / Senior |
| `linkedin_url` | String | No | Optional LinkedIn |
| `github_url` | String | No | Optional GitHub |
| `motivation` | String | No | Optional text |
| `consent` | Boolean | ✅ Yes | Must be true to submit |

Response – Success (200)

```JSON
{
  "status": "success",
  "submission_id": "abc123",
  "drive_file_url": "https://drive.google.com/file/d/FILE_ID/view?usp=drive_link"
  "message": "Your application has been received"
}
```

Response – Error (Internal Failure) [500]

```JSON
{
  "status": "error",
  "code": "PROCESSING_FAILED",
  "message": "We hit a snag while processing your submission. Please try again or reach out to support."
}
```
Response – Validation Error (422)

```JSON
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "fields": {
    "email": "Invalid format",
    "full_name": "Required"
  }
}
```
Frontend Example (JS)

```JavaScript
const formData = new FormData();
formData.append("file", fileInput.files[0]);
formData.append("full_name", fullName);
formData.append("email", email);
// ... append other fields
formData.append("consent", true);

fetch(`/api/upload`, {
  method: "POST",
  body: formData
});
```
## Reviewer Endpoints

### `GET /resumes/{submission_id}`

Secure resume proxy for reviewer dashboard users. The backend mediates all
resume access: it resolves the file by `submission_id`, fetches it from Google
Drive server-side, and streams the bytes back. Clients never receive Drive
paths, file ids, or share links, and cannot supply their own.

**Contract**

* Lookup is by `submission_id` **only**. The backend reads `resume_filename`
  and `resume_status` from that submission's own row; email, name, or
  client-provided filenames are never used to locate a file.
* Requires an authenticated internal actor (same Cloudflare Access header
  derivation as the ops write endpoints above). Without one: `401` with
  `INTERNAL_ACTOR_REQUIRED`.
* Every access attempt — served or denied — is logged with `submission_id`,
  actor, outcome, and reason for audit.
* Read-only: access failures never modify any tab and never affect the
  submission's presence in `/snapshot`; degraded resume state is reported by
  this endpoint, not hidden.

**Request**
```http
GET /resumes/{submission_id}
cf-access-authenticated-user-email: reviewer@example.org
```

**Response – 200 OK**

Binary PDF body with:

| Header | Value |
|--------|-------|
| `Content-Type` | `application/pdf` |
| `Content-Disposition` | `inline; filename*=UTF-8''{resume_filename}` |
| `X-Submission-Id` | The requested `submission_id` |

**Error responses** (JSON `detail` with `status`, `code`, `message`):

| Status | Code | Meaning |
|--------|------|---------|
| `401` | `INTERNAL_ACTOR_REQUIRED` | No reviewer identity could be derived. |
| `400` | `VALIDATION_ERROR` | Blank/missing `submission_id`. |
| `404` | `SUBMISSION_NOT_FOUND` | No submission row for this `submission_id`. |
| `404` | `RESUME_NOT_AVAILABLE` | Honest no-resume response: the submission exists but has no uploaded resume (`resume_status` is `missing` or `failed`). |
| `404` | `RESUME_FILE_NOT_FOUND` | Broken reference: the row says `uploaded` but no matching file exists in the Drive folder. |
| `502` | `RESUME_FETCH_FAILED` | The file exists but Drive retrieval failed; degraded storage state, safe to retry. |

## Admin & Setup Endpoints
These endpoints are used to bootstrap the backend's connection to Google Drive. **They are not for frontend user authentication.**

### `GET /authorize`
Starts the Google OAuth consent flow for the backend service. Returns a JSON object with the authorization URL. Current implementation does not automatically redirect the browser.

### `GET /oauth2callback`
Receives the Google authorization code, exchanges it for a token, and saves `token.json` file to the server for persistent backend Drive access. This endpoint must match the redirect URI configured in the Google OAuth client.

## Roadmap (Future Endpoints)
These are NOT implemented yet. For roadmap visibility only.

POST /api/match
GET  /api/volunteer/{id}
GET  /api/projects
POST /api/manual-sync

## Notes for Frontend Contributors 
Assume parsing logic runs asynchronously internally, even though the API returns a synchronous success response.

Never expose raw credentials or API tokens in frontend code.

If the backend health check fails, surface a clear UI state to the user preventing submission.

## Maintainer
[The Chamber of Us](https://www.thechamberofus.org/)
