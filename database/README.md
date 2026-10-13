# Compliance Database Tier

Status: placeholder. No schema or migrations exist yet.

This directory will hold the PostgreSQL 15+ WORM audit store: `BEFORE UPDATE OR DELETE` triggers, the `pgcrypto` SHA-256 hash chain, and Alembic migrations added by a later step (SRS FR-DAT-003 to FR-DAT-005).

`init/` is mounted into the postgres container at `/docker-entrypoint-initdb.d`. It is empty until the pgcrypto init script is added.
