# Libelle Documentation

**[Current architecture — start here](architecture/contributor_architecture_map.md).**
The Contributor Architecture Map describes the implemented intake, durable parser,
Resolver, snapshot, and reviewer workflow boundaries.

## Current architecture and contracts

- [Contributor Architecture Map](architecture/contributor_architecture_map.md) — canonical current overview.
- [Libelle Engineering Principles](architecture/engineering_principles.md)
- [State Transition Contract](architecture/state_contract.md)
- [System-of-Record Precedence Rules](architecture/system_of_record_precedence.md)
- [Field Ownership Contract](architecture/field_ownership_contract.md)
- [Ops Event History](architecture/ops_event_history.md)
- [Snapshot API](api-spec.md#get-snapshot)
- [Parser worker operations](deployment/parser_worker.md)

## Historical architecture — retained for context

These documents preserve earlier descriptions and design proposals. Use the
current architecture map for implementation guidance.

- [Earlier system architecture](architecture.md)
- [v0.1 data flow](data-flow.md)
- [Original asynchronous parser execution proposal](architecture/async_parser_execution.md)

## Local Development

- [Local Backend Google Setup](local-dev-backend-google-setup.md)
- [Local Dashboard Write Testing](local-dev-dashboard-writes.md)
