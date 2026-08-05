# Libelle v0.3 Staging Deployment

This document captures the current manual deployment path for the Libelle v0.3 staging environment.

## Purpose

The v0.3 staging environment allows the team to test the reviewer dashboard, parser results, ops workflow, Cloudflare Access gating, and staging Sheet/Drive configuration without changing the current public production surface at `libelle.io`.

## Current Staging URL

```text
https://staging.libelle.io
```

The staging dashboard is protected by Cloudflare Access.

Unauthenticated requests should redirect to the Cloudflare Access login flow.

## Production vs Staging Topology

| Area | Production v0.1 | Staging v0.3 |
|---|---|---|
| URL | `https://libelle.io` | `https://staging.libelle.io` |
| Frontend root | `/var/www/libelle` | `/var/www/libelle-staging` |
| Backend checkout | `/opt/libelle/backend` | `/opt/libelle-v03-staging/backend` |
| Backend service | `libelle-backend.service` | `libelle-v03-backend.service` |
| Backend port | `127.0.0.1:8000` | `127.0.0.1:8003` |
| Access | Public current surface | Cloudflare Access gated |
| Data | Current live / legacy Sheet configuration | Isolated v0.3 4-tab Sheet |
| Drive | Current live / legacy Drive configuration | Isolated staging Drive folder |

## Raspberry Pi Paths

### Repo checkout

```text
/opt/libelle-v03-staging
```

### Backend

```text
/opt/libelle-v03-staging/backend
```

### Frontend

```text
/opt/libelle-v03-staging/frontend
```

### Built frontend served by nginx

```text
/var/www/libelle-staging
```

### Environment file

```text
/etc/libelle/libelle-v03-staging.env
```

### Backend env symlink

```text
/opt/libelle-v03-staging/backend/.env -> /etc/libelle/libelle-v03-staging.env
```

## Systemd Service

The v0.3 staging backend runs as:

```text
libelle-v03-backend.service
```

Expected backend bind address:

```text
127.0.0.1:8003
```

## Public Intake Client IP Trust

Public intake rate limiting does not trust forwarded client-IP headers by
default. Staging should enable `CF-Connecting-IP` only for the controlled local
Cloudflare/nginx hop:

```text
INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS=127.0.0.1/32,::1/128
INTAKE_TRUSTED_FORWARD_PROXY_CIDRS=
```

See [Public Intake Proxy Trust](./intake_proxy_trust.md) for the local,
staging, and production trust boundary and the expected production origin-access
restrictions.

Useful commands:

```bash
sudo systemctl status libelle-v03-backend --no-pager -l
sudo systemctl restart libelle-v03-backend
sudo journalctl -u libelle-v03-backend -n 100 --no-pager
```

## Cloudflare Tunnel

The existing Cloudflare Tunnel routes public hostnames to the Raspberry Pi.

Current staging route:

```text
staging.libelle.io -> http://localhost:80
```

The tunnel config is managed on the Pi at:

```text
/etc/cloudflared/config.yml
```

Useful commands:

```bash
sudo systemctl status cloudflared --no-pager -l
sudo systemctl restart cloudflared
```

## Nginx

Staging is served through the nginx server block:

```text
/etc/nginx/sites-available/staging.libelle.io
```

Enabled through:

```text
/etc/nginx/sites-enabled/staging.libelle.io
```

The staging server block serves the React frontend from:

```text
/var/www/libelle-staging
```

and proxies backend routes to:

```text
http://127.0.0.1:8003
```

Important backend routes must be proxied before the React single-page-app fallback route.

Known backend routes include:

```text
/health
/debug/config
/authorize
/oauth2callback
/api/
/docs
/openapi.json
/snapshot
/ops/statuses
/ops/update
/resumes/
/submissions/
```

If one of these routes falls through to the React app, the browser may show an error like:

```text
Unexpected token '<', "<!doctype "... is not valid JSON
```

That means the dashboard expected JSON but received `index.html`.

## Manual Deployment Checklist

Run these commands on the Raspberry Pi.

### 1. SSH into the Pi

```bash
ssh tcus-admin@raspberrypi
```

### 2. Update staging checkout

```bash
cd /opt/libelle-v03-staging

git branch --show-current
git status --short

git fetch origin
git pull origin main
```

