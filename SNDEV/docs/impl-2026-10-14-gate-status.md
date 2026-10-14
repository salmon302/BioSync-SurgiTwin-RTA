Title: Phase 1 gate status and estimate updates
Date: 2026-10-14T17:15:48Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 gate tracking after commits a44c163, f4b9d8f, 4d2a372, 94fc8d1
Summary: Records the status of gates G1.1 to G1.8, marks task 1.10 done, and recomputes the Phase 1 estimate from the task rows.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1, Verification Gates table and task table. Migration map known-debt tables in `docs/migration-map.md`. Evidence logs: `SNDEV/docs/impl-2026-10-14-r2-tls.md` (G1.7), `SNDEV/docs/impl-2026-10-14-audit-capture-roles.md` (G1.2, G1.4), and `SNDEV/docs/impl-2026-10-14-hash-digest-equivalence.md` (G1.3, task 1.10).

## Specification Summary

* Add a Status column to the Phase 1 Verification Gates table, with one status per gate G1.1 to G1.8.
* Mark task 1.10 done at commit `4d2a372` and recompute the Phase 1 estimate from the task rows.
* Add one status sentence to the Phase 1 status paragraph that covers commits `a44c163`, `f4b9d8f`, and `94fc8d1`.
* Mark the FR-DAT-005 digest-equivalence debt CLOSED with its boundary note. Mark the Gateway R2 TLS debt CLOSED at `a44c163`.
* Add known-debt rows for the four items the latest streams raised and did not close.

## Implementation Notes

### Files changed

* `DEVELOPMENT_PLAN.md`: Phase 1 status paragraph, Estimate line, task 1.10 row, Verification Gates table (Status column added).
* `docs/migration-map.md`: Table 3 rows for the digest equivalence item (CLOSED) and the Gateway R2 item (CLOSED). Table 4 rows added for the four open items.
* `SNDEV/docs/impl-2026-10-14-gate-status.md`: this log (new).

### Gate status after this change

| Gate | Status | Commit | Evidence |
|:-----|:-------|:-------|:---------|
| G1.1 Append-only store | PASS | `ffcf167` | `SNDEV/docs/impl-2026-10-13-pg15-qualification.md` (PostgreSQL 15.19, 10 WORM tables) |
| G1.2 Audit capture | PASS | `f4b9d8f` | `SNDEV/docs/impl-2026-10-14-audit-capture-roles.md` (14 of 14 exercised changes) |
| G1.3 Hash chain | PASS with recorded boundaries | `4d2a372` | `SNDEV/docs/impl-2026-10-14-hash-digest-equivalence.md` (77 of 77 vectors, 54 of 54 tamper cases) |
| G1.4 Credentials | PASS | `f4b9d8f` | `SNDEV/docs/impl-2026-10-14-audit-capture-roles.md` (10 of 10 rejections, role matrix) |
| G1.5 Three-tier relay | PASS | `654510b` | `middleware/tests/test_uvloop_enabled.py`, `SNDEV/docs/impl-2026-10-13-telemetry-relay.md` |
| G1.6 FHIR path | PASS | `654510b` | `vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py` |
| G1.7 Transport security | PASS | `a44c163` | `SNDEV/docs/impl-2026-10-14-r2-tls.md` (connection matrix, zero xfail markers) |
| G1.8 Performance scope | OPEN | none | Tasks 1.6 and 1.11 remain. The 500-session run and p95 measurement are not done. |

The G1.3 boundaries are tail deletion, which needs an external anchor (finding F3), and decoded-value callers, which must use the JsonText path.

### Estimate arithmetic

The Phase 1 task rows give these estimates:

| Task | Est. | Status before | Status after |
|:-----|:-----|:--------------|:-------------|
| 1.1 | 4.0 d | done | done |
| 1.2 | 1.5 d | done | done |
| 1.3 | 1.0 d | done | done |
| 1.4 | 3.0 d | open | open |
| 1.5 | 4.0 d | done | done |
| 1.6 | 2.0 d | open | open |
| 1.7 | 2.0 d | done | done |
| 1.8 | 3.0 d | open | open |
| 1.9 | 2.0 d | open | open |
| 1.10 | 1.5 d | open | done (`4d2a372`) |
| 1.11 | 1.0 d | open | open |
| 1.12 | 0.5 d | open | open |

