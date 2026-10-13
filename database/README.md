# Compliance Database Tier

PostgreSQL 15+ WORM audit store for SRS FR-DAT-003 to FR-DAT-007.

## Migrations

Apply in order. Every file is idempotent, so re-running is safe.

| File | Purpose |
|:-----|:--------|
| `migrations/001-extensions.sql` | Enables `pgcrypto` for the SHA-256 chain |
| `migrations/002-schema.sql` | Tables: audit_log, users, patients, devices, device_metrics, observations, simulation_runs, simulation_states, rta_switch_events, sila2_rpc_log, surgical_telemetry |
| `migrations/003-triggers.sql` | Append-only rejection triggers, hash chain trigger, `audit_chain_digest()`, `verify_hash_chain()`, `insert_audit_log()` |
| `migrations/hash-chain-check.sql` | Nightly read-only recomputation report (not applied at initialization) |

`migrations/` is the single SQL source. Two paths apply it:

* Compose: `docker-compose.yml` mounts 001, 002, and 003 into the postgres init directory.
* Alembic: `middleware/alembic/versions/0001_initial_schema.py` executes the same three files.

## Append-only enforcement

Rejection triggers are installed for each WORM table: `<table>_prevent_update`,
`<table>_prevent_delete`, and `<table>_prevent_truncate`. They are `FOR EACH STATEMENT`, so they
also reject zero-row statements. `users` is excluded because account lifecycle requires updates.

The triggers do not stop a superuser from running `ALTER TABLE ... DISABLE TRIGGER`. Role
separation (table owner distinct from the application role) is open debt.

## Hash chain

Each `audit_log` row stores `prev_hash`, `current_hash`, `occurred_at` (set by the database), and
the `actor_id`, `data_prev`, `data_new`, and `reason` fields. The digest is
`SHA256(prev_hash || UTC(occurred_at) || actor_id || jsonb(data_prev) || jsonb(data_new) || reason)`.
The insert trigger takes a transaction-scoped advisory lock and assigns `id` under that lock.
Appends require READ COMMITTED isolation (the PostgreSQL default).

Verify with `SELECT * FROM verify_hash_chain();` or the nightly script.

## Known limits

* Client-certificate TLS and `pg_hba` enforcement are not shipped (Gateway R2, open).
* Automatic per-row audit capture for every WORM table (FR-DAT-004) is not implemented. The
  `insert_audit_log()` helper and the audit columns exist.
* Electronic signatures (FR-DAT-006) are not implemented.

See `docs/migration-map.md` for the full list.
