# Public Intake Proxy Trust

Libelle's public intake rate limiter keys per-IP limits from a resolved client IP.
Forwarded IP headers are only trusted when the backend socket peer is inside an
explicitly configured trusted proxy boundary.

## Environment Variables

```text
INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS=
INTAKE_TRUSTED_FORWARD_PROXY_CIDRS=
```

- `INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS` enables `CF-Connecting-IP` only for
  requests whose socket client address is in one of the listed CIDR ranges.
- `INTAKE_TRUSTED_FORWARD_PROXY_CIDRS` enables the leftmost `X-Forwarded-For`
  value only for requests whose socket client address is in one of the listed
  CIDR ranges.
- Empty values are safest: forwarded headers are ignored and the socket client
  address is used.

If both headers are available from a trusted boundary, `CF-Connecting-IP` wins.
Malformed header values are ignored.

## Local Development

Default local development should leave both variables empty. Direct requests to
Uvicorn then use the socket client address and cannot select their own identity
with forwarded headers.

When testing through a local reverse proxy that deliberately strips inbound
forwarded headers and sets its own, configure only that proxy address, for
example:

```text
INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS=127.0.0.1/32,::1/128
```

## Staging

Staging should trust only the local proxy or tunnel hop that is controlled by
TCUS and expected to provide Cloudflare headers. For the current Raspberry Pi
topology, the backend is bound to loopback behind nginx/cloudflared, so staging
can use:

```text
INTAKE_TRUSTED_CLOUDFLARE_PROXY_CIDRS=127.0.0.1/32,::1/128
INTAKE_TRUSTED_FORWARD_PROXY_CIDRS=
```

Keep `X-Forwarded-For` disabled unless a non-Cloudflare trusted proxy path is
intentionally added.

## Production

Production must restrict origin access so public clients cannot reach the
backend or origin nginx directly and inject their own `CF-Connecting-IP` header.
Expected controls:

- Backend binds to localhost or a private interface, not a public interface.
- Public DNS reaches the origin only through Cloudflare Tunnel or an equivalent
  Cloudflare-controlled path.
- Origin firewall rules block direct public HTTP/HTTPS access where applicable.
- The trusted CIDR list includes only the local tunnel/reverse-proxy peer or the
  private load balancer that strips untrusted inbound forwarding headers.
- `INTAKE_TRUSTED_FORWARD_PROXY_CIDRS` remains empty unless the listed proxy is
  responsible for sanitizing and setting `X-Forwarded-For`.

With those controls in place, direct public requests cannot choose their own
client identity, while requests through the configured Cloudflare path resolve
to the volunteer IP from `CF-Connecting-IP`.
