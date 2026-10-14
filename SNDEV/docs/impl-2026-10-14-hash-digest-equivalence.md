Title: Python and SQL hash digest equivalence across JSON value types
Date: 2026-10-14T16:46:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 task 1.10 (closes F4, F5)
Summary: Defines the canonical jsonb text rules for the FR-DAT-005 digest, makes the Python verifier match audit_chain_digest() byte for byte for every JSON value type, and records the equivalence matrix.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1, task 1.10 (prove Python and SQL digest equivalence for every JSON value type in the pgcrypto SHA-256 hash chain). Closes findings F4 and F5 in `SNDEV/docs/impl-2026-10-13-pg15-qualification.md`. Gate G1.3 (hash chain).

## Specification Summary

* The chain digest is H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i), computed by `audit_chain_digest()` in `database/migrations/003-triggers.sql`.
* The SQL side renders D_prev and D_new with `::TEXT` (jsonb output). A SQL NULL D_prev renders as `{}` through `COALESCE`.
* The Python verifier in `middleware/engine/hash_chain.py` must produce the same bytes for every JSON value type before hashing.
* F4: a JSON `null` in `data_prev` verifies in SQL and fails in Python, because psycopg2 decodes both SQL NULL and JSON null to `None`.
* F5: JSON numbers in exponent notation and decimals with more than 17 significant digits do not round-trip through psycopg2 floats.

## Implementation Notes

### Canonicalization rules (PostgreSQL 15.19 observed output)

The digest input is the jsonb text of each document. The rules below were checked against CAST(raw AS JSONB)::TEXT on PostgreSQL 15.19 (probe run recorded in SNDEV/logs/hash-digest-probe-2026-10-14.txt).

* Object keys are sorted by byte length, then by bytes. Separators are ", " and ": ". Duplicate keys keep the last value.
* Arrays use ", " separators. The empty object is "{}" and the empty array is "[]".
* JSON null, true, and false render as null, true, and false.
* Numbers are numeric values with the input scale. Exponent form is expanded to plain decimal notation: 1e3 gives 1000, 1.50e1 gives 15.0, 1.5e-07 gives 0.00000015, 1.0E+22 gives 10000000000000000000000.
* Digits beyond float precision are kept: 3.14159265358979323846 gives 3.14159265358979323846, and 0.10 gives 0.10.
* Negative zero loses its sign and keeps its scale: -0 gives 0, -0.0 gives 0.0, -0e-3 gives 0.000.
* Strings escape only the quote, the backslash, and control characters below 0x20. Control characters use \b, \f, \n, \r, \t, or \u00xx in lowercase hex. The slash, DEL (0x7f), U+2028, and non-ASCII characters are written as raw UTF-8.
* Input that PostgreSQL rejects is rejected by the Python canonicalizer too: \u0000 (NUL), lone surrogates, NaN, and Infinity.
* SQL NULL in data_prev renders as "{}" through COALESCE in udit_chain_digest(). JSON null in data_prev renders as "null". Both are distinct values, so the Python verifier must receive SQL NULL and JSON null as different inputs.

### Root causes

* F4: psycopg2 decodes both SQL NULL and JSON null to None. The verifier passed None on and compute_hash rendered it as "{}".
* F5: psycopg2 decodes jsonb numbers with json.loads default, which makes float. Exponent form, trailing zeros, and digits beyond float precision are lost before rendering.

### Design

* JsonText (str subclass in middleware/engine/hash_chain.py) marks a value as JSON document text. _jsonb_text() parses it with Decimal for numbers, so each number keeps its digits and scale, then renders by the rules above.
* The verifier path reads data_prev::text and data_new::text from the database and wraps non-NULL values in JsonText. SQL NULL stays None and renders as "{}".
* Python float and dict inputs keep the shortest-repr rendering. Those inputs are an enumerated boundary (see Verification).

### Canonicalization in code

