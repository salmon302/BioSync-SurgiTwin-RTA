// SPDX-License-Identifier: MIT
// pulse_physiology: FMI 3.0 Co-Simulation FMU proxy for the Kitware Pulse engine (SRS FR-MS-006 and FR-MS-007,
// plan task 2.7 slice 3).
//
// The DLL does not link Pulse. The engine runs in the biosync-pulse Linux container. The DLL connects to a
// TCP worker (sim/fmi/pulse/worker/pulse_worker.py) and exchanges MessagePack frames: a 4-byte big-endian
// length, then one MessagePack map. One connection is one FMU instance and owns one engine in the worker.
//
// Lifecycle: fmi3ExitInitializationMode connects and sends "init". fmi3DoStep sends "step" with n = 1
// (one engine step of 0.01 s) and then "pull". fmi3Reset sends "shutdown" and closes the connection; the next
// initialization opens a new connection and creates a fresh engine. Any failure returns fmi3Error.
//
// The MessagePack encoder and decoder below cover the subset the protocol uses: maps with string keys, strings,
// booleans, integers, doubles, arrays of doubles, and nil. The decoder reads the same subset and rejects others.
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "fmi3PlatformTypes.h"
#include "fmi3FunctionTypes.h"
#include "fmi3Functions.h"

#pragma comment(lib, "ws2_32.lib")

