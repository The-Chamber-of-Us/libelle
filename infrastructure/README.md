# Infrastructure (Templates Only)

This directory contains example templates for:

- NGINX configuration
- systemd services
- Cloudflare Tunnel structure

IMPORTANT:
No real credentials, tokens, or secrets should ever be committed here.
Production configuration lives in a private infrastructure repository.

## Durable parser worker

`systemd/libelle-parser-worker.service.template` installs as the single concrete
`libelle-parser-worker.service` on the designated staging/Pi host. See the
[worker runbook](../docs/deployment/parser_worker.md) for dependency gates,
configuration, single-worker inventory, restart/reboot tests, and rollback.
