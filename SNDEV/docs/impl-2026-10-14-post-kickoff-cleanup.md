Title: Post-kickoff documentation hygiene for VTM, plan, migration map, and SOUP
Date: 2026-10-14T21:31:12Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: residue from the 2026-10-14 Phase 2 kickoff and SRS v1.1 application streams
Summary: Corrects stale status statements in four tracked documents after commits 6fe9786, fd5e111, 5fb26a3, and 2cf977c. Documentation only.

## Task Reference

Instruction from the parent session on 2026-10-14. The residue comes from commit `6fe9786` (Phase 1 closure), commits `fd5e111` and `5fb26a3` (Phase 2 kickoff, Pulse delegation, SOUP inventory), and commit `2cf977c` (SRS.md v1.1.0).

Read-only inputs: SRS.md v1.1.0, `docs/srs-v1.1-change-proposal.md`, `SNDEV/docs/impl-2026-10-14-srs-v1.1-apply.md`, `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md`, `SNDEV/docs/impl-2026-10-14-phase1-closure.md`, and `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`.

## Specification Summary

Six items:

1. The intro paragraph of `vv/traceability/vtm.md` describes the SRS Section 5 table as a 10-row extract.
2. The FR-RTA-003 footnote in `vv/traceability/vtm.md` says the gap is open pending the SRS v1.1 amendment.
3. The NFR-PERF-001 through NFR-PERF-004 Test Method cells in `vv/traceability/vtm.md` show stale status for task 1.6.
4. The Pulse delegation debt row in `docs/migration-map.md` is OPEN.
5. `DEVELOPMENT_PLAN.md` needs two wording fixes: the Section 7.1 Gateway relay impact text, and a check of the G1.8 audit-parity note.
6. The Locust and websockets Pin status cells in `sim/SOUP.md` show no exact pin.

Acceptance Metric cells in the VTM, the SRS, the protocol register, and all test files are out of scope.

## Implementation Notes

### vv/traceability/vtm.md

Item 1, intro paragraph, line 5.
Old: "This table extends the SRS.md Section 5 VTM (lines 89-100), which carries rows for 10 of the 31 requirement IDs defined in Sections 3 and 4."
New: "This table extends the SRS.md Section 5 extract (lines 91-112 of SRS.md v1.1.0), which carries rows for 20 of the 31 requirement IDs defined in Sections 3 and 4 and defers to this file on any disagreement."
The row set, marker, and toolchain sentences are unchanged. The line range was stale and is updated with the count.

Item 2, FR-RTA-003 footnote, line 47.
Old, first sentence: "FR-RTA-003 has no SRS acceptance metric to supersede (finding VAL-003); its metric is new and is written against the risk-file thresholds."
New: "FR-RTA-003 has no SRS v1.0.0 acceptance metric to supersede (finding VAL-003); its metric is new and is written against the risk-file thresholds. SRS v1.1.0 closed VAL-003 with its own Section 5 row for FR-RTA-003 carrying this metric. The risk-file threshold values still pend Phase 3 task 3.1 (stub values 5.0 mm and 2.0 N until then)."
Old, second sentence (VAL-012): "...the gap stays open for the SRS v1.1 amendment."
New: "...the gap stays open because the SRS v1.1.0 amendment set (VAL-001 to VAL-004) did not cover it. The SOUP inventory is at `sim/SOUP.md`."
The phrase "stays open" sits in the VAL-012 sentence, not the FR-RTA-003 sentence, so both sentences are updated.

Item 3, Test Method cells, lines 34, 35, and 37. NFR-PERF-003 (line 36) is unchanged because its Phase 7 task 7.5 status is current.
NFR-PERF-001, old: "load definition planned (task 1.6): `vv/tests/PQ/locustfile.py`"
NFR-PERF-001, new: "load definition (task 1.6, done): `vv/tests/PQ/locustfile.py`; configuration record `SNDEV/docs/impl-2026-10-14-pq-config.md`"
NFR-PERF-002, old: "planned (task 1.6): `vv/tests/PQ/locustfile.py` (WSS leg); planned (task 4.6)"
NFR-PERF-002, new: "load definition (task 1.6, done): `vv/tests/PQ/locustfile.py` (WSS leg), configuration record `SNDEV/docs/impl-2026-10-14-pq-config.md`; relay leg evidence from run g18-run1 (500 sessions at 10 points per second offered, publisher round trip p95 1.46 ms, plaintext database connection, `SNDEV/logs/pq-2026-10-14-g18-run1.json`); planned (task 4.6)"
NFR-PERF-004, old: "planned (task 1.6): `vv/tests/PQ/locustfile.py`"
NFR-PERF-004, new: "load definition (task 1.6, done): `vv/tests/PQ/locustfile.py`; configuration record `SNDEV/docs/impl-2026-10-14-pq-config.md`; run g18-run1 (500 sessions, audit parity PASS at 2 audit rows per completed session, `SNDEV/logs/pq-2026-10-14-g18-run1.json`)"
The planned test file paths for NFR-PERF-001 (task 5.6), NFR-PERF-002 (task 4.6), and NFR-PERF-003 (task 7.5) are unchanged. The g18-run1 run used the pytest harness `vv/tests/PQ/test_pq_relay_sessions.py`, not Locust. The cell text names the harness through the existing entry.

Acceptance Metric cells: none changed (see Verification).

### docs/migration-map.md

