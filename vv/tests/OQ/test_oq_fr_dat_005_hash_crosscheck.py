# SPDX-License-Identifier: MIT
"""
OQ: Hash chain digest cross-check, Python engine versus pgcrypto (SRS FR-DAT-005)

Acceptance:
  * The Python digest for a fixed input matches the recorded test vector (runs without a database).
  * The SQL audit_chain_digest() returns the same digest as the Python engine for every JSON value
    type in JSON_VECTORS (requires BIOSYNC_TEST_DATABASE_URL).
  * VAL-015 injection suite (requires BIOSYNC_TEST_DATABASE_URL): tamper types are injected into
    audit_log chains of 5 and 200 rows at the first, middle, and last position. verify_hash_chain()
    must report the exact broken row ID in 100% of in-scope cases. The Python verifier must agree.
  * The nightly report in database/migrations/hash-chain-check.sql returns the same first broken row.

JSON values are passed to the digest as JsonText (the jsonb text), so exponent input and decimals
with more than 17 significant digits are exact. The verifier reads data_prev::text and
data_new::text, which keeps SQL NULL and JSON null distinct (findings F4 and F5). The full
value-type matrix and the Python float boundary are in test_oq_fr_dat_005_json_types.py.
"""

import json
import pathlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from engine.hash_chain import GENESIS_HASH, JsonText, compute_hash, compute_test_vector, verify_chain

PINNED_VECTOR_DIGEST = "609c640ee61ad85a8a522dc383127ca16458821b26563def228b2f70e6a73b21"
OCCURRED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

JSON_VECTORS = [
    ("json_null", "null"),
    ("json_true", "true"),
    ("json_false", "false"),
    ("int", "42"),
    ("int_negative", "-7"),
    ("int_beyond_double", "9007199254740993"),
    ("float", "98.6"),
    ("float_negative", "-0.5"),
    ("float_trailing_zero", "1.0"),
    ("float_zero", "0.0"),
    ("float_small_plain", "0.00001"),
    ("float_small_plain_long", "0.00000015"),
    ("string", '"abc"'),
    ("string_escapes", '"q\\"b\\\\s\\n\\t\\u0001 /"'),
    ("string_unicode", '"\\u00c5ngstr\\u00f6m \\u6e2c\\u8a66 \\ud83d\\ude00"'),
    ("object_empty", "{}"),
    ("array_empty", "[]"),
    ("nested", '{"b": [1, "x", null, true], "a": {"zz": 1, "y": 2}, "aaa": false}'),
    ("key_order", '{"bb": 1, "a": 2, "aaa": 3, "ab": 4, "\\u00e9": 5}'),
    ("float_exponent_input", "1e3"),
    ("float_more_than_17_digits", "3.14159265358979323846"),
]

CHAIN_SIZES = [5, 200]
POSITIONS = ["first", "middle", "last"]

FIELD_TAMPERS = {
    "data_new": ("UPDATE audit_log SET data_new = CAST(:v AS JSONB) WHERE id = :id", json.dumps({"tampered": True})),
    "data_prev": ("UPDATE audit_log SET data_prev = CAST(:v AS JSONB) WHERE id = :id", json.dumps({"tampered": True})),
    "actor_id": ("UPDATE audit_log SET actor_id = :v WHERE id = :id", "tampered-actor"),
    "occurred_at": ("UPDATE audit_log SET occurred_at = occurred_at + INTERVAL '1 microsecond' WHERE id = :id", None),
    "reason": ("UPDATE audit_log SET reason = :v WHERE id = :id", "tampered reason"),
    "prev_hash": ("UPDATE audit_log SET prev_hash = :v WHERE id = :id", "f" * 64),
    "current_hash": ("UPDATE audit_log SET current_hash = :v WHERE id = :id", "e" * 64),
}
SCENARIOS = list(FIELD_TAMPERS) + ["reorder_adjacent", "delete_interior"]

_RESULTS = []
_LIMIT_RESULTS = []


def _sql_digest(engine, raw_new):
    with engine.connect() as conn:
        conn.execute(text("SET TIME ZONE 'America/New_York'"))
        return conn.execute(
            text(
                "SELECT audit_chain_digest(:prev, :ts, :actor, NULL, CAST(:new AS JSONB), :reason)"
            ).bindparams(
                prev=GENESIS_HASH,
                ts=OCCURRED_AT,
                actor="vector_user",
                new=raw_new,
                reason="vector",
            )
        ).scalar()


def _as_json_text(entry):
    """Wrap jsonb text from the database. SQL NULL stays None; JSON null stays the text 'null'."""
    for key in ("data_prev", "data_new"):
        if entry[key] is not None:
            entry[key] = JsonText(entry[key])
    return entry