namespace
{

const char * kInstantiationToken = "b3e1d7a4-5f20-4c8e-9a61-0d2f7c4e8b19";
const double kStepSize = 0.01;  // Pulse engine TIME_STEP (middleware/engine/pulse.py)
const double kTimeTolerance = 1.0e-9;
const DWORD kSocketTimeoutMs = 120000;

// Value references (match model/modelDescription.xml).
enum : fmi3ValueReference
{
  kVrTime = 0,
  kVrPortUnused = 1,  // reserved (the worker host is fixed to 127.0.0.1 in this slice, see README)
  kVrPort = 2,
  kVrPatientAge = 3,
  kVrPatientWeight = 4,
  kVrPatientHeight = 5,
  kVrExerciseIntensity = 10,
  kVrHeartRate = 20,
  kVrSystolic = 21,
  kVrDiastolic = 22,
  kVrRespirationRate = 23,
  kVrSpO2 = 24,
  kVrMeanAirwayPressure = 25,
  kVrArterialO2 = 26,
  kVrEngineTime = 27,
  kVrEngineMs = 28,
};

enum class State { kConfig, kInitMode, kStepping, kTerminated };

// Minimal MessagePack writer for the protocol subset.
class Packer
{
public:
  void map(std::size_t n)
  {
    if (n < 16) {
      bytes_.push_back(static_cast<char>(0x80 | n));
    } else {
      bytes_.push_back(static_cast<char>(0xde));
      u16(static_cast<std::uint16_t>(n));
    }
  }
  void str(const std::string & s)
  {
    if (s.size() < 32) {
      bytes_.push_back(static_cast<char>(0xa0 | s.size()));
    } else {
      bytes_.push_back(static_cast<char>(0xda));
      u16(static_cast<std::uint16_t>(s.size()));
    }
    bytes_.insert(bytes_.end(), s.begin(), s.end());
  }
  void boolean(bool v) { bytes_.push_back(static_cast<char>(v ? 0xc3 : 0xc2)); }
  void integer(std::int64_t v)
  {
    if (v >= 0 && v < 128) {
      bytes_.push_back(static_cast<char>(v));
    } else {
      bytes_.push_back(static_cast<char>(0xd3));
      u64(static_cast<std::uint64_t>(v));
    }
  }
  void real(double v)
  {
    bytes_.push_back(static_cast<char>(0xcb));
    std::uint64_t bits;
    std::memcpy(&bits, &v, sizeof(bits));
    u64(bits);
  }
  const std::string & bytes() const { return bytes_; }
  void clear() { bytes_.clear(); }

private:
  void u16(std::uint16_t v)
  {
    bytes_.push_back(static_cast<char>(v >> 8));
    bytes_.push_back(static_cast<char>(v & 0xff));
  }
  void u64(std::uint64_t v)
  {
    for (int shift = 56; shift >= 0; shift -= 8) {
      bytes_.push_back(static_cast<char>((v >> shift) & 0xff));
    }
  }
  std::string bytes_;
};

// Decoded reply value (protocol subset).
struct Value
{
  enum Kind { kNil, kBool, kInt, kReal, kStr, kMap, kArray } kind = kNil;
  bool b = false;
  std::int64_t i = 0;
  double d = 0.0;
  std::string s;
  std::map<std::string, Value> map;
  std::vector<Value> array;
};

class Unpacker
{
public:
  explicit Unpacker(std::string data) : data_(std::move(data)) {}
  bool read(Value & out) { return value(out, 0); }

private:
  bool need(std::size_t n) const { return pos_ + n <= data_.size(); }
  std::uint8_t byte() { return static_cast<std::uint8_t>(data_[pos_++]); }
  std::uint64_t be(std::size_t n)
  {
    std::uint64_t v = 0;
    for (std::size_t k = 0; k < n; ++k) v = (v << 8) | byte();
    return v;
  }
  bool value(Value & out, int depth)
  {
    if (depth > 8 || !need(1)) return false;
    const std::uint8_t tag = byte();
    if (tag <= 0x7f) { out.kind = Value::kInt; out.i = tag; return true; }
    if (tag >= 0xe0) { out.kind = Value::kInt; out.i = static_cast<std::int8_t>(tag); return true; }
    if ((tag & 0xf0) == 0x80) return map_n(out, tag & 0x0f, depth);
    if ((tag & 0xf0) == 0x90) return array_n(out, tag & 0x0f, depth);
    if ((tag & 0xe0) == 0xa0) return str_n(out, tag & 0x1f);
    switch (tag) {
      case 0xc0: out.kind = Value::kNil; return true;
      case 0xc2: out.kind = Value::kBool; out.b = false; return true;
      case 0xc3: out.kind = Value::kBool; out.b = true; return true;
      case 0xca: {
        if (!need(4)) return false;
        std::uint32_t bits = static_cast<std::uint32_t>(be(4));
        float f;
        std::memcpy(&f, &bits, sizeof(f));
        out.kind = Value::kReal; out.d = f; return true;
      }
      case 0xcb: {
        if (!need(8)) return false;
        std::uint64_t bits = be(8);
        std::memcpy(&out.d, &bits, sizeof(bits));
        out.kind = Value::kReal; return true;
      }
      case 0xcc: if (!need(1)) return false; out.kind = Value::kInt; out.i = byte(); return true;
      case 0xcd: if (!need(2)) return false; out.kind = Value::kInt; out.i = static_cast<std::int64_t>(be(2)); return true;
      case 0xce: if (!need(4)) return false; out.kind = Value::kInt; out.i = static_cast<std::int64_t>(be(4)); return true;
      case 0xcf: if (!need(8)) return false; out.kind = Value::kInt; out.i = static_cast<std::int64_t>(be(8)); return true;
      case 0xd0: if (!need(1)) return false; out.kind = Value::kInt; out.i = static_cast<std::int8_t>(byte()); return true;
      case 0xd1: if (!need(2)) return false; out.kind = Value::kInt; out.i = static_cast<std::int16_t>(be(2)); return true;
      case 0xd2: if (!need(4)) return false; out.kind = Value::kInt; out.i = static_cast<std::int32_t>(be(4)); return true;
      case 0xd3: if (!need(8)) return false; out.kind = Value::kInt; out.i = static_cast<std::int64_t>(be(8)); return true;
      case 0xd9: if (!need(1)) return false; return str_n(out, byte());
      case 0xda: if (!need(2)) return false; return str_n(out, be(2));
      case 0xdc: if (!need(2)) return false; return array_n(out, be(2), depth);
      case 0xde: if (!need(2)) return false; return map_n(out, be(2), depth);
      default: return false;
    }
  }
  bool str_n(Value & out, std::size_t n)
  {
    if (!need(n)) return false;
    out.kind = Value::kStr;
    out.s.assign(data_, pos_, n);
    pos_ += n;
    return true;
  }
  bool array_n(Value & out, std::size_t n, int depth)
  {
    out.kind = Value::kArray;
    out.array.clear();
    for (std::size_t k = 0; k < n; ++k) {
      Value v;
      if (!value(v, depth + 1)) return false;
      out.array.push_back(v);
    }
    return true;
  }
  bool map_n(Value & out, std::size_t n, int depth)
  {
    out.kind = Value::kMap;
    out.map.clear();
    for (std::size_t k = 0; k < n; ++k) {
      Value key;
      if (!value(key, depth + 1) || key.kind != Value::kStr) return false;
      Value v;
      if (!value(v, depth + 1)) return false;
      out.map[key.s] = v;
    }
    return true;
  }
  std::string data_;
  std::size_t pos_ = 0;
};

struct Connection
{
  SOCKET sock = INVALID_SOCKET;

