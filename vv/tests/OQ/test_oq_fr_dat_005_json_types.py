# SPDX-License-Identifier: MIT
"""
OQ: Python and SQL digest equivalence for every JSON value type (SRS FR-DAT-005, task 1.10).

Acceptance:
  * For every case in VALUE_VECTORS, audit_chain_digest() and the Python engine produce the same
    SHA-256 digest with the JSON text in the data_prev position and in the data_new position.
    SQL NULL data_prev is included as its own case (rendered as "{}").
  * Every case in REJECTED_VECTORS is rejected by PostgreSQL jsonb and by the Python canonicalizer.
  * Rows written through the audit_log trigger verify in SQL (verify_hash_chain()) and in Python
    (verify_chain() over data_prev::text and data_new::text), including JSON null and SQL NULL.
  * Boundary: a Python value that was decoded from JSON text by json.loads (float for numbers)
    diverges from the SQL digest for the cases in DECODED_BOUNDARY. The test asserts that exact set.
    The digest path for verification uses JsonText, so these values are equivalent there.

Requires BIOSYNC_TEST_DATABASE_URL. The rule and the rendering table are in
SNDEV/docs/impl-2026-10-14-hash-digest-equivalence.md.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from engine.hash_chain import GENESIS_HASH, JsonText, compute_hash, verify_chain

OCCURRED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
FIXED_NEW = '{"n": 1}'


def _nested_object(levels):
    value = 1
    for depth in range(levels):
        value = {f"k{depth}": value, "n": depth}
    return json.dumps(value)


def _nested_array(levels):
    value = "leaf"
    for _ in range(levels):
        value = [value, {"x": None}]
    return json.dumps(value)


VALUE_VECTORS = [
    ("null", "top_level", "null"),
    ("boolean", "true", "true"),
    ("boolean", "false", "false"),
    ("object", "empty", "{}"),
    ("object", "nested_mixed", '{"b": [1, "x", null, true], "a": {"zz": 1, "y": 2}, "aaa": false}'),
    ("object", "null_members", '{"n": null, "e": {}, "a": []}'),
    ("object", "key_order_by_byte_length", '{"bb": 1, "a": 2, "aaa": 3, "ab": 4}'),
    ("object", "key_order_multibyte", '{"\\u00e9t\\u00e9": 1, "zz": 2, "\\u6e2c": 3}'),
    ("object", "duplicate_key_keeps_last", '{"a": 1, "a": 2}'),
    ("object", "insignificant_whitespace", ' { "a" : [ 1 , 2 ] } '),
    ("array", "empty", "[]"),
    ("array", "nested_empties", "[[], {}, [null]]"),
    ("array", "of_objects", '[{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": []}]'),
    ("array", "object_of_arrays", '{"rows": [[1, 2], [3, {"deep": null}]], "meta": {}}'),
    ("integer", "zero", "0"),
    ("integer", "negative_zero", "-0"),
    ("integer", "small", "42"),
    ("integer", "negative", "-7"),
    ("integer", "int4_max", "2147483647"),
    ("integer", "beyond_int4", "2147483648"),
    ("integer", "int8_max", "9223372036854775807"),
    ("integer", "beyond_int8", "9223372036854775808"),
    ("integer", "negative_beyond_int8", "-9223372036854775809"),
    ("integer", "beyond_double", "9007199254740993"),
    ("integer", "digits_30", "123456789012345678901234567890"),
    ("integer", "digits_5000", "7" * 5000),
    ("number", "plain_0_1", "0.1"),
    ("number", "plain_98_6", "98.6"),
    ("number", "negative_fraction", "-0.5"),
    ("number", "integral_1_0", "1.0"),
    ("number", "integral_20_zeros", "1.0000000000000000000000"),
    ("number", "scale_kept_100_00", "100.00"),
    ("number", "zero_point_zero", "0.0"),
    ("number", "negative_zero_point_zero", "-0.0"),
    ("number", "small_plain", "0.00001"),
    ("number", "small_plain_long", "0.00000015"),
    ("number", "exponent_1_5e_07", "1.5e-07"),
    ("number", "exponent_1_5e_7", "1.5e-7"),
    ("number", "exponent_negative_fraction", "-1.5e-7"),
    ("number", "exponent_very_small", "1.23456789012345678901234567890e-30"),
    ("number", "exponent_underflow_scale", "1e-400"),
    ("number", "exponent_integral", "1e3"),
    ("number", "exponent_integral_upper", "1E3"),
    ("number", "exponent_scale_1_0e2", "1.0e2"),
    ("number", "exponent_scale_1_50e1", "1.50e1"),
    ("number", "exponent_positive_sign", "1e+2"),
    ("number", "exponent_large", "1.0E+22"),
    ("number", "exponent_max_double", "1.7976931348623157e308"),
    ("number", "exponent_half", "5e-1"),
    ("number", "zero_with_exponent", "0e5"),
    ("number", "negative_zero_with_exponent", "-0e-3"),
    ("number", "more_than_17_digits", "3.14159265358979323846"),
    ("number", "more_than_17_digits_near_one", "2.5000000000000000000000001"),
    ("string", "empty", '""'),
    ("string", "ascii", '"abc"'),
    ("string", "spaces", '"two words"'),
    ("string", "embedded_quotes", r'"say \"hi\""'),
    ("string", "backslash", r'"a\\b"'),
    ("string", "newline", r'"line\nfeed"'),
    ("string", "tab_and_cr", r'"a\tb\rc"'),
    ("string", "controls_u0001_u001f", r'"\u0001\u001f"'),
    ("string", "backspace_formfeed", r'"\b\f"'),
    ("string", "del_u007f", r'"\u007f"'),
    ("string", "solidus_escape", r'"\/"'),
    ("string", "bmp_escapes", r'"\u00c5ngstr\u00f6m \u6e2c\u8a66"'),
    ("string", "non_bmp_escape", r'"\ud83d\ude00"'),
    ("string", "non_bmp_raw", '"\U0001F600 \u2028"'),
    ("string", "raw_non_ascii", '"\u00c5ngstr\u00f6m"'),
    ("string", "timestamp_like", '"2026-10-14T16:46:00.123456Z"'),
    ("string", "numeric_digits", '"42"'),
    ("string", "numeric_exponent_text", '"1.5e-07"'),
    ("string", "numeric_trailing_zero_text", '"0.10"'),
    ("string", "lookalike_null", '"null"'),
    ("string", "lookalike_object", '"{}"'),
    ("nested", "ten_levels_object", _nested_object(10)),
    ("nested", "ten_levels_array", _nested_array(10)),
    ("nested", "numbers_in_containers", '{"a": [1.5e-07, 0.10, 1e3], "b": {"c": -0.0, "d": 7}}'),
]

REJECTED_VECTORS = [
    ("string_nul_escape", r'"\u0000"'),
    ("string_lone_high_surrogate", r'"\ud800"'),
    ("constant_nan", "NaN"),
    ("constant_infinity", "Infinity"),
]

# Python values decoded from JSON text by json.loads (float for numbers, int limit for integers).
# These cases are not equivalent when the decoded value is passed to compute_hash(). They are
# equivalent when the JSON text is passed as JsonText, which is what the verifier does.
DECODED_BOUNDARY = {
    "number-exponent_integral",
    "number-exponent_integral_upper",
    "number-exponent_scale_1_0e2",
    "number-exponent_positive_sign",
    "number-zero_with_exponent",
    "number-negative_zero_with_exponent",
    "number-exponent_very_small",
    "number-exponent_underflow_scale",
    "number-more_than_17_digits",
    "number-more_than_17_digits_near_one",
    "number-integral_20_zeros",
    "number-scale_kept_100_00",
    "integer-digits_5000",
    "nested-numbers_in_containers",
}

CHAIN_ROWS = [
    (f"{category}-{name}", "data_prev", raw, FIXED_NEW) for category, name, raw in VALUE_VECTORS
] + [
    (f"{category}-{name}", "data_new", None, raw) for category, name, raw in VALUE_VECTORS
] + [
    ("null-sql_null_data_prev", "data_prev", None, "null"),
    ("null-json_null_data_prev", "data_prev", "null", "null"),
]

_MATRIX = {}


def _vector_id(category, name):
    return f"{category}-{name}"


def _sql_digest(engine, prev_raw, new_raw):
    with engine.connect() as conn:
        conn.execute(text("SET TIME ZONE 'America/New_York'"))
        return conn.execute(
            text(
                "SELECT audit_chain_digest(:prev, :ts, :actor, CAST(:dp AS JSONB), CAST(:dn AS JSONB), :reason)"
            ).bindparams(
                prev=GENESIS_HASH,
                ts=OCCURRED_AT,
                actor="vector_user",
                dp=prev_raw,
                dn=new_raw,
                reason="vector",
            )
        ).scalar()


def _python_digest(prev_json, new_json):
    return compute_hash(
        GENESIS_HASH,
        OCCURRED_AT,
        "vector_user",
        JsonText(new_json) if new_json is not None else None,
        JsonText(prev_json) if prev_json is not None else None,
        "vector",
    )


def _record(category, name, key, value):
    _MATRIX.setdefault(_vector_id(category, name), {"category": category})[key] = value


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize(
    "category, name, raw",
    VALUE_VECTORS,
    ids=[_vector_id(category, name) for category, name, _ in VALUE_VECTORS],
)
def test_digest_equivalence_in_data_new_position(db_engine, category, name, raw):
    sql = _sql_digest(db_engine, None, raw)
    python = compute_hash(GENESIS_HASH, OCCURRED_AT, "vector_user", JsonText(raw), None, "vector")
    _record(category, name, "data_new", sql == python)
    assert sql == python


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize(
    "category, name, raw",
    VALUE_VECTORS,
    ids=[_vector_id(category, name) for category, name, _ in VALUE_VECTORS],
)
def test_digest_equivalence_in_data_prev_position(db_engine, category, name, raw):
    sql = _sql_digest(db_engine, raw, FIXED_NEW)
    python = _python_digest(raw, FIXED_NEW)
    _record(category, name, "data_prev", sql == python)
    assert sql == python


@pytest.mark.oq
@pytest.mark.db
def test_sql_null_and_json_null_in_data_prev_are_distinct(db_engine):
    sql_null = _sql_digest(db_engine, None, FIXED_NEW)
    json_null = _sql_digest(db_engine, "null", FIXED_NEW)
    assert sql_null == _python_digest(None, FIXED_NEW)
    assert json_null == _python_digest("null", FIXED_NEW)
    assert sql_null != json_null


@pytest.mark.oq
@pytest.mark.db
@pytest.mark.parametrize("name, raw", REJECTED_VECTORS, ids=[name for name, _ in REJECTED_VECTORS])
def test_invalid_json_text_is_rejected_by_both(db_engine, name, raw):
    with pytest.raises(DBAPIError):
        _sql_digest(db_engine, None, raw)
    with pytest.raises(ValueError):
        compute_hash(GENESIS_HASH, OCCURRED_AT, "vector_user", JsonText(raw), None, "vector")


@pytest.mark.oq
@pytest.mark.db
def test_decoded_python_values_boundary(db_engine):
    """Assert the exact set of vectors whose decoded Python value does not match SQL."""
    diverged = set()
    for category, name, raw in VALUE_VECTORS:
        vector_id = _vector_id(category, name)
        sql = _sql_digest(db_engine, None, raw)
        try:
            decoded = compute_hash(GENESIS_HASH, OCCURRED_AT, "vector_user", json.loads(raw), None, "vector")
        except ValueError:
            decoded = None
        _record(category, name, "decoded", decoded == sql)
        if decoded != sql:
            diverged.add(vector_id)
    assert diverged == DECODED_BOUNDARY


@pytest.mark.oq
@pytest.mark.db
def test_chain_rows_verify_in_sql_and_python(db_session):
    status, broken_id, _ = db_session.execute(text("SELECT * FROM verify_hash_chain()")).first()
    assert (status, broken_id) == ("ok", None)

    for label, position, prev_raw, new_raw in CHAIN_ROWS:
        db_session.execute(
            text(
                "INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new, data_prev, reason) "
                "VALUES ('oq_fr_dat_005_types', 'INSERT', 0, :actor, CAST(:dn AS JSONB), CAST(:dp AS JSONB), :reason)"
            ).bindparams(actor=label, dn=new_raw, dp=prev_raw, reason=position)
        )

    status, broken_id, _ = db_session.execute(text("SELECT * FROM verify_hash_chain()")).first()
    assert (status, broken_id) == ("ok", None)

    rows = db_session.execute(
        text(
            "SELECT id, prev_hash, current_hash, occurred_at, actor_id, "
            "data_prev::text AS data_prev, data_new::text AS data_new, reason "
            "FROM audit_log ORDER BY id"
        )
    ).mappings().all()
    entries = []
    for row in rows:
        entry = dict(row)
        for key in ("data_prev", "data_new"):
            if entry[key] is not None:
                entry[key] = JsonText(entry[key])
        entries.append(entry)
    assert verify_chain(entries) == (True, None)


@pytest.mark.oq
def test_value_type_matrix_summary(capsys):
    if not _MATRIX:
        pytest.skip("value-type matrix did not run in this session")

    totals = {"cases": 0, "data_new": 0, "data_prev": 0, "decoded": 0}
    rows = []
    categories = []
    for category, _, _ in VALUE_VECTORS:
        if category not in categories:
            categories.append(category)
    for category in categories:
        group = [entry for entry in _MATRIX.values() if entry["category"] == category]
        new_ok = sum(bool(entry.get("data_new")) for entry in group)
        prev_ok = sum(bool(entry.get("data_prev")) for entry in group)
        decoded_ok = sum(bool(entry.get("decoded")) for entry in group)
        totals["cases"] += len(group)
        totals["data_new"] += new_ok
        totals["data_prev"] += prev_ok
        totals["decoded"] += decoded_ok
        rows.append(f"| {category} | {len(group)} | {new_ok} | {prev_ok} | {decoded_ok} |")

    lines = [
        "",
        "FR-DAT-005 value-type equivalence matrix (Python engine versus audit_chain_digest())",
        "| Value type | Cases | data_new equal | data_prev equal | Decoded Python value equal |",
        "|:-----------|------:|---------------:|----------------:|---------------------------:|",
        *rows,
        f"| TOTAL | {totals['cases']} | {totals['data_new']} | {totals['data_prev']} | {totals['decoded']} |",
        "",
        f"Rejected by both PostgreSQL and the Python engine: {len(REJECTED_VECTORS)} cases",
        "Decoded-value boundary (Python float or int limit; equal only through JsonText):",
    ]
    lines += [f"  * {vector_id}" for vector_id in sorted(DECODED_BOUNDARY)]
    lines.append("")

    with capsys.disabled():
        print("\n".join(lines))

    assert totals["data_new"] == len(VALUE_VECTORS)
    assert totals["data_prev"] == len(VALUE_VECTORS)
