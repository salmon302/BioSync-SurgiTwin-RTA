-- SurgiTwin-RTA compliance tier: append-only enforcement and hash chain
-- Origin: BioSync-Gateway database/migrations/003-triggers.sql (adapted)
-- SRS: FR-DAT-003 (WORM record tables), FR-DAT-004 (rejection triggers, audit trail),
--      FR-DAT-005 (pgcrypto SHA-256 chain).
-- Idempotent: functions use CREATE OR REPLACE and triggers are dropped before creation.
--
-- Adaptation from the Gateway:
--   * Rejection triggers are FOR EACH STATEMENT. A row-level trigger does not fire for
--     UPDATE or DELETE statements that match zero rows, so the Gateway could not reject
--     "UPDATE ... WHERE 1=0" attempts.
--   * A BEFORE TRUNCATE rejection trigger is added. Row-level triggers do not fire on TRUNCATE.
--   * The chain append takes a transaction-scoped advisory lock and assigns audit_log.id
--     under that lock, so concurrent inserts cannot fork the chain.
--   * The digest is computed by one shared function (audit_chain_digest) so the insert
--     trigger, verify_hash_chain(), and hash-chain-check.sql use the same byte layout.
--     Timestamps are rendered in UTC, so the digest does not depend on the session TimeZone.

-- ============================================
-- Append-only rejection functions
-- ============================================

CREATE OR REPLACE FUNCTION prevent_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION USING MESSAGE = 'Table ' || TG_TABLE_NAME || ' is append-only. UPDATE operations are not permitted. Use INSERT for new records.';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prevent_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION USING MESSAGE = 'Table ' || TG_TABLE_NAME || ' is append-only. DELETE operations are not permitted. Records cannot be removed.';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prevent_truncate()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION USING MESSAGE = 'Table ' || TG_TABLE_NAME || ' is append-only. TRUNCATE operations are not permitted.';
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Apply append-only triggers to every WORM record table (FR-DAT-003, FR-DAT-004)
-- users is excluded: account lifecycle requires updates (FR-DAT-006).
-- ============================================

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'audit_log', 'patients', 'devices', 'device_metrics', 'observations',
        'simulation_runs', 'simulation_states', 'rta_switch_events',
        'sila2_rpc_log', 'surgical_telemetry'
    ] LOOP
        EXECUTE 'DROP TRIGGER IF EXISTS ' || t || '_prevent_update ON ' || t;
        EXECUTE 'CREATE TRIGGER ' || t || '_prevent_update BEFORE UPDATE ON ' || t
             || ' FOR EACH STATEMENT EXECUTE FUNCTION prevent_update()';
        EXECUTE 'DROP TRIGGER IF EXISTS ' || t || '_prevent_delete ON ' || t;
        EXECUTE 'CREATE TRIGGER ' || t || '_prevent_delete BEFORE DELETE ON ' || t
             || ' FOR EACH STATEMENT EXECUTE FUNCTION prevent_delete()';
        EXECUTE 'DROP TRIGGER IF EXISTS ' || t || '_prevent_truncate ON ' || t;
        EXECUTE 'CREATE TRIGGER ' || t || '_prevent_truncate BEFORE TRUNCATE ON ' || t
             || ' FOR EACH STATEMENT EXECUTE FUNCTION prevent_truncate()';
    END LOOP;
END;
$$;

-- ============================================
-- Hash chain digest (SRS FR-DAT-005)
-- H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i)
-- NULL D_prev is rendered as '{}' (Gateway convention). T_i is rendered in UTC.
-- ============================================