  ~Connection() { close(); }

  void close()
  {
    if (sock != INVALID_SOCKET) {
      closesocket(sock);
      sock = INVALID_SOCKET;
    }
  }

  bool connect_to(const std::string & host, unsigned short port, std::string & error)
  {
    addrinfo hints{};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    addrinfo * result = nullptr;
    const std::string port_text = std::to_string(port);
    if (getaddrinfo(host.c_str(), port_text.c_str(), &hints, &result) != 0) {
      error = "cannot resolve worker host " + host;
      return false;
    }
    sock = socket(result->ai_family, result->ai_socktype, result->ai_protocol);
    if (sock == INVALID_SOCKET) {
      freeaddrinfo(result);
      error = "socket() failed";
      return false;
    }
    DWORD timeout = kSocketTimeoutMs;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char *>(&timeout), sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char *>(&timeout), sizeof(timeout));
    BOOL nodelay = TRUE;
    setsockopt(sock, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char *>(&nodelay), sizeof(nodelay));
    const int rc = connect(sock, result->ai_addr, static_cast<int>(result->ai_addrlen));
    freeaddrinfo(result);
    if (rc == SOCKET_ERROR) {
      error = "connect to the Pulse worker failed (is the biosync-pulse container running and the port published?)";
      close();
      return false;
    }
    return true;
  }

  bool send_all(const char * data, std::size_t n)
  {
    while (n > 0) {
      const int sent = send(sock, data, static_cast<int>(n), 0);
      if (sent <= 0) return false;
      data += sent;
      n -= static_cast<std::size_t>(sent);
    }
    return true;
  }

  bool recv_all(char * data, std::size_t n)
  {
    while (n > 0) {
      const int got = recv(sock, data, static_cast<int>(n), 0);
      if (got <= 0) return false;
      data += got;
      n -= static_cast<std::size_t>(got);
    }
    return true;
  }
};

struct Instance
{
  std::string instance_name;
  fmi3LogMessageCallback log = nullptr;
  fmi3InstanceEnvironment env = nullptr;
  bool logging = false;
  State state = State::kConfig;
  double time = 0.0;
  double start_time = 0.0;

  // Parameters.
  std::string host = "127.0.0.1";
  double port = 5055.0;
  double age = 45.0;
  double weight_kg = 70.0;
  double height_cm = 175.0;
  bool sex_female = false;

  // Input (applied by the worker as an exercise action when it changes).
  double exercise_intensity = 0.0;
  double applied_exercise = 0.0;

  // Outputs of the last completed step.
  double heart_rate = 0.0;
  double systolic = 0.0;
  double diastolic = 0.0;
  double respiration_rate = 0.0;
  double spo2 = 0.0;
  double mean_airway_pressure = 0.0;
  double arterial_o2 = 0.0;
  double engine_time = 0.0;
  double engine_ms = 0.0;

  Connection conn;
  std::string error;
};

void log_error(Instance * inst, const std::string & message)
{
  if (inst == nullptr) return;
  inst->error = message;
  if (inst->log != nullptr && inst->logging) {
    inst->log(inst->env, fmi3Error, "pulse_physiology", message.c_str());
  }
}