def _build_chain(session, count):
    ids = []
    for i in range(count):
        row_id = session.execute(
            text(
                "INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new, data_prev, reason) "
                "VALUES ('oq_fr_dat_005', 'INSERT', :rid, :actor, CAST(:dn AS JSONB), CAST(:dp AS JSONB), :reason) "
                "RETURNING id"
            ),
            {
                "rid": i,
                "actor": f"actor-{i}",
                "dn": json.dumps({"seq": i, "label": f"row-{i}", "flag": i % 2 == 0, "note": None, "vals": [i, 0.5]}),
                "dp": json.dumps({"before": i - 1}),
                "reason": f"injection chain row {i}",
            },
        ).scalar()
        ids.append(row_id)
    return ids


def _sql_verify(session):
    status, broken_id, _ = session.execute(text("SELECT * FROM verify_hash_chain()")).first()
    return status, broken_id


def _python_verify(session):
    rows = session.execute(
        text(
            "SELECT id, prev_hash, current_hash, occurred_at, actor_id, "
            "data_prev::text AS data_prev, data_new::text AS data_new, reason "
            "FROM audit_log ORDER BY id"
        )
    ).mappings().all()
    return verify_chain([_as_json_text(dict(row)) for row in rows])


def _disable_trigger(session, trigger_name):
    session.execute(text(f"ALTER TABLE audit_log DISABLE TRIGGER {trigger_name}"))


