// SPDX-License-Identifier: MIT
#include "srtra_fmi_master/scheduler.hpp"

#include <stdexcept>
#include <utility>

namespace srtra_fmi_master
{

namespace
{

constexpr double kNsPerSecond = 1.0e9;

}  // namespace

Scheduler::Scheduler(Ns base_step_ns,
  std::vector<ParticipantConfig> participants,
  std::vector<Wire> wires,
  std::vector<Stimulus> stimuli)
: base_step_ns_(base_step_ns),
  participants_(std::move(participants)),
  wires_(std::move(wires)),
  stimuli_(std::move(stimuli))
{
  if (base_step_ns_ <= 0) {
    throw std::invalid_argument("scheduler: base step must be positive");
  }
  if (participants_.empty()) {
    throw std::invalid_argument("scheduler: at least one participant is required");
  }
  for (const ParticipantConfig & p : participants_) {
    if (p.participant == nullptr) {
      throw std::invalid_argument("scheduler: participant pointer is null: " + p.name);
    }
    if (p.period_ns <= 0 || p.period_ns % base_step_ns_ != 0) {
      throw std::invalid_argument(
              "scheduler: period must be a positive multiple of the base step: " + p.name);
    }
    if (p.offset_ns < 0 || p.offset_ns % base_step_ns_ != 0) {
      throw std::invalid_argument(
              "scheduler: offset must be a non-negative multiple of the base step: " + p.name);
    }
    if (p.fixed_step_ns != p.period_ns) {
      throw std::invalid_argument(
              "scheduler: communication step must equal the FMU fixed step: " + p.name);
    }
  }
  for (const Wire & w : wires_) {
    if (w.from_participant >= participants_.size() || w.to_participant >= participants_.size()) {
      throw std::invalid_argument("scheduler: wire refers to a participant index out of range");
    }
    if (w.from_output >= participants_[w.from_participant].output_value_references.size()) {
      throw std::invalid_argument("scheduler: wire refers to an output slot out of range");
    }
  }
  for (const Stimulus & s : stimuli_) {
    if (s.to_participant >= participants_.size()) {
      throw std::invalid_argument("scheduler: stimulus refers to a participant index out of range");
    }
    if (s.value == nullptr) {
      throw std::invalid_argument("scheduler: stimulus function is null");
    }
  }

  next_step_.assign(participants_.size(), 0);
  steps_.assign(participants_.size(), 0);
  outputs_.resize(participants_.size());
  for (std::size_t p = 0; p < participants_.size(); ++p) {
    outputs_[p].assign(participants_[p].output_value_references.size(), 0.0);
  }
}

Status Scheduler::fail(Code code, std::size_t p, Ns t, const char * message, const char * detail)
{
  Status s;
  s.code = code;
  s.participant = p;
  s.time_ns = t;
  s.message = message;
  s.detail = detail;
  return s;
}

Status Scheduler::refresh_outputs(std::size_t p, Ns t)
{
  const ParticipantConfig & cfg = participants_[p];
  for (std::size_t slot = 0; slot < cfg.output_value_references.size(); ++slot) {
    double value = 0.0;
    if (!cfg.participant->get_real(cfg.output_value_references[slot], value)) {
      return fail(Code::kParticipantError, p, t, "get_real failed for an output",
               cfg.participant->last_error());
    }
    outputs_[p][slot] = value;
  }
  return Status{};
}

Status Scheduler::run_step_point(std::size_t p, Ns t)
{
  ParticipantConfig & cfg = participants_[p];
  Participant & fmu = *cfg.participant;

  for (const Stimulus & s : stimuli_) {
    if (s.to_participant == p && !fmu.set_real(s.to_input, s.value(t))) {
      return fail(Code::kParticipantError, p, t, "set_real failed for a stimulus", fmu.last_error());
    }
  }
  for (const Wire & w : wires_) {
    if (w.to_participant == p &&
      !fmu.set_real(w.to_input, outputs_[w.from_participant][w.from_output]))
    {
      return fail(Code::kParticipantError, p, t, "set_real failed for a wired input", fmu.last_error());
    }
  }

  const double t_s = static_cast<double>(t) / kNsPerSecond;
  const double h_s = static_cast<double>(cfg.period_ns) / kNsPerSecond;
  if (!fmu.do_step(t_s, h_s)) {
    return fail(Code::kParticipantError, p, t, "fmi3DoStep failed", fmu.last_error());
  }
  next_step_[p] += cfg.period_ns;
  ++steps_[p];
  return refresh_outputs(p, t);
}

Status Scheduler::initialize()
{
  if (latched_) {
    return latched_status_;
  }
  for (std::size_t p = 0; p < participants_.size(); ++p) {
    Participant & fmu = *participants_[p].participant;
    if (!fmu.initialize(0.0)) {
      latched_ = true;
      latched_status_ = fail(Code::kParticipantError, p, 0, "initialization failed", fmu.last_error());
      return latched_status_;
    }
    next_step_[p] = participants_[p].offset_ns;
    steps_[p] = 0;
  }
  for (std::size_t p = 0; p < participants_.size(); ++p) {
    Status s = refresh_outputs(p, 0);
    if (!s.ok()) {
      latched_ = true;
      latched_status_ = s;
      return s;
    }
  }
  expected_tick_ = 0;
  initialized_ = true;
  return Status{};
}

Status Scheduler::advance_to(Ns t_ns)
{
  if (latched_) {
    return latched_status_;
  }
  if (!initialized_) {
    return fail(Code::kNotInitialized, 0, t_ns, "advance_to called before initialize", "");
  }
  if (t_ns != expected_tick_) {
    return fail(Code::kTimeError, 0, t_ns, "tick is not the next base tick", "");
  }
  for (std::size_t p = 0; p < participants_.size(); ++p) {
    if (next_step_[p] != t_ns) {
      continue;
    }
    Status s = run_step_point(p, t_ns);
    if (!s.ok()) {
      latched_ = true;
      latched_status_ = s;
      return s;
    }
  }
  expected_tick_ += base_step_ns_;
  return Status{};
}

Status Scheduler::reset()
{
  for (std::size_t p = 0; p < participants_.size(); ++p) {
    Participant & fmu = *participants_[p].participant;
    if (!fmu.reset()) {
      latched_ = true;
      latched_status_ = fail(Code::kParticipantError, p, expected_tick_, "reset failed", fmu.last_error());
      return latched_status_;
    }
  }
  initialized_ = false;
  latched_ = false;
  latched_status_ = Status{};
  return initialize();
}

}  // namespace srtra_fmi_master