// Sends one request frame and reads one reply frame. Returns false on transport or decode errors.
bool exchange(Instance * inst, const Packer & request, Value & reply)
{
  const std::string & body = request.bytes();
  unsigned char header[4] = {
    static_cast<unsigned char>(body.size() >> 24),
    static_cast<unsigned char>(body.size() >> 16),
    static_cast<unsigned char>(body.size() >> 8),
    static_cast<unsigned char>(body.size()),
  };
  if (!inst->conn.send_all(reinterpret_cast<const char *>(header), 4) ||
      !inst->conn.send_all(body.data(), body.size()))
  {
    log_error(inst, "send to the Pulse worker failed (connection lost)");
    return false;
  }
  unsigned char reply_header[4];
  if (!inst->conn.recv_all(reinterpret_cast<char *>(reply_header), 4)) {
    log_error(inst, "no reply from the Pulse worker (timeout or connection lost)");
    return false;
  }
  const std::size_t n = (static_cast<std::size_t>(reply_header[0]) << 24) |
    (static_cast<std::size_t>(reply_header[1]) << 16) |
    (static_cast<std::size_t>(reply_header[2]) << 8) | static_cast<std::size_t>(reply_header[3]);
  if (n == 0 || n > (8u << 20)) {
    log_error(inst, "malformed frame length from the Pulse worker");
    return false;
  }
  std::string payload(n, '\0');
  if (!inst->conn.recv_all(&payload[0], n)) {
    log_error(inst, "truncated frame from the Pulse worker");
    return false;
  }
  Unpacker unpacker(payload);
  if (!unpacker.read(reply) || reply.kind != Value::kMap) {
    log_error(inst, "malformed MessagePack reply from the Pulse worker");
    return false;
  }
  auto ok = reply.map.find("ok");
  if (ok == reply.map.end() || ok->second.kind != Value::kBool) {
    log_error(inst, "reply has no ok field");
    return false;
  }
  if (!ok->second.b) {
    auto err = reply.map.find("error");
    log_error(inst, "Pulse engine error: " + (err != reply.map.end() ? err->second.s : std::string("unknown")));
    return false;
  }
  return true;
}

bool real_field(const Value & map, const char * key, double & out)
{
  auto it = map.map.find(key);
  if (it == map.map.end()) return false;
  if (it->second.kind == Value::kReal) { out = it->second.d; return true; }
  if (it->second.kind == Value::kInt) { out = static_cast<double>(it->second.i); return true; }
  return false;
}

bool start_worker(Instance * inst)
{
  const unsigned short port = static_cast<unsigned short>(inst->port);
  if (!inst->conn.connect_to(inst->host, port, inst->error)) {
    log_error(inst, inst->error);
    return false;
  }
  Packer p;
  p.map(2);
  p.str("op"); p.str("init");
  p.str("patient");
  p.map(6);
  p.str("patient_id"); p.str("fmu-" + inst->instance_name);
  p.str("age"); p.real(inst->age);
  p.str("weight_kg"); p.real(inst->weight_kg);
  p.str("height_cm"); p.real(inst->height_cm);
  p.str("sex"); p.str(inst->sex_female ? "female" : "male");
  p.str("pad"); p.boolean(false);
  Value reply;
  return exchange(inst, p, reply);
}

}  // namespace

extern "C" {

const char * fmi3GetVersion(void)
{
  return fmi3Version;
}

fmi3Status fmi3SetDebugLogging(fmi3Instance instance, fmi3Boolean loggingOn, size_t nCategories,
  const fmi3String categories[])
{
  (void)nCategories;
  (void)categories;
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return fmi3Error;
  inst->logging = loggingOn != fmi3False;
  return fmi3OK;
}

fmi3Instance fmi3InstantiateCoSimulation(fmi3String instanceName, fmi3String instantiationToken,
  fmi3String resourcePath, fmi3Boolean visible, fmi3Boolean loggingOn, fmi3Boolean eventModeUsed,
  fmi3Boolean earlyReturnAllowed, const fmi3ValueReference requiredIntermediateVariables[],
  size_t nRequiredIntermediateVariables, fmi3InstanceEnvironment instanceEnvironment,
  fmi3LogMessageCallback logMessage, fmi3IntermediateUpdateCallback intermediateUpdate)
{
  (void)resourcePath;
  (void)visible;
  (void)eventModeUsed;
  (void)earlyReturnAllowed;
  (void)requiredIntermediateVariables;
  (void)nRequiredIntermediateVariables;
  (void)intermediateUpdate;
  if (instantiationToken == nullptr || std::strcmp(instantiationToken, kInstantiationToken) != 0) {
    return nullptr;
  }
  static bool wsa_started = false;
  if (!wsa_started) {
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) return nullptr;
    wsa_started = true;
  }
  Instance * inst = new Instance();
  inst->instance_name = instanceName != nullptr ? instanceName : "pulse";
  inst->env = instanceEnvironment;
  inst->log = logMessage;
  inst->logging = loggingOn != fmi3False;
  return static_cast<fmi3Instance>(inst);
}

void fmi3FreeInstance(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return;
  inst->conn.close();
  delete inst;
}

