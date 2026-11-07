// SPDX-License-Identifier: MIT
// mechanical_sofa: FMI 3.0 Co-Simulation FMU proxy for the SOFA reference organ (SRS FR-MS-007, plan task 2.7 slice 2).
//
// The DLL does not link SOFA. In fmi3ExitInitializationMode it starts runSofa.exe with SofaPython3 and the
// worker scene (resources/mechanical_worker.py). fmi3DoStep sends one "STEP" line over a named pipe and reads
// one reply line after the worker has advanced one solver step (dt 0.001 s). fmi3Reset stops the worker and
// starts a new one, so a reset gives the same state as a fresh instance.
//
// Environment (read at instantiation, with build-time defaults):
//   SRTA_SOFA_ROOT   SOFA install root (default: the pinned v26.06.00 install)
//   SRTA_SOFAPY_ENV  pixi environment with the CPython 3.12 runtime (default: env/ros2-jazzy default env)
#include <windows.h>

#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>

#include "fmi3PlatformTypes.h"
#include "fmi3FunctionTypes.h"
#include "fmi3Functions.h"

#ifndef SRTA_DEFAULT_SOFA_ROOT
#define SRTA_DEFAULT_SOFA_ROOT "C:\\Users\\salmo\\SOFA\\v26.06.00"
#endif
#ifndef SRTA_DEFAULT_PIXI_ENV
#define SRTA_DEFAULT_PIXI_ENV "I:\\Documents\\GitHub\\BioSync\\BioSync-SurgiTwin-RTA\\env\\ros2-jazzy\\.pixi\\envs\\default"
#endif

namespace
{

const double kStepSize = 0.001;
const double kTimeTolerance = 1.0e-12;
const DWORD kConnectTimeoutMs = 120000;
const DWORD kReplyTimeoutMs = 30000;

// Value references (must match model/modelDescription.xml).
enum : fmi3ValueReference
{
  kVrTime = 0,
  kVrToolStiffness = 1,
  kVrTipX = 10, kVrTipY = 11, kVrTipZ = 12,
  kVrQuatX = 13, kVrQuatY = 14, kVrQuatZ = 15, kVrQuatW = 16,
  kVrForceX = 20, kVrForceY = 21, kVrForceZ = 22,
  kVrTorqueX = 23, kVrTorqueY = 24, kVrTorqueZ = 25,
  kVrPoseX = 30, kVrPoseY = 31, kVrPoseZ = 32,
  kVrPoseQx = 33, kVrPoseQy = 34, kVrPoseQz = 35, kVrPoseQw = 36,
  kVrMaxDisp = 40, kVrMeanDisp = 41, kVrTipNodeDisp = 42, kVrStepCount = 43,
};

enum class State { kConfig, kInitMode, kStepping, kTerminated };

struct Instance
{
  std::string instance_name;
  std::string resource_dir;  // ends with a backslash
  fmi3LogMessageCallback log = nullptr;
  fmi3InstanceEnvironment env = nullptr;
  bool logging = false;
  State state = State::kConfig;
  double start_time = 0.0;
  double time = 0.0;

  // Parameters and inputs (defaults restored by reset).
  double tool_stiffness = 2000.0;
  double tip[3] = {0.1, 0.2, 0.1};
  double quat[4] = {0.0, 0.0, 0.0, 1.0};

