Title: mechanical FMU status 3 under pipelined timing, diagnosis and fix (plan task 2.8 slice 3a)
Date: 2026-11-12T12:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.8 slice 3a; follows SNDEV/docs/impl-2026-11-12-val033-rebase.md (Part 2 open item)
Summary: Isolates the pipelined three-node failure (mechanical participant fmi3DoStep status 3 after 1 to 16 steps) to a layer, tests the two suspects (second request during a worker step or partial reply; state reuse under overlapping calls), measures the failure-step distribution over repeated runs, and applies the smallest fix the mechanism supports before the VAL-033 measurements.

## Task Reference

Open item of `SNDEV/docs/impl-2026-11-12-val033-rebase.md`, Part 2 (pipelined master). The pipelined master (VAL-033 slice 3) and the stale-input rule (`sim/fmi/master/src/pipelined_exchange.cpp`, six Catch2 cases) are in the working tree and uncommitted. Requirement FR-MS-007 (SRS v1.5.0, VAL-033). Plan task 2.8.

## Specification Summary

1. Standalone driver that speaks the participant request and reply protocol, with a structured capture of every request and every worker reply.
2. Classify the status 3 into one of three layers: the DLL's `fmi3DoStep` wrapper, the named-pipe protocol to the worker, or the runSofa worker. Test suspects (a) a second request during a worker step or partial reply, and (b) state reuse under overlapping calls.
3. Determinism: at least 20 runs at the failing cadence, with the failure-step distribution.
4. Smallest honest fix once the mechanism is confirmed. Stale-input semantics changes go to the owner.
5. Then the two VAL-033 measurements (quiet single-node reference, ten-minute three-node run) against the rebased clauses.

## Preflight

(Recorded below in Implementation Notes.)

## Implementation Notes

Status: mechanism confirmed; fix in progress. Each measurement is recorded with its artifact.

### Preflight

* Pipelined master and stale-input class uncommitted in the working tree (`sim/fmi/master/src/three_node_master.cpp`, `pipelined_exchange.cpp`, `tests/test_pipelined_exchange.cpp`). Catch2 suite passes (`SNDEV/logs/fmi-master-catch2-pipelined-2026-11-12.txt`).
* Host state before the diagnosis: total CPU quiet, no watched process; the `pulse-fmi-worker` container is up (precondition).

### Finding 1: the wrapper hides the FMU's reason (classification layer)

`FmuParticipant::do_step` (`sim/fmi/master/src/fmu_participant.cpp`) replaces the FMU's own reason with the generic text "fmi3DoStep returned FMI status 3". The FMU's own reason is written only through the FMI log callback, and the participant instantiated the FMU with logging off. So every reason was discarded, and the status 3 looked like one unexplained failure.

Instrumentation added (default off, no change to the protocol): the environment switch `SRTA_FMU_LOGGING=1` turns the FMU logging on, and `SRTA_PARTICIPANT_TRACE=1` makes the participant trace each request (tick, request time, the FMU time after the step). With logging on, the mechanical DLL reports: `[fmu 3 mechanical_sofa] currentCommunicationPoint does not match the FMU time`.

### Finding 2: the failing layer is the request-time contract, not the DLL, the pipe, or DDS

The DLL's `fmi3DoStep` returns status 3 at its time check (`currentCommunicationPoint` against the FMU time, tolerance 1e-9 s). The DLL and the worker run correctly at the serialized cadence (M1 to M5 pass). The failing request carries a time the FMU has not reached.

Standalone burst probe (`sim/fmi/master/tools/burst_probe.py`, record `SNDEV/logs/fmi-burst-probe-2026-11-12.json`): 40 requests sent at 1 ms spacing, with the participant running on one node and no master. The participant executed all 40 in order (trace tail shows ticks 28 to 39, each with the FMU time equal to the request time plus one step). So DDS delivery and the participant callback do not drop or reorder requests when the requests are on schedule. The probe rules out suspects (a) partial reply and (b) reentrancy under the probe cadence.

Trace of the failing pipelined run (`SNDEV/logs/fmi-three-node-smoke-diag-20s-2026-11-12T100452Z-node2-mechanical-stderr.txt`): the participant executes tick 0 (request time 0.000, FMU time after 0.001), then receives tick 25 with request time 0.025, and the DLL refuses (the FMU is at 0.001). Ticks 1 to 24 were never sent, because the master keeps one step in flight.

Mechanism (confirmed by the code and by the trace):

1. The mechanical DoStep takes 11 to 36 ms, longer than the 1 ms master tick.
2. The pipelined exchange sends the request for step s when the reply for step s-1 is read. That is the tick after the participant finishes, which is later than s ms.
3. The request's `master_time_ns` is the tick at which it is sent (`sim/fmi/master/src/three_node_master.cpp`, line 271: `req.master_time_ns = tick_ns`). The FMU's time is the step count times the step size.
4. The two diverge as soon as one step spans more than one tick. The first step matches (tick 0 and time 0). The second step carries the completion tick as its time and the FMU refuses it. The observed failure tick (13, 16, 17, 25, 29) is the tick at which the reply for step 0 arrived, which varies with the step duration.