def _index(position, count):
    return {"first": 0, "middle": count // 2, "last": count - 1}[position]


def _apply_field_tamper(session, name, target_id):
    sql, value = FIELD_TAMPERS[name]
    _disable_trigger(session, "audit_log_prevent_update")
    params = {"id": target_id}
    if value is not None:
        params["v"] = value
    session.execute(text(sql).bindparams(**params))


def _swap_ids(session, first_id, second_id):
    _disable_trigger(session, "audit_log_prevent_update")
    scratch = max(first_id, second_id) + 1000000
    session.execute(text("UPDATE audit_log SET id = :s WHERE id = :a").bindparams(s=scratch, a=first_id))
    session.execute(text("UPDATE audit_log SET id = :a WHERE id = :b").bindparams(a=first_id, b=second_id))
    session.execute(text("UPDATE audit_log SET id = :b WHERE id = :s").bindparams(b=second_id, s=scratch))


def _delete_row(session, row_id):
    _disable_trigger(session, "audit_log_prevent_delete")
    session.execute(text("DELETE FROM audit_log WHERE id = :id").bindparams(id=row_id))


def _apply_scenario(session, scenario, ids, position):
    """Inject one tamper and return the row ID the verifier must report."""
    index = _index(position, len(ids))
    if scenario in FIELD_TAMPERS:
        _apply_field_tamper(session, scenario, ids[index])
        return ids[index]
    if scenario == "reorder_adjacent":
        k = min(index, len(ids) - 2)
        _swap_ids(session, ids[k], ids[k + 1])
        return ids[k]
    if scenario == "delete_interior":
        k = min(index, len(ids) - 2)
        _delete_row(session, ids[k])
        return ids[k + 1]
    raise ValueError(f"unknown scenario {scenario}")


@pytest.mark.oq
def test_python_digest_matches_recorded_vector():
    vector = compute_test_vector()
    assert vector["expected_hash"] == PINNED_VECTOR_DIGEST


@pytest.mark.oq
def test_python_digest_is_stable_across_calls():
    vector = compute_test_vector()
    again = compute_test_vector()
    assert vector["expected_hash"] == again["expected_hash"]


@pytest.mark.oq
@pytest.mark.db
def test_sql_digest_matches_python_digest(db_engine):
    occurred_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    python_digest = compute_hash(
        previous_hash=GENESIS_HASH,
        occurred_at=occurred_at,
        actor_id="test_user",
        data_new={"field": "value"},
        data_prev=None,
        reason="initial creation",
    )
    with db_engine.connect() as conn:
        conn.execute(text("SET TIME ZONE 'America/New_York'"))
        sql_digest = conn.execute(
            text(
                "SELECT audit_chain_digest(:prev, :ts, :actor, NULL, CAST(:new AS JSONB), :reason)"
            ).bindparams(
                prev=GENESIS_HASH,
                ts=occurred_at,
                actor="test_user",
                new='{"field": "value"}',
                reason="initial creation",
            )
        ).scalar()
    assert sql_digest == python_digest
    assert sql_digest == PINNED_VECTOR_DIGEST


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize("name, raw", JSON_VECTORS, ids=[name for name, _ in JSON_VECTORS])
def test_sql_digest_matches_python_for_json_vector(db_engine, name, raw):
    expected = compute_hash(GENESIS_HASH, OCCURRED_AT, "vector_user", JsonText(raw), None, "vector")
    assert _sql_digest(db_engine, raw) == expected


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize("count", CHAIN_SIZES)
@pytest.mark.parametrize("position", POSITIONS)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_injection_reports_exact_broken_row(db_session, scenario, position, count):
    ids = _build_chain(db_session, count)
    assert _sql_verify(db_session) == ("ok", None)
    assert _python_verify(db_session) == (True, None)

    expected = _apply_scenario(db_session, scenario, ids, position)
    status, reported = _sql_verify(db_session)
    py_valid, py_reported = _python_verify(db_session)

    _RESULTS.append({
        "scenario": scenario,
        "rows": count,
        "position": position,
        "expected": expected,
        "detected": status == "broken",
        "reported_ok": reported == expected,
        "python_ok": (not py_valid) and py_reported == expected,
    })
    assert status == "broken", f"{scenario} at {position} ({count} rows) was not detected"
    assert reported == expected, f"{scenario} at {position} ({count} rows): expected {expected}, got {reported}"
    assert (not py_valid) and py_reported == expected


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize("count", CHAIN_SIZES)
def test_tail_deletion_boundary_is_not_detected_by_chain_alone(db_session, count):
    """Deleting the last row leaves a valid prefix. The chain cannot detect it without an external anchor."""
    ids = _build_chain(db_session, count)
    _delete_row(db_session, ids[-1])
    status, reported = _sql_verify(db_session)
    py_valid, _ = _python_verify(db_session)

    _LIMIT_RESULTS.append({"rows": count, "status": status, "python_valid": py_valid})
    assert status == "ok" and reported is None
    assert py_valid


NIGHTLY_REPORT = pathlib.Path(__file__).resolve().parents[3] / "database" / "migrations" / "hash-chain-check.sql"


def _nightly_report_statement():
    script = NIGHTLY_REPORT.read_text(encoding="utf-8")
    for chunk in script.split(";"):
        if "Hash Chain Verification Report" in chunk:
            return chunk
    raise AssertionError("report statement not found in hash-chain-check.sql")


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize("count", CHAIN_SIZES)
def test_nightly_report_is_ok_on_valid_chain(db_session, count):
    _build_chain(db_session, count)
    report = db_session.connection().exec_driver_sql(_nightly_report_statement()).mappings().first()
    assert report["integrity_status"] == "OK"
    assert report["total_entries"] == count


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize("count", CHAIN_SIZES)
@pytest.mark.parametrize("scenario", ["data_new", "reorder_adjacent", "delete_interior"])
def test_nightly_report_recomputes_and_reports_first_broken_row(db_session, scenario, count):
    ids = _build_chain(db_session, count)
    expected = _apply_scenario(db_session, scenario, ids, "middle")
    report = db_session.connection().exec_driver_sql(_nightly_report_statement()).mappings().first()
    assert report["integrity_status"] == "BROKEN"
    assert report["first_broken_id"] == expected


@pytest.mark.oq
def test_injection_suite_summary(capsys):
    if not _RESULTS:
        pytest.skip("injection suite did not run in this session")

    lines = [
        "",
        "VAL-015 injection suite (FR-DAT-005): audit_log chains, verify_hash_chain() and verify_chain()",
        "| Tamper type | Rows | Cases | Detected | Reported row correct | Python agrees |",
        "|:------------|-----:|------:|---------:|---------------------:|--------------:|",
    ]
    totals = {"cases": 0, "detected": 0, "reported_ok": 0, "python_ok": 0}
    for scenario in SCENARIOS:
        for count in CHAIN_SIZES:
            group = [r for r in _RESULTS if r["scenario"] == scenario and r["rows"] == count]
            if not group:
                continue
            detected = sum(r["detected"] for r in group)
            reported = sum(r["reported_ok"] for r in group)
            agrees = sum(r["python_ok"] for r in group)
            totals["cases"] += len(group)
            totals["detected"] += detected
            totals["reported_ok"] += reported
            totals["python_ok"] += agrees
            lines.append(f"| {scenario} | {count} | {len(group)} | {detected} | {reported} | {agrees} |")
    lines.append(
        f"| TOTAL | | {totals['cases']} | {totals['detected']} | {totals['reported_ok']} | {totals['python_ok']} |"
    )
    lines.append("")
    lines.append("Documented boundary (not in the injection total): tail deletion")
    lines.append("| Tamper type | Rows | Chain status | Python valid |")
    lines.append("|:------------|-----:|:-------------|:-------------|")
    for result in _LIMIT_RESULTS:
        lines.append(f"| tail_delete | {result['rows']} | {result['status']} | {result['python_valid']} |")
    lines.append("")

    with capsys.disabled():
        print("\n".join(lines))

    assert totals["cases"] == len(SCENARIOS) * len(CHAIN_SIZES) * len(POSITIONS)
    assert totals["detected"] == totals["cases"], "injected tamper was not detected in every case"
    assert totals["reported_ok"] == totals["cases"], "verifier did not report the injected row in every case"
    assert totals["python_ok"] == totals["cases"], "Python verifier disagreed with the injected row"