fmi3Status fmi3EnterInitializationMode(fmi3Instance instance, fmi3Boolean toleranceDefined, fmi3Float64 tolerance,
  fmi3Float64 startTime, fmi3Boolean stopTimeDefined, fmi3Float64 stopTime)
{
  (void)toleranceDefined;
  (void)tolerance;
  (void)stopTimeDefined;
  (void)stopTime;
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr || inst->state != State::kConfig) return fmi3Error;
  inst->start_time = startTime;
  inst->time = startTime;
  inst->state = State::kInitMode;
  return fmi3OK;
}

fmi3Status fmi3ExitInitializationMode(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr || inst->state != State::kInitMode) return fmi3Error;
  if (std::fabs(inst->start_time) > kTimeTolerance) {
    log_error(inst, "the Pulse FMU starts at time 0");
    return fmi3Error;
  }
  if (!start_worker(inst)) {
    inst->conn.close();
    return fmi3Error;
  }
  inst->state = State::kStepping;
  return fmi3OK;
}

fmi3Status fmi3Terminate(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return fmi3Error;
  if (inst->conn.sock != INVALID_SOCKET) {
    Packer p;
    p.map(1);
    p.str("op"); p.str("shutdown");
    Value reply;
    exchange(inst, p, reply);
    inst->conn.close();
  }
  inst->state = State::kTerminated;
  return fmi3OK;
}

fmi3Status fmi3Reset(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return fmi3Error;
  if (inst->conn.sock != INVALID_SOCKET) {
    Packer p;
    p.map(1);
    p.str("op"); p.str("shutdown");
    Value reply;
    exchange(inst, p, reply);
  }
  inst->conn.close();
  inst->time = 0.0;
  inst->start_time = 0.0;
  inst->age = 45.0; inst->weight_kg = 70.0; inst->height_cm = 175.0; inst->sex_female = false;
  inst->exercise_intensity = 0.0;
  inst->applied_exercise = 0.0;
  inst->heart_rate = inst->systolic = inst->diastolic = 0.0;
  inst->respiration_rate = inst->spo2 = inst->mean_airway_pressure = inst->arterial_o2 = 0.0;
  inst->engine_time = inst->engine_ms = 0.0;
  inst->state = State::kConfig;
  inst->error.clear();
  return fmi3OK;
}

fmi3Status fmi3DoStep(fmi3Instance instance, fmi3Float64 currentCommunicationPoint, fmi3Float64 communicationStepSize,
  fmi3Boolean noSetFMUStatePriorToCurrentPoint, fmi3Boolean * eventHandlingNeeded,
  fmi3Boolean * terminateSimulation, fmi3Boolean * earlyReturn, fmi3Float64 * lastSuccessfulTime)
{
  (void)noSetFMUStatePriorToCurrentPoint;
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr || inst->state != State::kStepping) return fmi3Error;
  if (std::fabs(communicationStepSize - kStepSize) > kTimeTolerance) {
    log_error(inst, "communicationStepSize must equal the Pulse engine step (0.01 s)");
    return fmi3Error;
  }
  if (std::fabs(currentCommunicationPoint - inst->time) > 1.0e-6) {
    log_error(inst, "currentCommunicationPoint does not match the FMU time");
    return fmi3Error;
  }
  if (!std::isfinite(inst->exercise_intensity) || inst->exercise_intensity < 0.0 || inst->exercise_intensity > 1.0) {
    log_error(inst, "exercise_intensity must be between 0 and 1");
    return fmi3Error;
  }

  if (inst->exercise_intensity != inst->applied_exercise) {
    Packer a;
    a.map(3);
    a.str("op"); a.str("action");
    a.str("kind"); a.str("exercise_intensity");
    a.str("value"); a.real(inst->exercise_intensity);
    Value reply;
    if (!exchange(inst, a, reply)) return fmi3Error;
    inst->applied_exercise = inst->exercise_intensity;
  }

  Packer s;
  s.map(2);
  s.str("op"); s.str("step");
  s.str("n"); s.integer(1);
  Value step_reply;
  if (!exchange(inst, s, step_reply)) return fmi3Error;
  real_field(step_reply, "engine_ms", inst->engine_ms);

  Packer q;
  q.map(1);
  q.str("op"); q.str("pull");
  Value pull;
  if (!exchange(inst, q, pull)) return fmi3Error;
  double t = 0.0;
  auto values = pull.map.find("values");
  auto time_field = pull.map.find("time_s");
  if (values == pull.map.end() || values->second.kind != Value::kArray || values->second.array.size() != 7) {
    log_error(inst, "pull reply does not carry seven physiology values");
    return fmi3Error;
  }
  if (!real_field(pull, "time_s", t)) {
    log_error(inst, "pull reply has no time_s");
    return fmi3Error;
  }
  (void)time_field;
  const std::vector<Value> & v = values->second.array;
  double out[7];
  for (int k = 0; k < 7; ++k) {
    if (v[k].kind == Value::kReal) {
      out[k] = v[k].d;
    } else if (v[k].kind == Value::kInt) {
      out[k] = static_cast<double>(v[k].i);
    } else {
      out[k] = std::nan("");
    }
  }
  inst->heart_rate = out[0];
  inst->systolic = out[1];
  inst->diastolic = out[2];
  inst->respiration_rate = out[3];
  inst->spo2 = out[4];
  inst->mean_airway_pressure = out[5];
  inst->arterial_o2 = out[6];
  inst->engine_time = t;
  inst->time += communicationStepSize;

  if (eventHandlingNeeded != nullptr) *eventHandlingNeeded = fmi3False;
  if (terminateSimulation != nullptr) *terminateSimulation = fmi3False;
  if (earlyReturn != nullptr) *earlyReturn = fmi3False;
  if (lastSuccessfulTime != nullptr) *lastSuccessfulTime = inst->time;
  return fmi3OK;
}