  // Outputs of the last completed step.
  double wrench[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
  double max_disp = 0.0;
  double mean_disp = 0.0;
  double tip_node_disp = 0.0;
  double steps = 0.0;

  // Worker transport.
  HANDLE process = nullptr;
  HANDLE pipe = INVALID_HANDLE_VALUE;
  HANDLE pipe_event = nullptr;
  std::string pipe_name;
  std::string config_path;
  std::string stdout_path;
  std::string pending;  // bytes read from the pipe beyond the last reply line
  std::string error;
};

void log_error(Instance * inst, const std::string & message)
{
  if (inst != nullptr) {
    inst->error = message;
    if (inst->log != nullptr && inst->logging) {
      inst->log(inst->env, fmi3Error, "mechanical_sofa", message.c_str());
    }
  }
}

std::string json_escape_path(const std::string & path)
{
  std::string out;
  for (char c : path) {
    if (c == '\\') {
      out += "\\\\";
    } else {
      out += c;
    }
  }
  return out;
}

std::string env_or(const char * name, const char * fallback)
{
  char buffer[1024];
  DWORD n = GetEnvironmentVariableA(name, buffer, sizeof(buffer));
  if (n == 0 || n >= sizeof(buffer)) {
    return fallback;
  }
  return std::string(buffer, n);
}

bool write_file(const std::string & path, const std::string & text)
{
  HANDLE h = CreateFileA(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (h == INVALID_HANDLE_VALUE) {
    return false;
  }
  DWORD written = 0;
  BOOL ok = WriteFile(h, text.data(), static_cast<DWORD>(text.size()), &written, nullptr);
  CloseHandle(h);
  return ok && written == text.size();
}

// Environment block for the worker: the current block with PATH, PYTHONPATH, and SRTA_MECH_CONFIG replaced.
std::vector<char> worker_environment(const std::string & sofa_root, const std::string & pixi_env,
  const std::string & config_path)
{
  const std::string path_value = pixi_env + ";" + pixi_env + "\\Library\\bin;" +
    sofa_root + "\\collections\\bin;" + env_or("PATH", "");
  const std::string pythonpath = sofa_root + "\\plugins\\SofaPython3\\lib\\python3\\site-packages;" +
    sofa_root + "\\collections\\bin";
  std::vector<std::string> entries;
  char * block = GetEnvironmentStringsA();
  if (block != nullptr) {
    for (const char * p = block; *p != '\0'; p += std::strlen(p) + 1) {
      std::string entry(p);
      std::string upper;
      for (size_t i = 0; i < entry.size() && entry[i] != '='; ++i) {
        upper += static_cast<char>(std::toupper(static_cast<unsigned char>(entry[i])));
      }
      if (upper == "PATH" || upper == "PYTHONPATH" || upper == "SRTA_MECH_CONFIG") {
        continue;
      }
      entries.push_back(entry);
    }
    FreeEnvironmentStringsA(block);
  }
  entries.push_back("PATH=" + path_value);
  entries.push_back("PYTHONPATH=" + pythonpath);
  entries.push_back("SRTA_MECH_CONFIG=" + config_path);
  std::vector<char> out;
  for (const std::string & e : entries) {
    out.insert(out.end(), e.begin(), e.end());
    out.push_back('\0');
  }
  out.push_back('\0');
  return out;
}

// Overlapped read of one reply line with a timeout. Returns false on timeout, EOF, or error.
bool read_line(Instance * inst, std::string & line, DWORD timeout_ms)
{
  for (;;) {
    size_t nl = inst->pending.find('\n');
    if (nl != std::string::npos) {
      line = inst->pending.substr(0, nl);
      inst->pending.erase(0, nl + 1);
      return true;
    }
    char buffer[512];
    OVERLAPPED ov{};
    ov.hEvent = inst->pipe_event;
    ResetEvent(inst->pipe_event);
    DWORD got = 0;
    if (!ReadFile(inst->pipe, buffer, sizeof(buffer), &got, &ov)) {
      if (GetLastError() != ERROR_IO_PENDING) {
        return false;
      }
      HANDLE waits[2] = {inst->pipe_event, inst->process};
      DWORD wait = WaitForMultipleObjects(2, waits, FALSE, timeout_ms);
      if (wait != WAIT_OBJECT_0) {
        CancelIo(inst->pipe);
        return false;
      }
      if (!GetOverlappedResult(inst->pipe, &ov, &got, FALSE)) {
        return false;
      }
    }
    if (got == 0) {
      return false;
    }
    inst->pending.append(buffer, got);
  }
}

bool write_all(Instance * inst, const std::string & text)
{
  OVERLAPPED ov{};
  ov.hEvent = inst->pipe_event;
  ResetEvent(inst->pipe_event);
  DWORD written = 0;
  if (!WriteFile(inst->pipe, text.data(), static_cast<DWORD>(text.size()), &written, &ov)) {
    if (GetLastError() != ERROR_IO_PENDING) {
      return false;
    }
    if (WaitForSingleObject(inst->pipe_event, kReplyTimeoutMs) != WAIT_OBJECT_0) {
      CancelIo(inst->pipe);
      return false;
    }
    if (!GetOverlappedResult(inst->pipe, &ov, &written, FALSE)) {
      return false;
    }
  }
  return written == text.size();
}

void stop_worker(Instance * inst)
{
  if (inst->pipe != INVALID_HANDLE_VALUE) {
    write_all(inst, "QUIT\n");
    CloseHandle(inst->pipe);
    inst->pipe = INVALID_HANDLE_VALUE;
  }
  if (inst->process != nullptr) {
    if (WaitForSingleObject(inst->process, 15000) != WAIT_OBJECT_0) {
      TerminateProcess(inst->process, 1);
      WaitForSingleObject(inst->process, 5000);
    }
    CloseHandle(inst->process);
    inst->process = nullptr;
  }
  if (inst->pipe_event != nullptr) {
    CloseHandle(inst->pipe_event);
    inst->pipe_event = nullptr;
  }
  inst->pending.clear();
  if (!inst->config_path.empty()) {
    DeleteFileA(inst->config_path.c_str());
    inst->config_path.clear();
  }
}

bool start_worker(Instance * inst)
{
  static LONG counter = 0;
  const LONG n = InterlockedIncrement(&counter);
  char temp_dir[MAX_PATH];
  GetTempPathA(MAX_PATH, temp_dir);
  const std::string stem = std::string(temp_dir) + "srta-mech-" + std::to_string(GetCurrentProcessId()) +
    "-" + std::to_string(n);
  inst->config_path = stem + ".json";
  inst->stdout_path = stem + "-worker.log";
  inst->pipe_name = "\\\\.\\pipe\\srta-mech-" + std::to_string(GetCurrentProcessId()) + "-" + std::to_string(n);

  const std::string sofa_root = env_or("SRTA_SOFA_ROOT", SRTA_DEFAULT_SOFA_ROOT);
  const std::string pixi_env = env_or("SRTA_SOFAPY_ENV", SRTA_DEFAULT_PIXI_ENV);
  const std::string worker = inst->resource_dir + "mechanical_worker.py";
  const std::string mesh = inst->resource_dir + "meshes\\reference_organ.msh";

  char tip_buf[256];
  std::snprintf(tip_buf, sizeof(tip_buf), "%.17g, %.17g, %.17g", inst->tip[0], inst->tip[1], inst->tip[2]);
  char stiff_buf[64];
  std::snprintf(stiff_buf, sizeof(stiff_buf), "%.17g", inst->tool_stiffness);
  std::string config = "{\n";
  config += "  \"mesh_path\": \"" + json_escape_path(mesh) + "\",\n";
  config += "  \"transport\": \"pipe\",\n";
  config += "  \"pipe_path\": \"" + json_escape_path(inst->pipe_name) + "\",\n";
  config += "  \"tool_stiffness_n_per_m\": " + std::string(stiff_buf) + ",\n";
  config += "  \"initial_tip_m\": [" + std::string(tip_buf) + "],\n";
  config += "  \"dump_steps\": [],\n";
  config += "  \"dump_dir\": \"" + json_escape_path(std::string(temp_dir)) + "\",\n";
  config += "  \"results_path\": \"" + json_escape_path(stem + "-results.json") + "\"\n";
  config += "}\n";
  if (!write_file(inst->config_path, config)) {
    log_error(inst, "cannot write the worker configuration");
    return false;
  }

  inst->pipe = CreateNamedPipeA(inst->pipe_name.c_str(),
    PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
    PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
    1, 65536, 65536, 0, nullptr);
  if (inst->pipe == INVALID_HANDLE_VALUE) {
    log_error(inst, "CreateNamedPipe failed");
    return false;
  }
  inst->pipe_event = CreateEventA(nullptr, TRUE, FALSE, nullptr);

  SECURITY_ATTRIBUTES sa{sizeof(sa), nullptr, TRUE};
  HANDLE out = CreateFileA(inst->stdout_path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa,
    CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  STARTUPINFOA si{};
  si.cb = sizeof(si);
  si.dwFlags = STARTF_USESTDHANDLES;
  si.hStdOutput = out;
  si.hStdError = out;
  si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  PROCESS_INFORMATION pi{};

  const std::string runsofa = sofa_root + "\\collections\\bin\\runSofa.exe";
  std::string cmdline = "\"" + runsofa + "\" \"" + worker + "\" -l SofaPython3 -g batch -n 1000000000";
  std::vector<char> env = worker_environment(sofa_root, pixi_env, inst->config_path);
  std::vector<char> cmd(cmdline.begin(), cmdline.end());
  cmd.push_back('\0');
  BOOL created = CreateProcessA(nullptr, cmd.data(), nullptr, nullptr, TRUE,
    CREATE_NO_WINDOW, env.data(), temp_dir, &si, &pi);
  if (out != INVALID_HANDLE_VALUE) {
    CloseHandle(out);
  }
  if (!created) {
    log_error(inst, "CreateProcess failed for runSofa.exe (check SRTA_SOFA_ROOT)");
    return false;
  }
  CloseHandle(pi.hThread);
  inst->process = pi.hProcess;

  // Wait for the worker to connect the pipe (scene load), or for the worker to exit.
  OVERLAPPED ov{};
  ov.hEvent = inst->pipe_event;
  ResetEvent(inst->pipe_event);
  if (!ConnectNamedPipe(inst->pipe, &ov)) {
    DWORD err = GetLastError();
    if (err == ERROR_PIPE_CONNECTED) {
      return true;
    }
    if (err != ERROR_IO_PENDING) {
      log_error(inst, "ConnectNamedPipe failed");
      return false;
    }
    HANDLE waits[2] = {inst->pipe_event, inst->process};
    DWORD wait = WaitForMultipleObjects(2, waits, FALSE, kConnectTimeoutMs);
    if (wait != WAIT_OBJECT_0) {
      log_error(inst, "runSofa worker did not connect (see " + inst->stdout_path + ")");
      return false;
    }
  }
  return true;
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
  (void)visible;
  (void)eventModeUsed;
  (void)earlyReturnAllowed;
  (void)requiredIntermediateVariables;
  (void)nRequiredIntermediateVariables;
  (void)intermediateUpdate;
  if (instantiationToken == nullptr || std::strcmp(instantiationToken, "7c1e5a2b-94d0-4f63-b8a1-2e6d0f3c9a57") != 0) {
    return nullptr;
  }
  if (resourcePath == nullptr) {
    return nullptr;
  }
  Instance * inst = new Instance();
  inst->instance_name = instanceName != nullptr ? instanceName : "mechanical";
  inst->resource_dir = resourcePath;
  if (!inst->resource_dir.empty() && inst->resource_dir.back() != '\\') {
    inst->resource_dir += '\\';
  }
  inst->env = instanceEnvironment;
  inst->log = logMessage;
  inst->logging = loggingOn != fmi3False;
  return static_cast<fmi3Instance>(inst);
}

void fmi3FreeInstance(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return;
  stop_worker(inst);
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
    log_error(inst, "the mechanical FMU starts at time 0 (the worker scene has no start offset)");
    return fmi3Error;
  }
  if (!start_worker(inst)) {
    stop_worker(inst);
    return fmi3Error;
  }
  inst->state = State::kStepping;
  return fmi3OK;
}

fmi3Status fmi3Terminate(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return fmi3Error;
  stop_worker(inst);
  inst->state = State::kTerminated;
  return fmi3OK;
}

fmi3Status fmi3Reset(fmi3Instance instance)
{
  Instance * inst = static_cast<Instance *>(instance);
  if (inst == nullptr) return fmi3Error;
  stop_worker(inst);
  inst->time = 0.0;
  inst->start_time = 0.0;
  inst->tool_stiffness = 2000.0;
  inst->tip[0] = 0.1; inst->tip[1] = 0.2; inst->tip[2] = 0.1;
  inst->quat[0] = 0.0; inst->quat[1] = 0.0; inst->quat[2] = 0.0; inst->quat[3] = 1.0;
  for (double & w : inst->wrench) w = 0.0;
  inst->max_disp = inst->mean_disp = inst->tip_node_disp = inst->steps = 0.0;
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
    log_error(inst, "communicationStepSize must equal the SOFA scene dt (0.001 s)");
    return fmi3Error;
  }
  if (std::fabs(currentCommunicationPoint - inst->time) > 1.0e-9) {
    log_error(inst, "currentCommunicationPoint does not match the FMU time");
    return fmi3Error;
  }
  for (int i = 0; i < 3; ++i) {
    if (!std::isfinite(inst->tip[i])) { log_error(inst, "non-finite tip position"); return fmi3Error; }
  }
  for (int i = 0; i < 4; ++i) {
    if (!std::isfinite(inst->quat[i])) { log_error(inst, "non-finite tip orientation"); return fmi3Error; }
  }

  char line[512];
  std::snprintf(line, sizeof(line), "STEP %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n",
    inst->tip[0], inst->tip[1], inst->tip[2], inst->quat[0], inst->quat[1], inst->quat[2], inst->quat[3]);
  if (!write_all(inst, line)) {
    log_error(inst, "pipe write to the worker failed");
    stop_worker(inst);
    inst->state = State::kTerminated;
    return fmi3Error;
  }
  std::string reply;
  if (!read_line(inst, reply, kReplyTimeoutMs)) {
    log_error(inst, "no reply from the worker (see the worker log)");
    stop_worker(inst);
    inst->state = State::kTerminated;
    return fmi3Error;
  }
  if (reply.rfind("OK ", 0) != 0) {
    log_error(inst, "worker reply: " + reply);
    stop_worker(inst);
    inst->state = State::kTerminated;
    return fmi3Error;
  }
  double v[10];
  std::istringstream fields(reply.substr(3));
  bool parsed = true;
  for (int i = 0; i < 10 && parsed; ++i) {
    parsed = static_cast<bool>(fields >> v[i]);
  }
  if (!parsed) {
    log_error(inst, "cannot parse worker reply: " + reply);
    return fmi3Error;
  }
  for (double x : v) {
    if (!std::isfinite(x)) {
      log_error(inst, "non-finite worker output");
      return fmi3Error;
    }
  }
  for (int i = 0; i < 6; ++i) inst->wrench[i] = v[i];
  inst->max_disp = v[6];
  inst->mean_disp = v[7];
  inst->tip_node_disp = v[8];
  inst->steps = v[9];
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
    const bool is_parameter = vr == kVrToolStiffness;
    if (is_parameter && inst->state != State::kConfig && inst->state != State::kInitMode) {
      log_error(inst, "tool_stiffness can be set only before initialization");
      return fmi3Error;
    }
    switch (vr) {
      case kVrToolStiffness:
        if (!(v >= 0.0) || !std::isfinite(v)) { log_error(inst, "tool_stiffness must be finite and non-negative"); return fmi3Error; }
        inst->tool_stiffness = v;
        break;
      case kVrTipX: inst->tip[0] = v; break;
      case kVrTipY: inst->tip[1] = v; break;
      case kVrTipZ: inst->tip[2] = v; break;
      case kVrQuatX: inst->quat[0] = v; break;
      case kVrQuatY: inst->quat[1] = v; break;
      case kVrQuatZ: inst->quat[2] = v; break;
      case kVrQuatW: inst->quat[3] = v; break;
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
      case kVrToolStiffness: v = inst->tool_stiffness; break;
      case kVrTipX: v = inst->tip[0]; break;
      case kVrTipY: v = inst->tip[1]; break;
      case kVrTipZ: v = inst->tip[2]; break;
      case kVrQuatX: v = inst->quat[0]; break;
      case kVrQuatY: v = inst->quat[1]; break;
      case kVrQuatZ: v = inst->quat[2]; break;
      case kVrQuatW: v = inst->quat[3]; break;
      case kVrForceX: v = inst->wrench[0]; break;
      case kVrForceY: v = inst->wrench[1]; break;
      case kVrForceZ: v = inst->wrench[2]; break;
      case kVrTorqueX: v = inst->wrench[3]; break;
      case kVrTorqueY: v = inst->wrench[4]; break;
      case kVrTorqueZ: v = inst->wrench[5]; break;
      case kVrPoseX: v = inst->tip[0]; break;
      case kVrPoseY: v = inst->tip[1]; break;
      case kVrPoseZ: v = inst->tip[2]; break;
      case kVrPoseQx: v = inst->quat[0]; break;
      case kVrPoseQy: v = inst->quat[1]; break;
      case kVrPoseQz: v = inst->quat[2]; break;
      case kVrPoseQw: v = inst->quat[3]; break;
      case kVrMaxDisp: v = inst->max_disp; break;
      case kVrMeanDisp: v = inst->mean_disp; break;
      case kVrTipNodeDisp: v = inst->tip_node_disp; break;
      case kVrStepCount: v = inst->steps; break;
      default:
        return fmi3Error;
    }
    values[n] = v;
  }
  return fmi3OK;
}

}  // extern "C"