* `middleware/engine/hash_chain.py`: `JsonText` marks JSON text. `_jsonb_text()` parses it with `parse_float=Decimal`, `parse_int=Decimal`, and a `parse_constant` that rejects NaN and Infinity. Strings with NUL or a lone surrogate raise ValueError. Numbers render with `format(value, "f")`, and zero drops its sign.
* Python float values use `Decimal(repr(value))` and the same number rule. Python dict keys are sorted by UTF-8 byte length, then by bytes.
* `_jsonb_text()`, `_utc_text()`, `compute_hash()`, and `verify_chain()` keep their names and signatures. `middleware/tests/test_hash_chain.py` imports `_jsonb_text` and `_utc_text` and passes unchanged.

## Verification

### Equivalence matrix

Source: `vv/tests/OQ/test_oq_fr_dat_005_json_types.py`, the test `test_value_type_matrix_summary`. Each vector is checked in the data_new position (D_prev NULL) and the data_prev position (D_new `{"n": 1}`). The decoded column checks the Python value from `json.loads` against the same SQL digest.

| Value type | Cases | data_new equal | data_prev equal | Decoded Python value equal |
|:-----------|------:|---------------:|----------------:|---------------------------:|
| null (top level) | 1 | 1 | 1 | 1 |
| boolean (true, false) | 2 | 2 | 2 | 2 |
| object (empty, nested, null members, key order, duplicate keys, whitespace) | 7 | 7 | 7 | 7 |
| array (empty, nested empties, arrays of objects, object of arrays) | 4 | 4 | 4 | 4 |
| integer (zero, negative zero, int4 and int8 limits, beyond int8, 30 digits, 5000 digits) | 12 | 12 | 12 | 11 |
| number (plain, integral, trailing zeros, exponent forms, very small, very large, more than 17 digits) | 27 | 27 | 27 | 15 |
| string (empty, escapes, controls, DEL, solidus, BMP, non-BMP, raw non-ASCII, timestamp-like, numeric text, lookalike null and object) | 21 | 21 | 21 | 21 |
| nested (10 levels of object, 10 levels of array, numbers in containers) | 3 | 3 | 3 | 2 |
| TOTAL | 77 | 77 | 77 | 63 |

* Claimed equivalent through JsonText: 77 of 77 in the data_new position, 77 of 77 in the data_prev position.
* SQL NULL data_prev renders as "{}" and JSON null renders as "null". The two digests differ, and both match Python (`test_sql_null_and_json_null_in_data_prev_are_distinct`).
* Rejected by both PostgreSQL and the Python engine: 4 cases (`"\u0000"`, `"\ud800"`, `NaN`, `Infinity`).
* Chain-level check: 156 rows were inserted through the `audit_log_hash_chain` trigger. They are the 77 vectors as data_prev, the 77 vectors as data_new, a SQL NULL data_prev, and a JSON null data_prev. `verify_hash_chain()` returns ok, and `verify_chain()` over `data_prev::text` and `data_new::text` returns (True, None).

### Decoded-value boundary (exact set, asserted)

A Python value decoded by `json.loads` is not equivalent for these 14 vectors. The test `test_decoded_python_values_boundary` asserts this set exactly. The verifier does not use decoded values, so these cases do not affect the chain check.

* integer-digits_5000: Python `json.loads` rejects an integer over 4300 digits (int string limit).
* nested-numbers_in_containers: contains `0.10` and `1e3`.
* number-exponent_integral (`1e3`), number-exponent_integral_upper (`1E3`), number-exponent_positive_sign (`1e+2`), number-exponent_scale_1_0e2 (`1.0e2`): the float renders with a trailing `.0` or loses the exponent-form scale.
* number-zero_with_exponent (`0e5`), number-negative_zero_with_exponent (`-0e-3`): the float zero loses the scale.
* number-exponent_underflow_scale (`1e-400`), number-exponent_very_small (`1.23456789012345678901234567890e-30`): the float underflows or loses digits.
* number-more_than_17_digits (`3.14159265358979323846`), number-more_than_17_digits_near_one (`2.5000000000000000000000001`): the float loses digits.
* number-integral_20_zeros (`1.0000000000000000000000`), number-scale_kept_100_00 (`100.00`): the float loses trailing zeros.