### 3. Update backend dependencies

```bash
cd /opt/libelle-v03-staging/backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Restart staging backend

```bash
sudo systemctl restart libelle-v03-backend
sudo systemctl status libelle-v03-backend --no-pager -l
```

### 5. Verify backend health

```bash
curl -i http://127.0.0.1:8003/health
```

Expected result:

```text
HTTP/1.1 200 OK
content-type: application/json
```

### 6. Build frontend

```bash
cd /opt/libelle-v03-staging/frontend

npm install
npm run build
```

### 7. Publish frontend build

```bash
sudo rsync -av --delete dist/ /var/www/libelle-staging/
```

### 8. Test and reload nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Local Route Verification

Use a known staging `submission_id` for route tests:

```bash
SID="<known-staging-submission-id>"

for path in \
  /health \
  /snapshot \
  /ops/statuses \
  /resumes/$SID \
  /submissions/$SID/ops
do
  echo ""
  echo "=== $path ==="
  curl --max-time 20 -i "http://127.0.0.1$path" -H "Host: staging.libelle.io" | head -30
done
```

Expected behavior:

- `/health` returns JSON
- `/snapshot` returns JSON
- `/ops/statuses` returns JSON
- `/resumes/{submission_id}` reaches the backend and enforces actor identity
- `/submissions/{submission_id}/ops` reaches the backend and allows POST only

## Ops Writeback Smoke Test

Use a known staging submission ID.

```bash
SID="<known-staging-submission-id>"

curl --max-time 20 -i \
  -H "Host: staging.libelle.io" \
  -H "cf-access-authenticated-user-email: kevin@thechamberofus.org" \
  --json "{
    \"submission_id\": \"$SID\",
    \"status\": \"reviewed\",
    \"notes\": \"Staging smoke test after deploy\"
  }" \
  http://127.0.0.1/ops/update
```

Expected result:

```text
HTTP/1.1 200 OK
```

and a JSON response with:

```text
"status": "updated"
```

The updated ops state should appear in `/snapshot`.

## Public Cloudflare Access Verification

From the Pi or another terminal:

```bash
curl -I https://staging.libelle.io
curl -i https://staging.libelle.io/health | head -30
```

Expected unauthenticated behavior:

```text
HTTP/2 302
location: https://thechamberofus.cloudflareaccess.com/...
```

A `302` redirect to Cloudflare Access is expected and means public unauthenticated access is gated.

## Browser Smoke Test

After deployment, an authorized reviewer should verify:

- login through Cloudflare Access works
- dashboard loads
- test submission appears
- Parser Results renders
- Ops renders
- Errors remains clean for a successful submission
- status save works
- notes save works
- refresh shows saved status/notes
- `updated_by` reflects the authenticated actor

## PyMuPDF Dependency Note

The staging environment currently uses a newer PyMuPDF version than the older repository pin that previously caused install problems on newer Python environments.

Observed issue:

- `PyMuPDF==1.22.5` can fail to install on newer Python/macOS/aarch64 environments because pip may attempt a source build.
- `PyMuPDF==1.27.2.3` installed successfully during staging setup.

This should be tracked separately as a dependency maintenance issue so the repository pin matches supported local and staging environments.

## Rollback Notes

If a staging deploy fails:

1. Do not change production `libelle.io`.
2. Check backend logs:

```bash
sudo journalctl -u libelle-v03-backend -n 100 --no-pager
```

3. Check service status:

```bash
sudo systemctl status libelle-v03-backend --no-pager -l
sudo systemctl status nginx --no-pager -l
sudo systemctl status cloudflared --no-pager -l
```

4. If frontend deploy caused the issue, restore `/var/www/libelle-staging` from a known good build or rebuild from the previous working commit.
5. If nginx config caused the issue, restore the most recent backup in:

```text
/etc/nginx/sites-available/staging.libelle.io.bak-*
```

then run:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Future Automation Path

The current staging deployment is manual.

Future automation should consider:

- a checked-in deploy script for staging
- GitHub Actions deployment after merge to `main`
- explicit staging environment secrets
- pre-deploy tests
- frontend build artifact upload
- backend dependency install strategy
- post-deploy health checks
- post-deploy smoke test checklist
- rollback instructions

Until then, manual deployment should follow this document.
