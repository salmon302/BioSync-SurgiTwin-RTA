-- SPDX-License-Identifier: MIT
-- SurgiTwin-RTA compliance tier: FR-DAT-003 finalization guard and FR-DAT-004 audit capture
-- Origin: new in Phase 1 task 1.8 (SNDEV/docs/impl-2026-10-14-audit-capture-roles.md).
-- SRS: FR-DAT-003 (WORM record tables), FR-DAT-004 (computer-generated audit trail with user identity,
--      action type, and pre- and post-change values), FR-DAT-005 (chain append through insert_audit_log).
-- Requires 001-extensions.sql, 002-schema.sql, and 003-triggers.sql (insert_audit_log and prevent_* functions).
-- Idempotent.
--
-- VAL-010 split (SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md):
--   Rejected: UPDATE, DELETE, and TRUNCATE on the WORM tables (003-triggers.sql) and on telemetry_sessions
--     (006-telemetry-sessions.sql). Every column of a WORM row is frozen after insert. A finalized state is
--     written as a new row, not as an UPDATE.
--   Permitted and audited: INSERT, UPDATE, and DELETE on users. The identity columns id, username, and
--     created_at are frozen by users_identity_guard. The other columns may change, and each change writes
--     one audit_log row through insert_audit_log().
--   Rejected: TRUNCATE on users. TRUNCATE skips row-level triggers, so it would remove rows with no audit row.
--
-- Actor and reason for audit rows come from transaction-local settings. The application sets
-- biosync.actor (for example SET LOCAL biosync.actor = 'username') and optionally biosync.reason. When
-- biosync.actor is not set, the actor is the database session user.
--
-- Rejected attempts are not written to audit_log. A rejection raises an exception, the enclosing
-- transaction rolls back, and any audit row written in that transaction rolls back with it.

-- ============================================
-- FR-DAT-003 finalization guard on users (identity columns are frozen)
-- ============================================

CREATE OR REPLACE FUNCTION guard_users_identity()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
        OR NEW.username IS DISTINCT FROM OLD.username
        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION USING MESSAGE = 'users identity columns (id, username, created_at) are frozen. Change rejected for user ' || OLD.username;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_identity_guard ON users;
CREATE TRIGGER users_identity_guard
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION guard_users_identity();

-- ============================================
-- TRUNCATE rejection on users (TRUNCATE bypasses row-level audit capture)
-- ============================================

CREATE OR REPLACE FUNCTION reject_users_truncate()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION USING MESSAGE = 'Table users does not permit TRUNCATE. TRUNCATE bypasses row-level audit capture. Delete rows individually.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_prevent_truncate ON users;
CREATE TRIGGER users_prevent_truncate
    BEFORE TRUNCATE ON users
    FOR EACH STATEMENT EXECUTE FUNCTION reject_users_truncate();

-- ============================================
-- FR-DAT-004 generic audit capture (AFTER row trigger for permitted changes)
-- D_prev is the prior row state (NULL on INSERT). D_new is the new row state, and JSON null on DELETE.
-- Requires an integer or bigint column named id on the audited table.
-- ============================================

CREATE OR REPLACE FUNCTION audit_row_change()
RETURNS TRIGGER AS $$
DECLARE
    v_actor TEXT;
    v_reason TEXT;
    v_record_id BIGINT;
    v_data_prev JSONB := NULL;
    v_data_new JSONB;
BEGIN
    v_actor := COALESCE(NULLIF(current_setting('biosync.actor', true), ''), session_user::TEXT);
    v_reason := NULLIF(current_setting('biosync.reason', true), '');

    IF TG_OP = 'DELETE' THEN
        v_data_prev := to_jsonb(OLD);
        v_data_new := 'null'::JSONB;
        v_record_id := (v_data_prev ->> 'id')::BIGINT;
    ELSE
        v_data_new := to_jsonb(NEW);
        v_record_id := (v_data_new ->> 'id')::BIGINT;
        IF TG_OP = 'UPDATE' THEN
            v_data_prev := to_jsonb(OLD);
        END IF;
    END IF;

    PERFORM insert_audit_log(
        TG_TABLE_NAME::VARCHAR, TG_OP::VARCHAR, v_record_id, v_actor::VARCHAR,
        v_data_new, v_data_prev, v_reason
    );
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_audit_capture ON users;
CREATE TRIGGER users_audit_capture
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON FUNCTION guard_users_identity() IS 'Rejects changes to users id, username, and created_at (SRS FR-DAT-003, FR-DAT-006)';
COMMENT ON FUNCTION reject_users_truncate() IS 'Rejects TRUNCATE on users, which bypasses row-level audit capture (SRS FR-DAT-004)';
COMMENT ON FUNCTION audit_row_change() IS 'Writes an audit_log row for each INSERT, UPDATE, or DELETE through insert_audit_log() (SRS FR-DAT-004)';
COMMENT ON TRIGGER users_identity_guard ON users IS 'Freezes identity columns of users (SRS FR-DAT-003)';
COMMENT ON TRIGGER users_prevent_truncate ON users IS 'Rejects TRUNCATE on users (SRS FR-DAT-004)';
COMMENT ON TRIGGER users_audit_capture ON users IS 'Captures prior and new row states of permitted changes to users (SRS FR-DAT-004)';