### Crosscheck file

* `KNOWN_LIMIT_VECTORS` and the strict xfail test are removed. `float_exponent_input` (`1e3`) and `float_more_than_17_digits` (`3.14159265358979323846`) are in `JSON_VECTORS`, and they pass through JsonText.
* `_python_verify()` selects `data_prev::text` and `data_new::text`, and wraps non-NULL values in JsonText. The 54-case VAL-015 injection suite still reports 54 of 54 detected, reported, and Python-agreeing cases.

### Run results

Interpreter: `.venv-qual311` (Python 3.11.9). Database: `surgitwin_test` on PostgreSQL 15.19 at 127.0.0.1:5432. The database is not dropped. Each DB test runs in a rolled-back transaction.

| Run | Command | Result | Capture |
|:----|:--------|:-------|:--------|
| Two hash files | `pytest vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py vv/tests/OQ/test_oq_fr_dat_005_json_types.py -q` | 251 passed | `SNDEV/logs/hash-digest-equivalence-run-2026-10-14.log` |
| Full suite | `pytest middleware/tests vv/tests -q` | 492 passed, 8 skipped, 3 xfailed | `SNDEV/logs/hash-digest-equivalence-full-suite-2026-10-14.log` |
| Baseline at HEAD | same command on `git archive HEAD`, same interpreter and database | 328 passed, 8 skipped, 5 xfailed | not saved (temporary export, removed) |

* The 333 baseline in the task is 328 passed plus 5 xfailed on the measured HEAD tree.
* Change: +162 passing cases in the new JSON types file, +2 converted xfails. The xfail count drops from 5 to 3. The 3 remaining xfails are the Gateway R2 TLS items in `middleware/tests/test_db_ssl_config.py`, which are out of scope.
* The 8 skips are unchanged: 2 Pulse engine tests (no `pulse` module), 5 relay PostgreSQL tests (no `BIOSYNC_RELAY_ADMIN_URL`), and PQ-3 (no `BIOSYNC_PQ3_DATABASE_URL`).
* The repository has no lint or type configuration (no pyproject, setup.cfg, ruff, or mypy files), so the pytest suite is the quality gate. The owned files contain no banned words, no em or en dashes, and no curly quotes.
* PostgreSQL probe capture: `SNDEV/logs/hash-digest-probe-2026-10-14.txt`.

### Findings disposition

* F4 (CLOSED in the verifier): psycopg2 decoded SQL NULL and JSON null to None. The verifier now reads `data_prev::text`, so SQL NULL stays None and JSON null is "null". Evidence: the chain-level test and the distinct-digest test above. The write-time guard in the API layer is not required for chain verification. It remains an option for the owner of `middleware/api`.
* F5 (CLOSED for JSON text input, boundary enumerated for decoded values): exponent input and more than 17 significant digits are exact when the JSON text reaches the digest, because SQL receives the text through CAST and Python receives it through JsonText. The 14 decoded-value cases above are the enumerated boundary. The same float path also drops trailing zeros (`0.10`, `100.00`), which is a wider form of F5.

### Open items for other owners

* `SNDEV/docs/impl-2026-10-13-pg15-qualification.md` still lists F4 and F5 as OPEN. Its owner should record the closure with a reference to this log.
* Any caller in `middleware/` that passes psycopg2-decoded values to `verify_chain()` is on the enumerated boundary. The owner of that caller should select `data_prev::text` and `data_new::text` and wrap them in JsonText. No such caller was found in the repository. The unit tests and the PQ chain test pass Python values, and `middleware/api/routes/audit.py` uses the SQL verifier.
* SQL NULL in data_new is not reachable because the column is NOT NULL. The COALESCE branch in `audit_chain_digest()` for data_new is therefore not part of the equivalence rule.
