-- SurgiTwin-RTA compliance tier: telemetry relay session records
-- Origin: BioSync-Gateway database/migrations/002-schema.sql (telemetry_sessions, adapted)
-- SRS: FR-DAT-001 (relay session records sit in the compliance tier, not the visualization path),
--      FR-DAT-003 (finalized records are immutable), FR-DAT-004 (audit rows for session events),
--      NFR-SEC-001 (client identity is the JWT sub claim).
-- Requires 001-extensions.sql, 002-schema.sql, and 003-triggers.sql (prevent_* functions and
-- insert_audit_log). Idempotent.
--
-- Row pattern: each session writes an 'open' row at connect and a 'finalized' row at disconnect.
-- Both rows share session_uid. No row is updated or deleted (WORM triggers below).

CREATE TABLE IF NOT EXISTS telemetry_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_uid UUID NOT NULL,
    record_status VARCHAR(20) NOT NULL CHECK (record_status IN ('open', 'finalized')),
    client_identity VARCHAR(255) NOT NULL,
    connected_at TIMESTAMPTZ NOT NULL,
    disconnected_at TIMESTAMPTZ,
    points_relayed BIGINT NOT NULL DEFAULT 0 CHECK (points_relayed >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT telemetry_sessions_status_shape CHECK (
        (record_status = 'open' AND disconnected_at IS NULL AND points_relayed = 0)
        OR (record_status = 'finalized' AND disconnected_at IS NOT NULL AND disconnected_at >= connected_at)
    ),
    CONSTRAINT telemetry_sessions_one_row_per_status UNIQUE (session_uid, record_status)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_sessions_connected ON telemetry_sessions(connected_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_sessions_client ON telemetry_sessions(client_identity);

-- ============================================
-- Finalization guard: a 'finalized' row needs an existing 'open' row for the same session
-- ============================================

CREATE OR REPLACE FUNCTION telemetry_session_finalize_guard()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.record_status = 'finalized' AND NOT EXISTS (
        SELECT 1 FROM telemetry_sessions
        WHERE session_uid = NEW.session_uid AND record_status = 'open'
    ) THEN
        RAISE EXCEPTION USING MESSAGE = 'Telemetry session ' || NEW.session_uid::text || ' has no open record; finalization rejected';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS telemetry_sessions_finalize_guard ON telemetry_sessions;
CREATE TRIGGER telemetry_sessions_finalize_guard
    BEFORE INSERT ON telemetry_sessions
    FOR EACH ROW EXECUTE FUNCTION telemetry_session_finalize_guard();

-- ============================================
-- Append-only rejection (same functions as 003-triggers.sql, FOR EACH STATEMENT)
-- ============================================

DROP TRIGGER IF EXISTS telemetry_sessions_prevent_update ON telemetry_sessions;
CREATE TRIGGER telemetry_sessions_prevent_update
    BEFORE UPDATE ON telemetry_sessions
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_update();

DROP TRIGGER IF EXISTS telemetry_sessions_prevent_delete ON telemetry_sessions;
CREATE TRIGGER telemetry_sessions_prevent_delete
    BEFORE DELETE ON telemetry_sessions
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_delete();

DROP TRIGGER IF EXISTS telemetry_sessions_prevent_truncate ON telemetry_sessions;
CREATE TRIGGER telemetry_sessions_prevent_truncate
    BEFORE TRUNCATE ON telemetry_sessions
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_truncate();

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE telemetry_sessions IS 'WebSocket telemetry relay sessions, append-only with open and finalized rows (SRS FR-DAT-001, FR-DAT-003)';
COMMENT ON COLUMN telemetry_sessions.client_identity IS 'JWT sub claim of the connected client (SRS NFR-SEC-001)';
COMMENT ON FUNCTION telemetry_session_finalize_guard() IS 'Rejects a finalized session row without a matching open row (SRS FR-DAT-003)';
