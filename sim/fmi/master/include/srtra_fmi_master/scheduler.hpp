// SPDX-License-Identifier: MIT
#ifndef SRTA_FMI_MASTER_SCHEDULER_HPP_
#define SRTA_FMI_MASTER_SCHEDULER_HPP_

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "srtra_fmi_master/participant.hpp"

namespace srtra_fmi_master
{

// Integer nanoseconds on the master timeline. Step points are exact multiples of the base step, so
// the schedule has no floating-point drift. Conversion to seconds happens only at the FMU boundary.
using Ns = std::int64_t;

struct ParticipantConfig
{
  std::string name;
  Participant * participant = nullptr;
  // Communication step: the h passed to fmi3DoStep. Must equal fixed_step_ns (the FMU fixed step).
  Ns period_ns = 0;
  // First step point on the master timeline. A non-negative multiple of the base step.
  Ns offset_ns = 0;
  Ns fixed_step_ns = 0;
  // Value references of the outputs that the master caches after each step point (published state).
  std::vector<std::uint32_t> output_value_references;
};

// Scheduled-variable wire. At the consumer's step point, the input receives the producer output cached
// at the producer's most recent step point (zero-order hold). The producer is not stepped for the wire.
struct Wire
{
  std::size_t from_participant = 0;
  std::size_t from_output = 0;  // index into the producer's output_value_references
  std::size_t to_participant = 0;
  std::uint32_t to_input = 0;
};

// Master-side input profile. The function is evaluated at the consumer's step point.
using StimulusFn = double (*)(Ns t_ns);

struct Stimulus
{
  std::size_t to_participant = 0;
  std::uint32_t to_input = 0;
  StimulusFn value = nullptr;
};

enum class Code
{
  kOk,
  kNotInitialized,
  kTimeError,
  kParticipantError,
};

// Result of a scheduler call. message is a static literal. detail is the participant last_error() text
// (valid until that participant is called again) or an empty string.
struct Status
{
  Code code = Code::kOk;
  std::size_t participant = 0;
  Ns time_ns = 0;
  const char * message = "";
  const char * detail = "";

  bool ok() const { return code == Code::kOk; }
};

// Scheduler for scheduled-variable co-simulation with one fixed master base step.
//
// advance_to(t) must be called with t = 0, base, 2 base, ... in order. For each participant whose step
// point equals t, in participant index order, the scheduler sets the stimuli, sets the wired inputs from
// the cached outputs, calls do_step(t, period), then caches the participant outputs. A failure latches:
// every later call returns the same failure until reset().
class Scheduler
{
public:
  // Throws std::invalid_argument if the configuration breaks the schedule rules (see README).
  Scheduler(Ns base_step_ns,
    std::vector<ParticipantConfig> participants,
    std::vector<Wire> wires,
    std::vector<Stimulus> stimuli);

  Status initialize();
  Status advance_to(Ns t_ns);
  // Resets every participant and initializes again. Clears the timeline and the step counts.
  Status reset();

  Ns base_step_ns() const { return base_step_ns_; }
  Ns next_tick_ns() const { return expected_tick_; }
  std::size_t participant_count() const { return participants_.size(); }
  std::size_t output_count(std::size_t p) const { return outputs_[p].size(); }
  std::uint64_t step_count(std::size_t p) const { return steps_[p]; }
  double output(std::size_t p, std::size_t slot) const { return outputs_[p][slot]; }
  const std::string & participant_name(std::size_t p) const { return participants_[p].name; }

private:
  Status fail(Code code, std::size_t p, Ns t, const char * message, const char * detail);
  Status refresh_outputs(std::size_t p, Ns t);
  Status run_step_point(std::size_t p, Ns t);

  Ns base_step_ns_;
  std::vector<ParticipantConfig> participants_;
  std::vector<Wire> wires_;
  std::vector<Stimulus> stimuli_;
  std::vector<Ns> next_step_;
  std::vector<std::uint64_t> steps_;
  std::vector<std::vector<double>> outputs_;
  Ns expected_tick_ = 0;
  bool initialized_ = false;
  bool latched_ = false;
  Status latched_status_;
};

}  // namespace srtra_fmi_master

#endif  // SRTA_FMI_MASTER_SCHEDULER_HPP_
