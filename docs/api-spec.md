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

In deployed environments, the actor is derived from Cloudflare Access headers, preferably `cf-access-authenticated-user-email`, or from the `email` claim in `cf-access-jwt-assertion`. If no actor can be derived, these endpoints return `401` with `INTERNAL_ACTOR_REQUIRED`.

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