So the status 3 is the FMU correctly refusing a request whose time is not the FMU's next time. The serialized master never shows it, because the serialized master sends step s at tick s, so the request time and the FMU time match.

Semantic consequence: the request's time must be the participant's own next step time, not the tick at which the request is sent. The tick of the request becomes metadata. The stale-input rule is unchanged (the held value is still the reply of the previous step); only the request time is corrected.

### Fix (applied)

`sim/fmi/master/src/three_node_master.cpp`: the pipelined request carries the participant's own next step time, `master_time_ns = step_index * step_ns`, instead of the send tick. The send tick is kept in `req.tick` and the stale-input rule is unchanged (the held value is still the reply of the previous step). Semantic note for the owner: the request time now means the FMU time the participant is due to step, which is the FMI contract. The send tick no longer equals the FMU time, which is the pipelining itself.

Verification of the fix:

* Trace check (`SNDEV/logs/fmi-three-node-smoke-fix-20s-*-node2-mechanical-stderr.txt`): 467 trace lines, zero mismatches between request time plus one step and the FMU time after the step, and no status 3.
* Determinism (20 runs, 8 s each, the same cadence that failed): zero stderr output and zero status 3 in 20 of 20 runs, with 183 to 261 mechanical steps per run and 517 to 520 pipelined round trips per run. The master exited 0 in every run. Records: `SNDEV/logs/fmi-three-node-determinism*-*.json`.
* Catch2 suite (16 test cases, including the six stale-input cases): passes after the fix (`SNDEV/logs/fmi-master-build-fix-tests-2026-11-12.txt`).

### Determinism (failure-step distribution)

Before the fix: every run failed. The failing step was between 1 and 16 in the earlier smoke runs, and the failing request tick (13, 16, 17, 25, 29) was the tick at which the reply for the previous step arrived. That is a distribution set by the mechanical step duration, not a random failure: the failure fires on the first step whose request is sent after the FMU's time has moved on.

After the fix: 20 of 20 runs complete with no status 3.

### Diagnostic instrumentation kept (default off)

* `SRTA_FMU_LOGGING=1`: the FMU's own diagnostics reach stderr (the wrapper previously discarded them).
* `SRTA_PARTICIPANT_TRACE=1`: the participant traces each request with the FMU time after the step.
* `sim/fmi/master/tools/burst_probe.py`: a standalone burst probe (40 requests at 1 ms spacing, no master). It shows the participant executes an on-schedule burst in order, so DDS delivery is not the failing layer.

### Classification (summary)

* Layer that returns status 3: the DLL's `fmi3DoStep` time check, which correctly refuses a request whose time is not the FMU's next time.
* Not the failing layer: the named-pipe protocol (the DLL reads one reply per step, and the probes show no partial or duplicated reply), the DDS delivery (the burst probe), and the runSofa worker (its log shows no error).
* Suspect (b), reentrancy: not reproduced. The failure is fully explained by the request-time contract, and the fixed run shows no overlap error.

### Single-node quiet reference (rebased clauses, VAL-033)

Record `SNDEV/logs/fmi-multirate-single-node-quiet-val033-600s-2026-11-12T104127Z.json`, sidecar `.messages.json`, launcher `fmi-multirate-single-node-quiet-val033-launcher-2026-11-12.txt`. Host before: 1.9 percent CPU, no watched process. Host after: 1.6 percent CPU, no watched process (`...-host-before.txt`, `...-host-after.txt`).

Result: 49,921 master ticks in 600 s. Each stream has 49,921 messages with consecutive sequences. Epoch check passed.

* (a) Skew p99 at most 2 ms: worst stream 1.03 ms (Pulse). PASS.
* (b) Jitter p99 at most 1.5 times the schedule tick: schedule tick 11.2 ms (mechanical DoStep), bound 16.8 ms; worst stream jitter p99 15.33 ms (Pulse). PASS, with about 1.5 ms of margin.
* (c) Zero timeouts and exact schedule adherence: a single node has no remote steps. The recorded tick sequence is consecutive on every stream. PASS on the recorded sequence, not a remote-step result.
* (d) Stamp resolution at least 1 ms: the perf_counter resolution is 1e-7 s. PASS.

Per-stream values (skew p50 / p99 / max absolute, ms; jitter p50 / p99 / max absolute, ms): clock 0.22 / 0.53 / 3.08 and 10.67 / 15.30 / 28.02; thermal 0.30 / 0.70 / 3.24 and 10.68 / 15.30 / 28.14; mechanical 0.38 / 0.91 / 3.34 and 10.68 / 15.32 / 27.40; Pulse 0.59 / 1.03 / 3.43 and 10.68 / 15.33 / 27.31. The maximum values are recorded per the clause and are above the 2 ms skew p99 bound at the tail; the clause does not bound the maximum.

