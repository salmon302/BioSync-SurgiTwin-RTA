-- SurgiTwin-RTA compliance tier: core schema
-- Origin: BioSync-Gateway database/migrations/002-schema.sql (adapted)
-- SRS: FR-DAT-003 (WORM record tables), FR-DAT-004 (audit columns),
--      FR-DAT-005 (hash chain columns), FR-DAT-006 (users), FR-DAT-007 (FHIR),
--      FR-MS-006 (Pulse state persistence).
-- Triggers are applied in 003-triggers.sql. All statements here are idempotent.

-- ============================================
-- audit_log: hash-chained computer-generated audit trail (FR-DAT-004, FR-DAT-005)
-- Column mapping to the FR-DAT-005 formula H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i):
--   prev_hash = H_{i-1}, occurred_at = T_i, actor_id = U_i,
--   data_prev = D_prev, data_new = D_new, reason = R_i, current_hash = H_i
-- ============================================
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_id VARCHAR(255),
    action VARCHAR(10) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    table_name VARCHAR(255) NOT NULL,
    record_id BIGINT NOT NULL,
    data_prev JSONB,
    data_new JSONB NOT NULL,
    reason TEXT,
    prev_hash VARCHAR(64),
    current_hash VARCHAR(64) NOT NULL CHECK (current_hash ~ '^[a-f0-9]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_audit_log_table_record ON audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_occurred ON audit_log(occurred_at DESC);

-- ============================================
-- users: unique individual credentials for RBAC (FR-DAT-006)
-- Not append-only: account lifecycle (lockout, deactivation) requires updates.
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'clinician', 'researcher', 'qa_officer')),
    scopes TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================
-- patients: synthetic virtual patients only (FR-MS-001 anatomical models, no PHI)
-- ============================================
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    patient_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    synthetic_id VARCHAR(255) UNIQUE NOT NULL CHECK (synthetic_id ~ '^SYN-[A-Za-z0-9_-]+$'),
    demographics JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patients_uid ON patients(patient_uid);
CREATE INDEX IF NOT EXISTS idx_patients_synthetic ON patients(synthetic_id);

-- ============================================
-- devices: instrument and simulated peripheral registry (FR-DAT-002 SiLA 2 servers)
-- ============================================
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_identifier VARCHAR(255) UNIQUE NOT NULL,
    device_name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255),
    model_number VARCHAR(100),
    device_type VARCHAR(100),
    fhir_resource JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_devices_identifier ON devices(device_identifier);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);

-- ============================================
-- device_metrics: FHIR DeviceMetric resources (FR-DAT-007)
-- ============================================
CREATE TABLE IF NOT EXISTS device_metrics (
    id SERIAL PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id),
    metric_name VARCHAR(255) NOT NULL,
    category VARCHAR(50),
    operational_status VARCHAR(50),
    unit VARCHAR(50),
    measurement_period DOUBLE PRECISION,
    fhir_resource JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_metrics_device ON device_metrics(device_id);
CREATE INDEX IF NOT EXISTS idx_device_metrics_name ON device_metrics(metric_name);

-- ============================================
-- simulation_runs: finalized simulation run records (FR-DAT-003)
-- Written once at finalization (WORM). Live status is carried by simulation_states.
-- ============================================
CREATE TABLE IF NOT EXISTS simulation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    run_key VARCHAR(255) UNIQUE NOT NULL,
    patient_id VARCHAR(255),
    engine VARCHAR(50) NOT NULL CHECK (engine IN ('pulse', 'sofa', 'fmi', 'synthetic')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('completed', 'failed', 'aborted')),
    seed JSONB,
    config JSONB,
    output_hashes JSONB,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by VARCHAR(255),
    CONSTRAINT simulation_runs_time_order CHECK (completed_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_patient ON simulation_runs(patient_id);

-- ============================================
-- simulation_states: serialized Pulse engine states, append-only (FR-MS-006, FR-3.6.3 pattern)
-- ============================================
CREATE TABLE IF NOT EXISTS simulation_states (
    id BIGSERIAL PRIMARY KEY,
    state_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    run_key VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('initializing', 'running', 'paused', 'stopped', 'error')),
    engine_state JSONB NOT NULL,
    state_hash VARCHAR(64) NOT NULL CHECK (state_hash ~ '^[a-f0-9]{64}$'),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_simulation_states_run ON simulation_states(run_key, id);

-- ============================================
-- rta_switch_events: RTA Simplex switch decisions and overrides (FR-DAT-003, FR-RTA-001/004)
-- ============================================
CREATE TABLE IF NOT EXISTS rta_switch_events (
    id BIGSERIAL PRIMARY KEY,
    event_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    run_key VARCHAR(255) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('decision', 'override', 'fallback_engaged', 'fallback_released')),
    primary_source VARCHAR(50) NOT NULL CHECK (primary_source IN ('drl', 'teleoperator', 'unknown')),
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('accept', 'reject', 'fallback')),
    envelope_snapshot JSONB NOT NULL,
    operator_id VARCHAR(255),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_rta_switch_events_run ON rta_switch_events(run_key, id);