CREATE OR REPLACE FUNCTION audit_chain_digest(
    p_prev_hash TEXT,
    p_occurred_at TIMESTAMPTZ,
    p_actor_id TEXT,
    p_data_prev JSONB,
    p_data_new JSONB,
    p_reason TEXT
) RETURNS TEXT AS $$
BEGIN
    RETURN encode(
        digest(
            COALESCE(p_prev_hash, '') ||
            to_char(p_occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') ||
            COALESCE(p_actor_id, '') ||
            COALESCE(p_data_prev::TEXT, '{}') ||
            COALESCE(p_data_new::TEXT, '{}') ||
            COALESCE(p_reason, '')
        , 'sha256'),
        'hex'
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Chain append trigger (BEFORE INSERT on audit_log)
-- The advisory lock serializes appends. id is assigned under the lock, so id order
-- matches chain order. Requires READ COMMITTED isolation (the PostgreSQL default).
-- ============================================

CREATE OR REPLACE FUNCTION compute_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    v_prev TEXT;
    genesis_hash CONSTANT TEXT := '0000000000000000000000000000000000000000000000000000000000000000';
BEGIN
    PERFORM pg_advisory_xact_lock(7426001);

    NEW.id := nextval(pg_get_serial_sequence('audit_log', 'id')::regclass);

    SELECT current_hash INTO v_prev
    FROM audit_log
    ORDER BY id DESC
    LIMIT 1;

    IF v_prev IS NULL THEN
        v_prev := genesis_hash;
    END IF;

    -- T_i is database-generated and overrides any client-supplied value.
    NEW.occurred_at := clock_timestamp();
    NEW.prev_hash := v_prev;
    NEW.current_hash := audit_chain_digest(
        v_prev, NEW.occurred_at, NEW.actor_id, NEW.data_prev, NEW.data_new, NEW.reason
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_hash_chain ON audit_log;
CREATE TRIGGER audit_log_hash_chain
    BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION compute_hash_chain();

-- ============================================
-- Audit insert helper (SRS FR-DAT-004: user identity, action, pre and post values, reason)
-- ============================================

CREATE OR REPLACE FUNCTION insert_audit_log(
    p_table_name VARCHAR(255),
    p_action VARCHAR(10),
    p_record_id BIGINT,
    p_actor_id VARCHAR(255),
    p_data_new JSONB,
    p_data_prev JSONB DEFAULT NULL,
    p_reason TEXT DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    new_id BIGINT;
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new, data_prev, reason)
    VALUES (p_table_name, p_action, p_record_id, p_actor_id, p_data_new, p_data_prev, p_reason)
    RETURNING id INTO new_id;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Chain verification (SRS FR-DAT-005)
-- Returns ('ok', NULL, NULL) or ('broken', id, table_name) at the first failing row.
-- ============================================

CREATE OR REPLACE FUNCTION verify_hash_chain()
RETURNS TABLE (
    integrity_status VARCHAR(10),
    broken_at_row_id BIGINT,
    broken_at_table VARCHAR(255)
) AS $$
DECLARE
    v_prev TEXT := '0000000000000000000000000000000000000000000000000000000000000000';
    v_expected TEXT;
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT * FROM audit_log ORDER BY id ASC
    LOOP
        IF rec.prev_hash IS DISTINCT FROM v_prev THEN
            integrity_status := 'broken';
            broken_at_row_id := rec.id;
            broken_at_table := rec.table_name;
            RETURN NEXT;
            RETURN;
        END IF;

        v_expected := audit_chain_digest(
            rec.prev_hash, rec.occurred_at, rec.actor_id, rec.data_prev, rec.data_new, rec.reason
        );

        IF v_expected IS DISTINCT FROM rec.current_hash THEN
            integrity_status := 'broken';
            broken_at_row_id := rec.id;
            broken_at_table := rec.table_name;
            RETURN NEXT;
            RETURN;
        END IF;

        v_prev := rec.current_hash;
    END LOOP;

    integrity_status := 'ok';
    broken_at_row_id := NULL;
    broken_at_table := NULL;
    RETURN NEXT;
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON FUNCTION prevent_update() IS 'Rejects UPDATE statements on append-only tables (SRS FR-DAT-004)';
COMMENT ON FUNCTION prevent_delete() IS 'Rejects DELETE statements on append-only tables (SRS FR-DAT-004)';
COMMENT ON FUNCTION prevent_truncate() IS 'Rejects TRUNCATE on append-only tables (SRS FR-DAT-004)';
COMMENT ON FUNCTION audit_chain_digest(TEXT, TIMESTAMPTZ, TEXT, JSONB, JSONB, TEXT) IS 'SHA-256 chain digest over H_{i-1}, T_i, U_i, D_prev, D_new, R_i (SRS FR-DAT-005)';
COMMENT ON FUNCTION compute_hash_chain() IS 'Appends a hash-chained audit_log row under advisory lock (SRS FR-DAT-005)';
COMMENT ON FUNCTION verify_hash_chain() IS 'Verifies audit_log chain integrity and reports the first broken row (SRS FR-DAT-005)';
COMMENT ON FUNCTION insert_audit_log(VARCHAR, VARCHAR, BIGINT, VARCHAR, JSONB, JSONB, TEXT) IS 'Helper to insert an audit entry into the hash chain (SRS FR-DAT-004)';
