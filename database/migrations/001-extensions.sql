-- SurgiTwin-RTA compliance tier: extensions
-- Origin: BioSync-Gateway database/migrations/001-extensions.sql (adapted)
-- SRS: FR-DAT-005 (pgcrypto SHA-256 hash chain)
-- Adaptation: uuid-ossp and btree_gin are not carried. UUID defaults use
-- gen_random_uuid(), which is in core PostgreSQL 13 and later (target: 15+).

CREATE EXTENSION IF NOT EXISTS pgcrypto;
