# Libelle v0.3 Staging vs Production Data Configuration

This document describes the current production and staging data separation for Libelle.

## Purpose

Libelle v0.3 uses a separate staging environment so reviewer-dashboard work can be tested without changing the current public production surface at `libelle.io`.

The staging environment is intentionally isolated from the current production data layer.

## Environment Summary

| Area | Production v0.1 | Staging v0.3 |
|---|---|---|
| Public URL | `https://libelle.io` | `https://staging.libelle.io` |
| Frontend root | `/var/www/libelle` | `/var/www/libelle-staging` |
| Backend service | `libelle-backend.service` | `libelle-v03-backend.service` |
| Backend port | `127.0.0.1:8000` | `127.0.0.1:8003` |
| Repo checkout | `/opt/libelle` | `/opt/libelle-v03-staging` |
| Data layer | Current live v0.1 / legacy Sheet configuration | Isolated native v0.3 4-tab Google Sheet |
| Drive storage | Current live v0.1 / legacy Drive configuration | Isolated staging Drive folder |
| Access model | Public intake surface | Cloudflare Access gated internal dashboard |

## Staging Data Model

The v0.3 staging backend expects a native Google Sheet with the following tabs:

- `submissions`
- `parser_results`
- `ops`
- `errors`

The staging backend validates this schema during startup. If the expected tabs are missing, the backend should fail fast rather than writing into an incompatible Sheet.

## Sheet and Drive IDs

Do not commit Google Sheet IDs, Drive folder IDs, credentials, service-account JSON, OAuth secrets, or other operational secrets to the repository.

The active staging identifiers are stored on the Raspberry Pi in:

```text
/etc/libelle/libelle-v03-staging.env
```

The backend `.env` symlink points to this environment file:

```text
/opt/libelle-v03-staging/backend/.env -> /etc/libelle/libelle-v03-staging.env
```

## Service Account Access

The Libelle service account must have editor access to the staging Google Sheet and staging Drive folder.

The staging Sheet and Drive folder should remain separate from production/live resources so staging submissions, test resumes, parser results, ops writes, and error records do not affect the current public intake surface.

## Current v0.3 Staging Verification

Staging has been verified with real test submissions.

Confirmed:

- intake submission writes to the staging `submissions` tab
- resume upload writes a file into the staging Drive folder
- `parser_results` rows are created
- `/snapshot` composes records from the v0.3 4-tab schema
- dashboard renders staging submissions
- status/notes writeback updates the `ops` state
- successful submissions do not create false error rows
- unauthenticated public access to `staging.libelle.io` redirects to Cloudflare Access

## Operational Principle

Production and staging must remain separated.

Production `libelle.io` should not be used for v0.3 dashboard testing until the v0.3 path is intentionally promoted.
