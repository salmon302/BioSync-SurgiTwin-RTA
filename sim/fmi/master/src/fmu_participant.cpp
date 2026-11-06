// SPDX-License-Identifier: MIT
#include "srtra_fmi_master/fmu_participant.hpp"

#include <cmath>
#include <cstdio>
#include <string>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include "fmi3PlatformTypes.h"
#include "fmi3FunctionTypes.h"

namespace srtra_fmi_master
{

namespace
{

constexpr double kTimeTolerance = 1.0e-9;

void log_fmu_message(fmi3InstanceEnvironment, fmi3Status status, fmi3String category, fmi3String message)
{
  std::fprintf(stderr, "[fmu %d %s] %s\n", static_cast<int>(status),
    category != nullptr ? category : "", message != nullptr ? message : "");
}

}  // namespace

struct FmuParticipant::Impl
{
  HMODULE module = nullptr;
  fmi3InstantiateCoSimulationTYPE * instantiate = nullptr;
  fmi3FreeInstanceTYPE * free_instance = nullptr;
  fmi3EnterInitializationModeTYPE * enter_initialization = nullptr;
  fmi3ExitInitializationModeTYPE * exit_initialization = nullptr;
  fmi3TerminateTYPE * terminate = nullptr;
  fmi3ResetTYPE * reset = nullptr;
  fmi3SetFloat64TYPE * set_float64 = nullptr;
  fmi3GetFloat64TYPE * get_float64 = nullptr;
  fmi3DoStepTYPE * do_step = nullptr;
  fmi3Instance instance = nullptr;
  std::string error;

  ~Impl()
  {
    if (instance != nullptr && free_instance != nullptr) {
      free_instance(instance);
    }
    if (module != nullptr) {
      FreeLibrary(module);
    }
  }

  bool fail(const std::string & what)
  {
    error = what;
    return false;
  }

  bool ok(fmi3Status status, const char * what)
  {
    if (status > fmi3Warning) {
      error = std::string(what) + " returned FMI status " + std::to_string(static_cast<int>(status));
      return false;
    }
    return true;
  }
};

FmuParticipant::FmuParticipant(std::unique_ptr<Impl> impl)
: impl_(std::move(impl))
{
}

FmuParticipant::~FmuParticipant() = default;

std::unique_ptr<FmuParticipant> FmuParticipant::create(
  const std::string & dll_path,
  const std::string & instantiation_token,
  const std::string & instance_name,
  std::string & error)
{
  auto impl = std::make_unique<Impl>();
  impl->module = LoadLibraryA(dll_path.c_str());
  if (impl->module == nullptr) {
    error = "LoadLibrary failed for " + dll_path;
    return nullptr;
  }

  auto resolve = [&](const char * name) -> FARPROC {
      FARPROC proc = GetProcAddress(impl->module, name);
      if (proc == nullptr) {
        error = std::string("missing FMI 3.0 export ") + name;
      }
      return proc;
    };

  FARPROC version = resolve("fmi3GetVersion");
  FARPROC inst = resolve("fmi3InstantiateCoSimulation");
  FARPROC freei = resolve("fmi3FreeInstance");
  FARPROC enter = resolve("fmi3EnterInitializationMode");
  FARPROC exitm = resolve("fmi3ExitInitializationMode");
  FARPROC term = resolve("fmi3Terminate");
  FARPROC rst = resolve("fmi3Reset");
  FARPROC setf = resolve("fmi3SetFloat64");
  FARPROC getf = resolve("fmi3GetFloat64");
  FARPROC step = resolve("fmi3DoStep");
  if (!error.empty()) {
    return nullptr;
  }
  using VersionFn = fmi3GetVersionTYPE *;
  const char * fmi_version = reinterpret_cast<VersionFn>(version)();
  if (fmi_version == nullptr || std::string(fmi_version) != "3.0") {
    error = std::string("FMU reports FMI version ") + (fmi_version != nullptr ? fmi_version : "null");
    return nullptr;
  }

  impl->instantiate = reinterpret_cast<fmi3InstantiateCoSimulationTYPE *>(inst);
  impl->free_instance = reinterpret_cast<fmi3FreeInstanceTYPE *>(freei);
  impl->enter_initialization = reinterpret_cast<fmi3EnterInitializationModeTYPE *>(enter);
  impl->exit_initialization = reinterpret_cast<fmi3ExitInitializationModeTYPE *>(exitm);
  impl->terminate = reinterpret_cast<fmi3TerminateTYPE *>(term);
  impl->reset = reinterpret_cast<fmi3ResetTYPE *>(rst);
  impl->set_float64 = reinterpret_cast<fmi3SetFloat64TYPE *>(setf);
  impl->get_float64 = reinterpret_cast<fmi3GetFloat64TYPE *>(getf);
  impl->do_step = reinterpret_cast<fmi3DoStepTYPE *>(step);

  impl->instance = impl->instantiate(
    instance_name.c_str(),
    instantiation_token.c_str(),
    "",
    fmi3False,
    fmi3False,
    fmi3False,
    fmi3False,
    nullptr,
    0,
    nullptr,
    log_fmu_message,
    nullptr);
  if (impl->instance == nullptr) {
    error = "fmi3InstantiateCoSimulation failed (instantiation token or resource check)";
    return nullptr;
  }
  return std::unique_ptr<FmuParticipant>(new FmuParticipant(std::move(impl)));
}

bool FmuParticipant::initialize(double start_time_s)
{
  Impl & m = *impl_;
  if (!m.ok(m.enter_initialization(m.instance, fmi3False, 0.0, start_time_s, fmi3False, 0.0),
    "fmi3EnterInitializationMode"))
  {
    return false;
  }
  return m.ok(m.exit_initialization(m.instance), "fmi3ExitInitializationMode");
}

bool FmuParticipant::set_real(std::uint32_t value_reference, double value)
{
  Impl & m = *impl_;
  fmi3ValueReference vr = value_reference;
  fmi3Float64 v = value;
  return m.ok(m.set_float64(m.instance, &vr, 1, &v, 1), "fmi3SetFloat64");
}

bool FmuParticipant::get_real(std::uint32_t value_reference, double & value)
{
  Impl & m = *impl_;
  fmi3ValueReference vr = value_reference;
  fmi3Float64 v = 0.0;
  if (!m.ok(m.get_float64(m.instance, &vr, 1, &v, 1), "fmi3GetFloat64")) {
    return false;
  }
  value = v;
  return true;
}

bool FmuParticipant::do_step(double current_time_s, double step_s)
{
  Impl & m = *impl_;
  fmi3Boolean event = fmi3False;
  fmi3Boolean terminate = fmi3False;
  fmi3Boolean early = fmi3False;
  fmi3Float64 last = 0.0;
  if (!m.ok(m.do_step(m.instance, current_time_s, step_s, fmi3True, &event, &terminate, &early, &last),
    "fmi3DoStep"))
  {
    return false;
  }
  if (terminate) {
    return m.fail("FMU requested termination during fmi3DoStep");
  }
  if (std::fabs(last - (current_time_s + step_s)) > kTimeTolerance) {
    return m.fail("fmi3DoStep lastSuccessfulTime does not match the requested end time");
  }
  return true;
}

bool FmuParticipant::reset()
{
  Impl & m = *impl_;
  return m.ok(m.reset(m.instance), "fmi3Reset");
}

const char * FmuParticipant::last_error() const
{
  return impl_->error.c_str();
}

}  // namespace srtra_fmi_master
