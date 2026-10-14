-- SPDX-License-Identifier: MIT
-- SurgiTwin-RTA compliance tier: role separation and FR-DAT-006 credential seed
-- Origin: new in Phase 1 task 1.9 (SNDEV/docs/impl-2026-10-14-audit-capture-roles.md).
-- SRS: FR-DAT-003 and FR-DAT-004 (the application cannot disable immutability triggers),
--      FR-DAT-006 (unique individual credentials; RBAC is enforced in middleware/api/auth.py).
-- Requires 002-schema.sql, 003-triggers.sql, 004-audit-capture.sql, and 006-telemetry-sessions.sql
-- (the grants name telemetry_sessions). Apply order: 001, 002, 003, 004, 006, 005.
-- Creating roles and transferring ownership need CREATEROLE and superuser or surgitwin_owner membership.
-- Idempotent.
--
-- Roles (cluster-wide):
--   surgitwin_owner: NOLOGIN. Owns every table and sequence in schema public. Migrations run as a member.
--   surgitwin_app: NOLOGIN. Carries the privileges the application needs. Login roles are granted
--     membership in this role. It owns nothing, and it holds no TRIGGER and no TRUNCATE privilege.
--
-- ALTER TABLE, ENABLE TRIGGER, and DISABLE TRIGGER require table ownership. The application role is blocked
-- by ownership, not by a revoked grant. A superuser can still run them, as allowed by FR-DAT-006 administration.
-- Functions are not transferred. The pgcrypto functions belong to an extension and cannot be altered, and the
-- application role cannot replace any function because it does not own one.

-- ============================================
-- Roles
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'surgitwin_owner') THEN
        CREATE ROLE surgitwin_owner NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'surgitwin_app') THEN
        CREATE ROLE surgitwin_app NOLOGIN;
    END IF;
END;
$$;

GRANT surgitwin_owner TO CURRENT_USER;

-- ============================================
-- Ownership: tables in public belong to surgitwin_owner
-- Sequences owned by serial columns change owner with their table, so only tables are listed.
-- ============================================

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND pg_get_userbyid(c.relowner) <> 'surgitwin_owner'
    LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(r.relname) || ' OWNER TO surgitwin_owner';
    END LOOP;
END;
$$;

-- ============================================
-- Application role grants (least privilege for the application)
-- Record tables: SELECT and INSERT only. No UPDATE, DELETE, or TRUNCATE.
-- users: SELECT, INSERT, and UPDATE. No DELETE and no TRUNCATE.
-- ============================================

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM surgitwin_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM surgitwin_app;

GRANT USAGE ON SCHEMA public TO surgitwin_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO surgitwin_app;
GRANT INSERT ON audit_log, patients, devices, device_metrics, observations,
    simulation_runs, simulation_states, rta_switch_events, sila2_rpc_log,
    surgical_telemetry, telemetry_sessions TO surgitwin_app;
GRANT INSERT, UPDATE ON users TO surgitwin_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO surgitwin_app;

-- ============================================
-- FR-DAT-006 seed: unique individual credentials on users
-- Uniqueness is case-insensitive and whitespace-insensitive, so "Alice" and " alice " cannot
-- create a second account. The check rejects generic account names that are typically shared.
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_individual') THEN
        ALTER TABLE users ADD CONSTRAINT users_username_individual CHECK (
            username = btrim(username)
            AND username <> ''
            AND lower(username) NOT IN (
                'admin', 'administrator', 'root', 'shared', 'guest', 'operator',
                'clinic', 'team', 'generic', 'anonymous'
            )
        );
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS users_username_normalized_key ON users (lower(btrim(username)));
CREATE UNIQUE INDEX IF NOT EXISTS users_email_normalized_key ON users (lower(btrim(email)));

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON ROLE surgitwin_owner IS 'Owns the SurgiTwin-RTA tables and sequences; migrations run as a member (SRS FR-DAT-003)';
COMMENT ON ROLE surgitwin_app IS 'Application privileges: SELECT on all tables, INSERT on record tables, INSERT and UPDATE on users (SRS FR-DAT-003, FR-DAT-004)';
COMMENT ON CONSTRAINT users_username_individual ON users IS 'Rejects untrimmed, empty, and generic shared account names (SRS FR-DAT-006)';
COMMENT ON INDEX users_username_normalized_key IS 'Case- and whitespace-insensitive unique username (SRS FR-DAT-006)';
COMMENT ON INDEX users_email_normalized_key IS 'Case- and whitespace-insensitive unique email (SRS FR-DAT-006)';
