// SPDX-License-Identifier: MIT
#ifndef SRTA_FMI_MASTER_PARTICIPANT_HPP_
#define SRTA_FMI_MASTER_PARTICIPANT_HPP_

#include <cstdint>

namespace srtra_fmi_master
{

// Co-Simulation participant as seen by the scheduler. The FMU adapter (fmu_participant.hpp) and the
// test fake implement it. Every method returns false on failure, and last_error() names the cause.
// last_error() returns a pointer that stays valid until the next call on the same participant.
class Participant
{
public:
  virtual ~Participant() = default;

  // Enter and exit initialization mode with the given start time (seconds).
  virtual bool initialize(double start_time_s) = 0;
  virtual bool set_real(std::uint32_t value_reference, double value) = 0;
  virtual bool get_real(std::uint32_t value_reference, double & value) = 0;
  // One communication step: fmi3DoStep(current_time_s, step_s).
  virtual bool do_step(double current_time_s, double step_s) = 0;
  // fmi3Reset. The scheduler calls initialize() again after a successful reset.
  virtual bool reset() = 0;
  virtual const char * last_error() const = 0;
};

}  // namespace srtra_fmi_master

#endif  // SRTA_FMI_MASTER_PARTICIPANT_HPP_