fmi3Status fmi3SetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences,
  const fmi3Float64 values[], size_t nValues)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr || nValues != nValueReferences) return fmi3Error;
  for (size_t n = 0; n < nValueReferences; ++n) {
    const fmi3ValueReference vr = valueReferences[n];
    const double v = values[n];
    const bool parameter = vr == kVrPort || vr == kVrPatientAge || vr == kVrPatientWeight || vr == kVrPatientHeight;
    if (parameter && inst->state != State::kConfig && inst->state != State::kInitMode) {
      log_error(inst, "patient and port parameters can be set only before initialization");
      return fmi3Error;
    }
    switch (vr) {
      case kVrPort:
        if (!(v >= 1.0 && v <= 65535.0) || v != std::floor(v)) { log_error(inst, "port must be an integer in 1..65535"); return fmi3Error; }
        inst->port = v;
        break;
      case kVrPatientAge:
        if (!(v > 0.0 && v < 120.0)) { log_error(inst, "age must be in (0, 120) years"); return fmi3Error; }
        inst->age = v;
        break;
      case kVrPatientWeight:
        if (!(v > 0.0 && v < 400.0)) { log_error(inst, "weight_kg must be in (0, 400)"); return fmi3Error; }
        inst->weight_kg = v;
        break;
      case kVrPatientHeight:
        if (!(v > 0.0 && v < 250.0)) { log_error(inst, "height_cm must be in (0, 250)"); return fmi3Error; }
        inst->height_cm = v;
        break;
      case kVrExerciseIntensity:
        inst->exercise_intensity = v;
        break;
      default:
        return fmi3Error;
    }
  }
  return fmi3OK;
}

fmi3Status fmi3GetFloat64(fmi3Instance instance, const fmi3ValueReference valueReferences[], size_t nValueReferences,
  fmi3Float64 values[], size_t nValues)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr || nValues != nValueReferences) return fmi3Error;
  for (size_t n = 0; n < nValueReferences; ++n) {
    double v = 0.0;
    switch (valueReferences[n]) {
      case kVrTime: v = inst->time; break;
      case kVrPort: v = inst->port; break;
      case kVrPatientAge: v = inst->age; break;
      case kVrPatientWeight: v = inst->weight_kg; break;
      case kVrPatientHeight: v = inst->height_cm; break;
      case kVrExerciseIntensity: v = inst->exercise_intensity; break;
      case kVrHeartRate: v = inst->heart_rate; break;
      case kVrSystolic: v = inst->systolic; break;
      case kVrDiastolic: v = inst->diastolic; break;
      case kVrRespirationRate: v = inst->respiration_rate; break;
      case kVrSpO2: v = inst->spo2 * 100.0; break;
      case kVrMeanAirwayPressure: v = inst->mean_airway_pressure; break;
      case kVrArterialO2: v = inst->arterial_o2; break;
      case kVrEngineTime: v = inst->engine_time; break;
      case kVrEngineMs: v = inst->engine_ms; break;
      default:
        return fmi3Error;
    }
    values[n] = v;
  }
  return fmi3OK;
}

}  // extern "C"