Before: complete is 4.0 + 1.5 + 1.0 + 4.0 + 2.0 = 12.5 d. Remaining is 3.0 + 2.0 + 3.0 + 2.0 + 1.5 + 1.0 + 0.5 = 13.0 d. Total is 25.5 d.

After: complete is 4.0 + 1.5 + 1.0 + 4.0 + 2.0 + 1.5 = 14.0 d. Remaining is 3.0 + 2.0 + 3.0 + 2.0 + 1.0 + 0.5 = 11.5 d. Total is 25.5 d.

Tasks 1.4, 1.8, and 1.9 have landed commits (`a44c163`, `f4b9d8f`) and their gates are PASS. Their rows are not marked done in this change because the task scope names only task 1.10. If those rows are also marked done, the complete figure becomes 22.0 d (adds 3.0 + 3.0 + 2.0) and the remaining figure becomes 3.5 d (tasks 1.6, 1.11, and 1.12). That is a separate decision for the plan owner.

### Migration map changes

* Digest equivalence row (Table 3): OPEN changed to CLOSED (`4d2a372`), with the decoded-value boundary of 14 vectors.
* Gateway R2 row (Table 3): OPEN (carried) changed to CLOSED (`a44c163`).
* Table 4 rows added: rejected attempts are not audit-logged (design limit), the denylist includes `admin`, the shared 5432 container runs with ssl=off, and the middleware client-key wrapper is not exercised in a live container.

### Items not changed

* Table 3 rows for automatic audit capture and role separation still read OPEN, although gate G1.2 and G1.4 are PASS. Their status was not in this change's scope.
* Findings F-1 to F-4 from `SNDEV/docs/impl-2026-10-14-audit-capture-roles.md` have no migration-map row. F-1 is the compose init mount list, which omits migrations 004 and 005.
* DEVELOPMENT_PLAN.md Section 7.1 still says Gateway R2 remains open.

## Verification

### Commit hashes

`git log --oneline` resolves each cited hash:

* `ffcf167 test(compliance): qualify baseline on PostgreSQL 15 and fix IQ-5 pins`
* `f4b9d8f feat(compliance): audit capture trigger and role separation (1.8, 1.9)`
* `4d2a372 fix(hash-chain): prove Python and SQL digest equivalence across JSON types (1.10)`
* `94fc8d1 docs,ci: record hygiene updates and qualification job (1.12)`
* `a44c163 feat(security): enforce PostgreSQL client-cert TLS (R2, NFR-SEC-001)`
* `654510b fix(auth,relay): unblock suite imports and qualify 006 migration on PostgreSQL`
* `d0ef2c5 feat(relay): migrate telemetry relay with off-loop persistence (R3)`

Result: PASS (all seven hashes resolve).

### Evidence paths

Each path cited in DEVELOPMENT_PLAN.md, docs/migration-map.md, and this log was checked with `Test-Path` from the repository root. The checked paths are the three impl logs, `vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py`, `middleware/tests/test_uvloop_enabled.py`, `middleware/tests/test_db_ssl_config.py`, `vv/tests/OQ/test_oq_fr_dat_005_json_types.py`, `vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py`, `vv/tests/OQ/test_oq_fr_dat_004_audit_capture.py`, `vv/tests/OQ/test_oq_fr_dat_006_access_control.py`, `middleware/tests/test_roles_scope.py`, `docs/db-client-cert-tls.md`, `database/certs/generate-certs.sh`, `database/postgres/pg_hba.conf`, `database/migrations/004-audit-capture.sql`, `database/migrations/005-roles.sql`, `SNDEV/scripts/tls-connection-matrix.py`, and the SNDEV logs named in the three evidence logs.

Result: PASS (every checked path exists).

### Gate test evidence

Tests were not re-run in this change. It edits documents only. The gate results come from the cited impl logs.

### Staging

Only `DEVELOPMENT_PLAN.md`, `docs/migration-map.md`, and this log were staged for the commit, by name. Other agents' files were not touched.
