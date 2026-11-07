# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: Pulse engine worker for the physiology FMU (plan task 2.7 slice 3)
# Date: 2026-11-07T20:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.7 slice 3
# Summary: Container-side TCP worker that owns one Pulse engine per connection and serves MessagePack frames (init, step, pull, action, serialize, shutdown) to the pulse_physiology FMU.
"""Pulse engine worker for the physiology FMU (SRS FR-MS-006 engine rules, plan task 2.7 slice 3).

Runs inside the biosync-pulse container (Python 3.11.13, PYTHONPATH=/pulse/python:/pulse/bin). It listens
on a TCP port (default 5055, see sim/fmi/pulse/README.md). Each accepted connection is one FMU instance:
the connection owns exactly one Pulse engine, created on the "init" request and destroyed when the
connection closes or on "shutdown". The engine object is never pickled or shared across connections.

Frame format (both directions): 4-byte unsigned big-endian length, then one MessagePack map.

Requests (field "op"):
  {"op": "init", "patient": {...}}              create the engine and initialize the patient
  {"op": "step", "n": int}                      advance n engine steps of 0.01 s (TIME_STEP)
  {"op": "action", "kind": str, "value": float}  apply a scenario action (see ACTION_KINDS)
  {"op": "pull"}                                read the physiology data requests
  {"op": "serialize"}                           return the engine state as a JSON string
  {"op": "shutdown"}                            release the engine and close the connection

Replies (field "ok"): {"ok": true, ...} on success, {"ok": false, "error": str} on any failure. A failure
after "init" leaves the connection open, but the FMU treats any failure as fail-closed.
"""

import os
import socket
import struct
import sys
import time

import msgpack

TIME_STEP_S = 0.01
DEFAULT_PORT = 5055
MAX_FRAME_BYTES = 8 << 20  # a serialized engine state is about 2.3 MB (measured 2026-11-07)
PULSE_DATA_ROOT = os.environ.get("PULSE_DATA_ROOT", "/pulse/bin")
PHYSIOLOGY_REQUESTS = [
    "HeartRate",
    "SystolicArterialPressure",
    "DiastolicArterialPressure",
    "RespirationRate",
    "OxygenSaturation",
    "MeanAirwayPressure",
    "ArterialOxygenPartialPressure",
]
ACTION_KINDS = ("exercise_intensity",)


def recv_exact(conn, count):
    chunks = []
    remaining = count
    while remaining:
        chunk = conn.recv(remaining)
        if not chunk:
            raise ConnectionError("peer closed the connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(conn):
    (length,) = struct.unpack(">I", recv_exact(conn, 4))
    if length == 0 or length > MAX_FRAME_BYTES:
        raise ValueError(f"frame length {length} is outside 1..{MAX_FRAME_BYTES}")
    return msgpack.unpackb(recv_exact(conn, length), raw=False)


def write_frame(conn, message):
    payload = msgpack.packb(message, use_bin_type=True)
    conn.sendall(struct.pack(">I", len(payload)) + payload)


class EngineSession:
    """One Pulse engine. Created on init, released on shutdown or connection close."""

    def __init__(self):
        self.engine = None
        self.drm = None
        self.pulse = None

    def initialize(self, patient):
        import Pulse  # compat shim over the pulse bindings (loaded inside the worker only)
        from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
        from pulse.cdm.patient import SEPatientConfiguration, eSex
        from pulse.cdm.scalars import LengthUnit, MassUnit, TimeUnit

        self.pulse = Pulse
        self.engine = Pulse.Engine(data_root_dir=PULSE_DATA_ROOT)
        config = SEPatientConfiguration()
        obj = config.get_patient()
        obj.set_name(str(patient["patient_id"]))
        obj.get_age().set_value(float(patient["age"]), TimeUnit.yr)
        obj.get_weight().set_value(float(patient["weight_kg"]), MassUnit.kg)
        obj.get_height().set_value(float(patient["height_cm"]), LengthUnit.cm)
        obj.set_sex(eSex.Female if str(patient["sex"]).lower() == "female" else eSex.Male)
        self.drm = SEDataRequestManager([SEDataRequest.create_physiology_request(n) for n in PHYSIOLOGY_REQUESTS])
        if not self.engine.initialize_engine(config, self.drm):
            raise RuntimeError("initialize_engine returned False")

    def step(self, n):
        for _ in range(n):
            self.engine.advance_time_s(TIME_STEP_S)

    def action(self, kind, value):
        if kind not in ACTION_KINDS:
            raise ValueError(f"unknown action kind {kind}")
        from pulse.cdm.patient_actions import SEExercise
        act = SEExercise()
        act.get_intensity().set_value(float(value))
        self.engine.process_action(act)

    def pull(self):
        values = self.engine.pull_data()
        if values is None or len(values) < 2:
            raise RuntimeError("pull_data returned no physiology values")
        return {"time_s": float(values[0]),
                "values": [float(values[i + 1]) for i in range(len(PHYSIOLOGY_REQUESTS))]}

    def serialize(self):
        from pulse.cdm.engine import eSerializationFormat
        return self.engine.serialize_to_string(eSerializationFormat.JSON)

    def close(self):
        self.engine = None
        self.drm = None


def handle(session, request):
    op = request.get("op")
    if op == "init":
        session.initialize(request["patient"])
        return {"ok": True}
    if session.engine is None:
        raise RuntimeError("engine not initialized on this connection")
    if op == "step":
        n = int(request["n"])
        if n < 1 or n > 1000:
            raise ValueError("n must be between 1 and 1000")
        started = time.perf_counter()
        session.step(n)
        return {"ok": True, "engine_ms": (time.perf_counter() - started) * 1000.0}
    if op == "action":
        session.action(request["kind"], request["value"])
        return {"ok": True}
    if op == "pull":
        out = session.pull()
        out["ok"] = True
        return out
    if op == "serialize":
        return {"ok": True, "state_json": session.serialize()}
    raise ValueError(f"unknown op {op}")


def serve_connection(conn):
    session = EngineSession()
    try:
        while True:
            try:
                request = read_frame(conn)
            except ConnectionError:
                break
            if request.get("op") == "shutdown":
                write_frame(conn, {"ok": True})
                break
            try:
                reply = handle(session, request)
            except Exception as exc:  # reported to the FMU; the FMU is fail-closed on any error
                reply = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            write_frame(conn, reply)
    finally:
        session.close()
        conn.close()


def main(argv):
    port = int(argv[1]) if len(argv) > 1 else DEFAULT_PORT
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(4)
    print(f"pulse_worker listening on 0.0.0.0:{port}", flush=True)
    while True:
        conn, _ = server.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        serve_connection(conn)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
