# Libelle API Specification

This document defines how the Libelle frontend and backend communicate.

It is the single source of truth for request / response formats.

## Base URL
Local: `http://localhost:8000`
Prod: `https://api.libelle.io`


  ---

## General Rules

- All responses are in JSON
- Authentication is currently **open** (no auth, no tokens)
- Errors return standard HTTP status codes
- File upload is done using `multipart/form-data`
- CORS is restricted to approved origins

---

## Endpoints

### `GET /health`

Used to confirm the backend is online.

**Request**

```http
GET /health
```

**Response – 200 OK**
  ```json
{
  "status": "ok",
  "service": "libelle-backend",
  "timestamp": "2025-11-22T13:04:12Z"
}
  ```



### `POST /api/upload`

Uploads a resume and submits a volunteer application.

**Purpose**
1. Uploads PDF to Google Drive.
2. Creates a base row in the Google Sheet.
3. Triggers parsing + internal logging.
4. Returns submission confirmation to the frontend.

---

### Request

- **Method:** `POST`
- **Content-Type:** `multipart/form-data`

| Key | Type | Required | Description |
|-----|-----|------|-------------|
| file | File (PDF) | ✅ Yes | Resume PDF |
| full_name | String | ✅ Yes | User full name |
| email | String | ✅ Yes | Contact email |
| location | String | ✅ Yes | City/Region |
| interests | String / String[] | ✅ Yes | Areas of interest (array preferred, CSV accepted) |
| availability | String | ✅ Yes | Hours per week |
| experience_level | String | ✅ Yes | Beginner / Mid / Senior |
| linkedin_url | String | No | Optional LinkedIn |
| github_url | String | No | Optional GitHub |
| motivation | String | No | Optional text |
| consent | Boolean | ✅ Yes | Must be true to submit |

For v0.1, all fields are stored but not all are used in matching logic yet.

---

### Response – Success (200)

```json
{
  "status": "success",
  "submission_id": "abc123",
  "message": "Your application has been received"
}
```
### Response – Error (Internal Failure) [500]
```json
{
  "status": "error",
  "code": "PROCESSING_FAILED",
  "message": "We hit a snag while processing your submission. Please try again or reach out to support."
}
```

### Response – Missing File (400)
```json
{
  "status": "error",
  "code": "FILE_REQUIRED",
  "message": "A resume file is required to complete this submission."
}
```
### Response – Validation Error (422)
```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "fields": {
    "email": "Invalid format",
    "full_name": "Required"
  }
}
```


**Frontend Example (JS)**
```js
const formData = new FormData();
formData.append("file", fileInput.files[0]);
formData.append("full_name", fullName);
formData.append("email", email);
formData.append("location", location);
formData.append("interests", interests); // csv or string[]
formData.append("availability", availability);
formData.append("experience_level", experienceLevel);
formData.append("linkedin_url", linkedin);
formData.append("github_url", github);
formData.append("motivation", motivation);
formData.append("consent", true);

fetch(`${API_URL}/api/upload`, {
  method: "POST",
  body: formData
});
```

> ⚠️ **Note (Future State – Not Implemented Yet)**
> Parser confidence scores will be logged internally but not returned to the frontend in v0.1.
> A future version of this API may include:
```json
{
  "parsed_data": {
    "name": { "value": "Jane Doe", "confidence": 0.92 },
    "emails": { "value": ["jane@email.com"], "confidence": 0.88 },
    ...
  },
  "overall_confidence": 0.78
}
```


 **Roadmap (Future Endpoints)**
 These are NOT implemented yet. For visibility only.
```text
POST /api/match
GET  /api/volunteer/{id}
GET  /api/projects
POST /api/manual-sync
```
Notes for Frontend Contributors
- Assume parsing is asynchronous internally but returns a response
- Treat confidence scores as guidance, not truth
- Never expose raw credentials in frontend code
- If backend zone is down, surface clear UI state

## Maintainer

[The Chamber of Us](https://www.thechamberofus.org)
 


