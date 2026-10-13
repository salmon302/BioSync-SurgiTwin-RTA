# Continuous Verification Tier (V&V)

Status: placeholder. Scripts and harness code are not implemented yet.

This tier holds the ASAM XIL test abstraction, the bidirectional traceability engine, and the IQ/OQ/PQ protocol tests.

* `xil/`: ASAM XIL v3.0.0 port adapters (SRS FR-VV-002, FR-VV-003)
* `traceability/`: requirements trace engine (SRS FR-VV-005)
* `tests/IQ/`: installation qualification tests, including the repo layout check
* `tests/OQ/`: operational qualification tests (empty)
* `tests/PQ/`: performance qualification tests (empty)

Run the current IQ checks from the repo root with `python -m pytest vv/tests -q`.