### Three-node run (rebased clauses, VAL-033, pipelined)

Record `SNDEV/logs/fmi-three-node-g26-val033-pipelined-600s-2026-11-12T105252Z.json`, sidecar `.messages.json` (41.7 MB), per-node transcripts `...-node1-master.txt`, `...-node2-mechanical.txt`, `...-node3-pulse.txt`, launcher `fmi-three-node-g26-val033-launcher-2026-11-12.txt`. Topology as attempt 1: node 1 the master (clock, thermal FMU, pipelined remote steps), node 2 the mechanical participant, node 3 the Pulse participant (container worker on 127.0.0.1:5055 as precondition). Host before: 0.27 percent CPU, no watched process. Host after: 0.34 percent CPU at the late check, no watched process. The launcher writes no host snapshot file for the three-node run; the before and after values are from the manual checks in this log.

Result: master exit 0, mechanical participant exit 0 (6,731 steps), Pulse participant exit 0 (32,220 steps). Every stderr file is empty. The master ran 600,001 ticks (1 kHz, the master grid) with zero reply timeouts (master summary), 38,949 remote round trips, and 621,051 late replies (ticks with no reply yet for the step in flight; the master holds the last reply, the zero-order hold). Epoch check passed. Each stream has consecutive tick sequences, with 600,001 messages on the clock and thermal streams.

Rebased clauses (the schedule grid is the master's 1 ms tick; the bound is 1.5 times it):

* (a) Skew p99 at most 2 ms: worst stream 0.80 ms (Pulse). PASS.
* (b) Jitter p99 at most 1.5 times the schedule tick (1.5 ms): worst stream 0.48 ms (Pulse). PASS. The maximum is recorded: 16.5 ms on the clock stream and 13.8 ms on Pulse. The master's maximum lateness is 4.13 ms, and 81 ticks were late by more than 1 ms.
* (c) Zero timeouts and exact schedule adherence: zero reply timeouts (master summary, not the record's run block, which does not carry the field), and no participant error. Exact schedule adherence does NOT hold. The schedule has 600,001 mechanical step points, and the mechanical participant executed 6,731 of them (the master held the last reply in between, the zero-order hold). The Pulse participant executed 32,220 steps against 60,001 scheduled step points. Clause (c) reads "every scheduled participant step executes exactly as scheduled", so the pipelined run does not meet (c) as written. Verdict on (c): FAIL as worded. This is an owner decision: either clause (c) admits the zero-order hold for a participant running slower than its schedule (a semantic change to VAL-033), or the pipeline must match the participant's rate to the schedule (not achievable with a 11 ms step on a 1 ms grid).
* (d) Stamp resolution at least 1 ms: the perf_counter resolution is 1e-7 s. PASS.

Per-stream (skew p50 / p99 / max absolute, ms; jitter p50 / p99 / max absolute, ms): clock 0.20 / 0.36 / 17.55 and 0.02 / 0.34 / 16.50; thermal 0.28 / 0.51 / 17.65 and 0.02 / 0.38 / 10.92; mechanical 0.35 / 0.64 / 17.73 and 0.02 / 0.43 / 9.37; Pulse 0.49 / 0.80 / 18.73 and 0.02 / 0.48 / 13.83. The maximum skew values (17 to 19 ms) are tail events on all streams at once; the clause does not bound the maximum, and it is recorded as the clause requires.

Round-trip split, for comparison with attempt 1 (master summary, `split_*` fields, pipelined, mean ms):

| Part | Attempt 1 (serialized, 31 ms wait) | Pipelined (this run) |
|:--|--:|--:|
| Request transit | 15.47 | 22.05 |
| FMU step (mechanical) | 10.64 | 4.54 |
| Reply transit | 4.98 | 4.22 |

The pipelined request transit is longer because the master sends requests at 1 kHz and the participant consumes them at its own step rate, so the queueing delay sits in the transit. The FMU step is shorter because the participant executed fewer steps (6,731 against 17,495) over the same wall time. The master no longer waits for the reply inside the tick, so the master's tick rate is not set by the round trip.

Overall verdict on the rebased clauses: (a), (b), and (d) PASS; (c) FAIL as worded (see above). The gate G2.6 claim is therefore not met under the clause as written, and the open item is the owner decision on clause (c).

Interpretation and limits. Clauses (a), (b), and (d) pass on this run. The run is single-host over loopback, so the skew measures the delivery and epoch offset on one machine, not network latency, and the multi-host case stays unmeasured (VAL-033 Section 6). The pipelined mechanical state is one step stale in the zero-order hold, and the mechanical participant ran about 11 Hz against the master's 1 kHz grid; the schedule semantics document this (VAL-033 Section 3 clause (c) and the pipelined exchange, `sim/fmi/master/src/pipelined_exchange.cpp`). The 6,731-step count is the participant's actual rate under the pipeline, and the clause does not require a particular participant rate, only exact adherence to the schedule the master runs.
