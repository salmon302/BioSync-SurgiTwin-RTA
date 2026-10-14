# SPDX-License-Identifier: MIT
"""
SQLAlchemy ORM Models
Implements SRS FR-DAT-003 to FR-DAT-007 (ORM layer over database/migrations/002-schema.sql)

Origin: BioSync-Gateway middleware/models.py (adapted). The schema is owned by the SQL
migrations and Alembic. These models mirror it and never issue DDL. Tables that were
dropped from the Gateway (plates, dilution, scenarios, LLM, and similar) are not mapped.
"""

from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, Double, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func

from database import Base


class User(Base):
    """User accounts with unique individual credentials (SRS FR-DAT-006)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    scopes = Column(ARRAY(String), nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True))


class AuditLog(Base):
    """Hash-chained computer-generated audit trail (SRS FR-DAT-004, FR-DAT-005)."""
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_id = Column(String(255))
    action = Column(String(10), nullable=False)
    table_name = Column(String(255), nullable=False)
    record_id = Column(BigInteger, nullable=False)
    data_prev = Column(JSONB)
    data_new = Column(JSONB, nullable=False)
    reason = Column(Text)
    prev_hash = Column(String(64))
    current_hash = Column(String(64), nullable=False)


class Patient(Base):
    """Synthetic virtual patient, no PHI (SRS FR-MS-001)."""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    patient_uid = Column(String(36), unique=True, nullable=False)
    synthetic_id = Column(String(255), unique=True, nullable=False)
    demographics = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Device(Base):
    """Instrument and simulated peripheral registry (SRS FR-DAT-002)."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_identifier = Column(String(255), unique=True, nullable=False)
    device_name = Column(String(255), nullable=False)
    manufacturer = Column(String(255))
    model_number = Column(String(100))
    device_type = Column(String(100))
    fhir_resource = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DeviceMetric(Base):
    """FHIR DeviceMetric resources (SRS FR-DAT-007)."""
    __tablename__ = "device_metrics"

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    metric_name = Column(String(255), nullable=False)
    category = Column(String(50))
    operational_status = Column(String(50))
    unit = Column(String(50))
    measurement_period = Column(Double)
    fhir_resource = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Observation(Base):
    """FHIR R4 Observation resources with raw and filtered values (SRS FR-DAT-007, FR-3.5.3 pattern)."""
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True)
    observation_uid = Column(String(36), unique=True, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"))
    patient_id = Column(String(255))
    run_key = Column(String(255))
    observation_code = Column(String(100), nullable=False)
    value_quantity = Column(JSONB, nullable=False)
    unit = Column(String(50))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_data = Column(JSONB)
    filtered_data = Column(JSONB)
    fhir_resource = Column(JSONB, nullable=False)


class SimulationRun(Base):
    """Finalized simulation run record, written once (SRS FR-DAT-003)."""
    __tablename__ = "simulation_runs"

    id = Column(BigInteger, primary_key=True)
    run_uid = Column(String(36), unique=True, nullable=False)
    run_key = Column(String(255), unique=True, nullable=False)
    patient_id = Column(String(255))
    engine = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    seed = Column(JSONB)
    config = Column(JSONB)
    output_hashes = Column(JSONB)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recorded_by = Column(String(255))

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed', 'aborted')",
            name="simulation_runs_status_check",
        ),
    )


class SimulationState(Base):
    """Serialized Pulse engine state snapshot, append-only (SRS FR-MS-006)."""
    __tablename__ = "simulation_states"

    id = Column(BigInteger, primary_key=True)
    state_uid = Column(String(36), unique=True, nullable=False)
    run_key = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    engine_state = Column(JSONB, nullable=False)
    state_hash = Column(String(64), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RtaSwitchEvent(Base):
    """RTA Simplex switch decision or override (SRS FR-DAT-003, FR-RTA-001, FR-RTA-004)."""
    __tablename__ = "rta_switch_events"

    id = Column(BigInteger, primary_key=True)
    event_uid = Column(String(36), unique=True, nullable=False)
    run_key = Column(String(255), nullable=False)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type = Column(String(50), nullable=False)
    primary_source = Column(String(50), nullable=False)
    decision = Column(String(20), nullable=False)
    envelope_snapshot = Column(JSONB, nullable=False)
    operator_id = Column(String(255))
    reason = Column(Text)


class Sila2RpcLog(Base):
    """SiLA 2 remote procedure call record (SRS FR-DAT-002, FR-DAT-003)."""
    __tablename__ = "sila2_rpc_log"

    id = Column(BigInteger, primary_key=True)
    rpc_uid = Column(String(36), unique=True, nullable=False)
    run_key = Column(String(255))
    device_id = Column(Integer, ForeignKey("devices.id"))
    server_uid = Column(String(255), nullable=False)
    feature_identifier = Column(String(255), nullable=False)
    command_identifier = Column(String(255), nullable=False)
    request_payload = Column(JSONB)
    response_payload = Column(JSONB)
    grpc_status = Column(String(50), nullable=False)
    error_message = Column(Text)
    called_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    duration_ms = Column(Integer)


class SurgicalTelemetry(Base):
    """Raw and filtered surgical telemetry sample (SRS FR-RTA-005, FR-3.5.3 pattern)."""
    __tablename__ = "surgical_telemetry"

    id = Column(BigInteger, primary_key=True)
    sample_uid = Column(String(36), unique=True, nullable=False)
    run_key = Column(String(255), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"))
    channel = Column(String(100), nullable=False)
    source_timestamp = Column(DateTime(timezone=True))
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_value = Column(Double, nullable=False)
    filtered_value = Column(Double)
    filter_name = Column(String(50))
    filter_alpha = Column(Double)
    unit = Column(String(50), nullable=False)


class TelemetrySession(Base):
    """WebSocket telemetry relay session row, append-only (SRS FR-DAT-001, FR-DAT-003).

    Each session writes an 'open' row at connect and a 'finalized' row at disconnect.
    See database/migrations/006-telemetry-sessions.sql.
    """
    __tablename__ = "telemetry_sessions"

    id = Column(BigInteger, primary_key=True)
    session_uid = Column(String(36), nullable=False)
    record_status = Column(String(20), nullable=False)
    client_identity = Column(String(255), nullable=False)
    connected_at = Column(DateTime(timezone=True), nullable=False)
    disconnected_at = Column(DateTime(timezone=True))
    points_relayed = Column(BigInteger, nullable=False, default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "record_status IN ('open', 'finalized')",
            name="telemetry_sessions_record_status_check",
        ),
    )
