# Prototype: Volunteer Intake Flow (AI Studio)

**Context**
This folder is a standalone prototype generated to validate the Volunteer Intake user experience.

**Do not deploy this folder to production.** Use it as a reference implementation for the UI behaviors and backend contract listed below.

---

## API Integration (Critical)

This frontend must adhere to the backend contract defined in the Libelle API Specification.

- **Spec Location:** [`/docs/api-spec.md`](https://github.com/The-Chamber-of-Us/libelle/blob/main/docs/api-spec.md)
- **Endpoint:** `POST /api/upload`
- **Format:** `multipart/form-data` (required for file uploads)

### Required payload (must match backend keys exactly)
The intake form must submit these fields:

Required:
- `file` (PDF, max size 5MB)
- `full_name` (string)
- `email` (string)
- `location` (string)
- `interests` (string or string[]; CSV accepted)
- `availability` (string)
- `experience_level` (enum: `Beginner` / `Mid` / `Senior`)
- `consent` (boolean, must be `true`)

Optional:
- `linkedin_url`
- `github_url`
- `motivation`

### Implementation note (current prototype behavior)
- The prototype gathers `first_name` + `last_name` in the UI and sends `full_name` to the API.
- The prototype uses multiple consent checkboxes in the UI, but submits `consent=true` to match the backend contract.

---

## Core User Flow (MVP)

This prototype uses a **single-page form** (not a stepper). That’s acceptable for v0.1 as long as the API contract and validation rules are enforced.

Required behaviors:
1. Collect all required fields listed above.
2. Enforce that consent is checked before allowing submission.
3. Enforce resume constraints before submission:
   - PDF only
   - Max size 5MB
4. Submit via `multipart/form-data` to `POST /api/upload`.
5. Display success UI on `200 OK`.
6. Handle error states gracefully:
   - `400 FILE_REQUIRED`
   - `422 VALIDATION_ERROR` (render field-level errors from `fields`)
   - `500 PROCESSING_FAILED` (show a clear retry/support message)

---

## Local Development (Important)

This prototype expects an API base URL via Vite env var.

### Option A: Set VITE_API_URL (recommended)
Create a `.env.local` file:

```bash
VITE_API_URL=http://localhost:8000
```
## Option B: Use a Vite proxy

Alternatively, configure a dev proxy so `/api/*` routes to `http://localhost:8000`.

---

## Architecture Notes for Developers

- **Components:** Review `components/ui/*` against the main Libelle design system before migrating.
- **State Management:** Prototype uses local state. Production app should use a form library (React Hook Form recommended) to simplify validation and `FormData` construction.
- **Mocking:** If backend is offline, you may mock a `200 OK` response to test the UI flow, but do not change the field names or contract.

---

## Known validation / UX TODO

Some constraints may be enforced in `IntakeForm.tsx` validation even if the upload component UI allows selection. Verify `components/ui/FileUpload.tsx` also enforces:

- PDF-only selection
- 5MB max size
- clear user feedback on violation

---

## Running this Prototype (Standalone)

```bash
npm install
npm run dev
```