-- ============================================
-- sila2_rpc_log: SiLA 2 remote procedure call records, written on completion (FR-DAT-002, FR-DAT-003)
-- ============================================
CREATE TABLE IF NOT EXISTS sila2_rpc_log (
    id BIGSERIAL PRIMARY KEY,
    rpc_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    run_key VARCHAR(255),
    device_id INTEGER REFERENCES devices(id),
    server_uid VARCHAR(255) NOT NULL,
    feature_identifier VARCHAR(255) NOT NULL,
    command_identifier VARCHAR(255) NOT NULL,
    request_payload JSONB,
    response_payload JSONB,
    grpc_status VARCHAR(50) NOT NULL,
    error_message TEXT,
    called_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_sila2_rpc_log_run ON sila2_rpc_log(run_key, id);

-- ============================================
-- observations: FHIR R4 Observation resources (FR-DAT-007)
-- ============================================
CREATE TABLE IF NOT EXISTS observations (
    id SERIAL PRIMARY KEY,
    observation_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    device_id INTEGER REFERENCES devices(id),
    patient_id VARCHAR(255),
    run_key VARCHAR(255),
    observation_code VARCHAR(100) NOT NULL,
    value_quantity JSONB NOT NULL,
    unit VARCHAR(50),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB,
    filtered_data JSONB,
    fhir_resource JSONB NOT NULL,
    CONSTRAINT observations_value_check CHECK (value_quantity ? 'value' AND value_quantity ? 'unit')
);

CREATE INDEX IF NOT EXISTS idx_observations_device ON observations(device_id);
CREATE INDEX IF NOT EXISTS idx_observations_patient ON observations(patient_id);
CREATE INDEX IF NOT EXISTS idx_observations_timestamp ON observations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_observations_code ON observations(observation_code);

-- ============================================
-- surgical_telemetry: raw and filtered telemetry samples (FR-RTA-005, FR-3.5.3 pattern)
-- Raw value is the source of truth. The filtered value is the EMA or One Euro output.
-- ============================================
CREATE TABLE IF NOT EXISTS surgical_telemetry (
    id BIGSERIAL PRIMARY KEY,
    sample_uid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    run_key VARCHAR(255) NOT NULL,
    device_id INTEGER REFERENCES devices(id),
    channel VARCHAR(100) NOT NULL,
    source_timestamp TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_value DOUBLE PRECISION NOT NULL,
    filtered_value DOUBLE PRECISION,
    filter_name VARCHAR(50),
    filter_alpha DOUBLE PRECISION CHECK (filter_alpha IS NULL OR (filter_alpha > 0 AND filter_alpha <= 1)),
    unit VARCHAR(50) NOT NULL,
    CONSTRAINT surgical_telemetry_filter_pair CHECK ((filtered_value IS NULL) = (filter_name IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_surgical_telemetry_run ON surgical_telemetry(run_key, channel, id);

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE audit_log IS 'Append-only audit trail with pgcrypto SHA-256 hash chain (SRS FR-DAT-004, FR-DAT-005)';
COMMENT ON TABLE users IS 'User accounts with unique individual credentials (SRS FR-DAT-006)';
COMMENT ON TABLE patients IS 'Synthetic virtual patients, no PHI (SRS FR-MS-001)';
COMMENT ON TABLE devices IS 'Instrument and simulated peripheral registry (SRS FR-DAT-002)';
COMMENT ON TABLE device_metrics IS 'FHIR DeviceMetric resources (SRS FR-DAT-007)';
COMMENT ON TABLE simulation_runs IS 'Finalized simulation run records, written once (SRS FR-DAT-003)';
COMMENT ON TABLE simulation_states IS 'Serialized Pulse engine states, append-only (SRS FR-MS-006)';
COMMENT ON TABLE rta_switch_events IS 'RTA Simplex switch decisions and overrides (SRS FR-DAT-003)';
COMMENT ON TABLE sila2_rpc_log IS 'SiLA 2 remote procedure call records (SRS FR-DAT-002, FR-DAT-003)';
COMMENT ON TABLE observations IS 'FHIR R4 Observation resources (SRS FR-DAT-007)';
COMMENT ON TABLE surgical_telemetry IS 'Raw and filtered surgical telemetry samples (SRS FR-RTA-005)';
