# Local Dashboard Write Testing

Use this guide when local dashboard write actions, such as workflow status changes or notes saves, return `401`.

The deployed dashboard should get reviewer identity from Cloudflare Access. Local development does not naturally include Cloudflare Access headers, so backend ops write endpoints reject writes unless you provide a simulated internal actor.

This local path does not change production authentication. It only tells the local Vite dev proxy to send the same actor identity header that Cloudflare Access sends in deployed environments.

## Protected Write Endpoints

These backend dashboard write endpoints require an internal actor:

- `POST /ops/update`
- `POST /submissions/{submission_id}/ops`
- `PATCH /submissions/{submission_id}/ops`

Current frontend dashboard writes use `POST /ops/update` for status updates and notes saves.

Dashboard read endpoints such as `GET /snapshot` and `GET /ops/statuses` do not require this actor header.

## Expected Actor Header

The backend derives the internal actor from one of these Cloudflare Access request headers:

- `cf-access-authenticated-user-email`
- `cf-access-jwt-assertion`, using the JWT payload `email` claim

If both are present, `cf-access-authenticated-user-email` wins. The backend normalizes the actor to a trimmed lowercase email and writes it into the ops `updated_by` field.

If neither header produces an actor, write endpoints return:

```json
{
  "status": "error",
  "code": "INTERNAL_ACTOR_REQUIRED",
  "message": "Authenticated internal actor identity is required."
}
```

## Local UI Path

1. Start the backend as usual:

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

2. Start the frontend with a local dev actor:

```bash
cd frontend
VITE_DEV_INTERNAL_ACTOR_EMAIL=local.reviewer@example.org npm run dev
```

The Vite dev proxy adds `cf-access-authenticated-user-email` only to local `/ops` and `/submissions` API requests. If `VITE_DEV_INTERNAL_ACTOR_EMAIL` is absent, no actor header is added and writes should continue to fail with `401`.

3. Open the dashboard through the Vite dev server:

```text
http://localhost:3000/inbox
```

4. Select a submission that already has an ops row, then save a workflow status or notes change.

5. Confirm that the UI no longer shows a `401` for valid writes and that the refreshed dashboard record has:

```json
{
  "updated_by": "local.reviewer@example.org"
}
```

## Direct API Checks

Without an actor header, a write should fail:

```bash
curl -i -X POST http://127.0.0.1:8000/ops/update \
  -H 'Content-Type: application/json' \
  -d '{"submission_id":"sub_001","notes":"Local auth check"}'
```

Expected result: `401` with `INTERNAL_ACTOR_REQUIRED`.

With an actor header, the same write should reach the ops write path:

```bash
curl -i -X POST http://127.0.0.1:8000/ops/update \
  -H 'Content-Type: application/json' \
  -H 'cf-access-authenticated-user-email: local.reviewer@example.org' \
  -d '{"submission_id":"sub_001","notes":"Local auth check"}'
```

Expected result:

- `200` with `"status": "updated"` when `sub_001` has an existing ops row
- `404` with `OPS_ROW_NOT_FOUND` when the actor is accepted but that submission has no ops row

The `404` case still confirms local actor simulation is working because the request passed actor enforcement.

## Troubleshooting

- `401` from status or notes saves means the backend did not receive a usable internal actor. Restart `npm run dev` after setting `VITE_DEV_INTERNAL_ACTOR_EMAIL`.
- Open the dashboard through `http://localhost:3000`, not the backend URL, when testing the UI path. The Vite proxy is what adds the local header.
- Do not add this header in production frontend code. Deployed dashboard access remains the Cloudflare Access gate.
- Public intake stays open and is not affected by this setting.
