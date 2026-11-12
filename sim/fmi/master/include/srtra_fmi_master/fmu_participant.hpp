// SPDX-License-Identifier: MIT
#ifndef SRTA_FMI_MASTER_FMU_PARTICIPANT_HPP_
#define SRTA_FMI_MASTER_FMU_PARTICIPANT_HPP_

#include <memory>
#include <string>

#include "srtra_fmi_master/participant.hpp"

namespace srtra_fmi_master
{

// FMI 3.0 Co-Simulation FMU loaded from its unzipped directory (Windows x64 binary). The FMI types stay
// inside fmu_participant.cpp, so the public headers do not include the FMI headers.
class FmuParticipant final : public Participant
{
public:
  // dll_path: binaries/x86_64-windows/<model>.dll inside the unzipped FMU. instantiation_token is the
  // instantiationToken of modelDescription.xml. Returns nullptr on failure and sets error.
  // resource_dir: the unzipped FMU "resources" directory (FMI 3.0 resourcePath, with a trailing separator).
  // An FMU that starts a worker from its resources (mechanical_sofa) needs it; others accept "".
  static std::unique_ptr<FmuParticipant> create(
    const std::string & dll_path,
    const std::string & instantiation_token,
    const std::string & instance_name,
    std::string & error,
    const std::string & resource_dir = "");

  ~FmuParticipant() override;
  FmuParticipant(const FmuParticipant &) = delete;
  FmuParticipant & operator=(const FmuParticipant &) = delete;

  bool initialize(double start_time_s) override;
  bool set_real(std::uint32_t value_reference, double value) override;
  bool get_real(std::uint32_t value_reference, double & value) override;
  bool do_step(double current_time_s, double step_s) override;
  bool reset() override;
  const char * last_error() const override;

private:
  struct Impl;
  explicit FmuParticipant(std::unique_ptr<Impl> impl);
  std::unique_ptr<Impl> impl_;
};

}  // namespace srtra_fmi_master

#endif  // SRTA_FMI_MASTER_FMU_PARTICIPANT_HPP_
