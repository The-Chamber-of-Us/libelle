# Internal actor trust boundary

Libelle selects **Option A: trusted proxy identity**. Cloudflare Access authenticates reviewers before requests reach Libelle through Cloudflare Tunnel → nginx → FastAPI. The backend accepts only `cf-access-authenticated-user-email` supplied by that protected ingress. It does not decode or authenticate `cf-access-jwt-assertion`; a JWT alone never establishes an actor.

## Required deployment boundary

This is an ingress authentication contract, not application JWT verification. Production and staging must enforce all of the following:

- Protect reviewer routes with an Access application and authenticated-user policy, including `/ops/*`, `/submissions/*/ops`, `/resumes/*`, and reviewer read surfaces such as `/snapshot`. Public intake may remain public, but must not provide an alternate route to protected APIs.
- Validate Access before forwarding. Configure `cloudflared` to validate the Access application token for the expected team and application audience, following [Cloudflare's origin protection guidance](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/).
- Block direct external access to nginx and FastAPI. Keep FastAPI on loopback and restrict nginx's origin listener to the tunnel path using binding/firewall rules. Every hostname, port, and public proxy route reaching these APIs must preserve the same protection. Loopback alone does not prove a request passed Access when a public nginx listener also forwards to it.
- Preserve the Access-generated email header through nginx. Untrusted ingress must strip caller-supplied identity headers and deny protected routes; it must never forward those headers as authenticated identity. Do not use a static reviewer header in production nginx or frontend code.
- Run built frontend assets in deployed environments. Never deploy the Vite development server or enable local actor simulation there.

The backend cannot distinguish a forged header arriving through a misconfigured origin from an Access-generated header. Network isolation and ingress header handling are therefore mandatory. If this boundary cannot be enforced, application JWT verification is required before deployment; merely decoding a JWT is never sufficient.

## Backend behavior

A single email header is required. The backend trims surrounding spaces, lowercases the address, and accepts a single ASCII mailbox with a dotted domain. Missing, blank, duplicate, control-containing, or malformed values fail closed. Display names, address lists, and non-ASCII addresses are not accepted. No JWT, request-body actor field, or development environment variable can replace a missing or invalid header.

`POST /ops/update`, `POST /submissions/{submission_id}/ops`, `PATCH /submissions/{submission_id}/ops`, and `GET /resumes/{submission_id}` reject unusable identity with `401` / `INTERNAL_ACTOR_REQUIRED` before invoking their service. Valid requests retain normalized actor attribution in `ops.updated_by`, `ops_events.actor_email`, and mediated resume access. Reviewer read routes without actor checks still rely on the ingress Access policy.

## Local simulation and verification

The [local development guide](../local-dev-dashboard-writes.md) describes explicit simulation through the local Vite proxy. `VITE_DEV_INTERNAL_ACTOR_EMAIL` adds a header only for `serve` in `development` mode, excluding preview. The backend has no environment-based actor fallback. Local direct-header checks are simulations against a trusted local process, not evidence of authentication.

Repository tests cover fabricated JWT rejection, malformed and duplicate headers, rejection before protected services, existing valid attribution, and the development/build/preview simulation boundary. They do not prove deployed ingress isolation.

Before operational sign-off, record the deployed SHA and verify that unauthenticated requests (including forged email/JWT headers) cannot reach protected APIs through any public hostname or direct origin port; authenticated requests with a spoofed email header must either be rejected or retain the signed-in reviewer's identity. Confirm valid writes retain that identity in both the ops row and event history. Inspect Access policy, tunnel token validation, nginx routes, and firewall rules. These live checks remain required for production acceptance.