Item 4, Table row "ProcessPoolExecutor delegation for Pulse steps".
Old status: "OPEN"
New status: "CLOSED (`5fb26a3`)"
Old note: "`SimulationManager.step_simulation` is synchronous. The native engine object cannot be pickled, so a process pool needs one long-lived worker per engine."
New note: the same two sentences, with "so a process pool needs" changed to "so the landed design is", followed by the design and the boundary: "one long-lived spawned worker per engine instance, with the native engine created inside the worker, the step awaited off the event loop with a bounded timeout, and fail-closed handling on import failure or worker crash. Boundary: the real-engine run is pending the pinned Pulse build (task 2.6), and the 100% statement and branch coverage obligation for `middleware/engine/pulse.py` and `middleware/engine/pulse_bridge.py` is open because no coverage tool is pinned."
The design sentence was checked against `middleware/engine/pulse.py` (module docstring lines 16 to 27; `_child` worker functions and `PulseWorker` lines 376 to 640, with `spawn` at line 334) and against `middleware/requirements-test.txt`, which has no coverage package.

### DEVELOPMENT_PLAN.md

Item 5a, Section 7.1 row "Gateway R3 relay path", Impact cell.
Old: "NFR-PERF-002 holds only at 10 points per second on this host, because the 50 ms bound fails at 20 points per second and above."
New: "NFR-PERF-002 holds only at 10 points per second on this host, and the 50 ms bound fails at 20 points per second and above. The tail-latency source is not isolated: the relay serializes broadcast fan-out per frame (`ConnectionManager.broadcast`), and client-side queueing in the single client process is an unmeasured candidate."
The source is run record Finding 1 in `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`. The row's causal "because" clause named the rate threshold, not fan-out. The fan-out causal claim appears in the G1.8 row (see Deliberately left).

Item 5b, Phase 1 gate G1.8 PASS note (Phase 1 gate table, line 181).
The note already states the audit-parity definition: "`audit_log` at 1,000 rows (2 per completed session)", with the session count and the surgical telemetry row count. The row is unchanged, as the item instructs.

### sim/SOUP.md

Item 6, Pin status cells.
Locust row, old: "pin gap (add an exact pin in a load-test requirements file)"
Locust row, new: "pinned (exact pin tracked in `vv/tests/PQ/requirements.txt`)"
websockets row, old: "pin gap (add an exact pin to `middleware/requirements.txt` at the next pin change)"
websockets row, new: "pinned (exact pin tracked in `vv/tests/PQ/requirements.txt`)"
The file `vv/tests/PQ/requirements.txt` pins `locust==2.46.7` and `websockets==17.2`, as checked on disk. The Version cells and all other cells are unchanged.

### Deliberately left

* `vv/traceability/vtm.md` Coverage Statement (line 51) describes a sweep of SRS.md v1.0.0 that counts 10 surplus Section 5 rows. That is a dated record of v1.0.0, so it is not rewritten here. The item scope covered only the intro paragraph.
* `DEVELOPMENT_PLAN.md` line 181 (G1.8 PASS row) still attributes the 50 ms boundary to "broadcast fan-out serialization". Run record Finding 1 says the source was not isolated. This sentence sits outside the two wording fixes that item 5 allows.
* `sim/SOUP.md` Version cells still read "Not pinned in a tracked file" (Locust) and "Not pinned directly" (websockets). Item 6 limited edits to the Pin status cells.
* `vv/tests/PQ/requirements.txt` was untracked at the time of editing, because it belongs to the parallel stream. The SOUP cells cite that path.

## Verification

| Check | Method | Result |
|:------|:-------|:-------|
| Diff scope | `git diff --stat` over the four tracked files | 4 files, 9 insertions and 9 deletions. Only the lines listed above changed. PASS |
| Acceptance Metric byte identity in vtm.md | Split each FR and NFR row of `git show HEAD:vv/traceability/vtm.md` and of the working copy on the pipe character, and compare the last table cell | 31 of 31 rows identical. PASS |
| Stale phrases gone | Grep for "carries rows for 10 of the 31", "planned (task 1.6): `vv/tests/PQ/locustfile.py`", "pending the SRS v1.1 amendment", "pin gap (add", "because the 50 ms bound fails", and the OPEN status on the Pulse row | 0 matches for each. The Pulse row reads "CLOSED (`5fb26a3`)". PASS |
| New statements present once | Grep for "lines 91-112 of SRS.md v1.1.0", "defers to this file on any disagreement", "still pend Phase 3 task 3.1", "CLOSED (`5fb26a3`)", and "tail-latency source is not isolated" | 1 match each. The "exact pin tracked" statement matches 2 times, once in each SOUP row. PASS |
| Section 5 extract row count | Grep `^\| \*\*(FR\|NFR)-` in SRS.md | 20 rows, matching "20 of the 31". PASS |
| VTM row count | Grep `^\| (FR\|NFR)-` in vv/traceability/vtm.md | 31 rows, matching "31 requirement IDs". PASS |
| Pulse design claims | Read `middleware/engine/pulse.py` and `middleware/requirements-test.txt` | Spawned single-process `ProcessPoolExecutor` with bounded timeouts and fail-closed handling; no coverage package is pinned. PASS |
| SOUP pins on disk | Read `vv/tests/PQ/requirements.txt` | `locust==2.46.7` and `websockets==17.2`. PASS |
| Banned words in inserted text | Scan added lines and this log for the banned list in AGENTS.md section 1 | See sweep result below |
| Em dashes, en dashes, curly quotes in inserted text | Scan added lines and this log for U+2014, U+2013, U+201C, U+201D, U+2018, U+2019 | See sweep result below |

No code or test file was edited, and no test was run.
