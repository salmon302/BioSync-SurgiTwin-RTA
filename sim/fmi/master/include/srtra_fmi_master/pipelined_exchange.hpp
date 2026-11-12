// SPDX-License-Identifier: MIT
#ifndef SRTA_FMI_MASTER_PIPELINED_EXCHANGE_HPP_
#define SRTA_FMI_MASTER_PIPELINED_EXCHANGE_HPP_

#include <cstddef>
#include <cstdint>
#include <vector>

namespace srtra_fmi_master
{

// Pipelined remote-step exchange (SRS FR-MS-007, VAL-033, plan task 2.8 slice 3).
//
// A remote participant is stepped once per its own step point. The request for step point k is sent at tick k
// (the tick that makes it due). Its reply is read at the next step point of the same participant, so the master
// uses the output of step k at tick k + period (one period stale, zero-order hold). The master never waits for a
// reply inside a tick: it reads the reply that is already available and holds the last received value.
//
// This class holds only the rule. It has no ROS dependency, so the Catch2 test drives it directly. The master node
// uses the same class, so the test and the node share one implementation of the stale-input rule.
class PipelinedExchange
{
public:
  struct Sample
  {
    std::uint64_t step_index = 0;  // which step of this participant produced the value
    double value = 0.0;
    bool valid = false;
  };

  // period_ticks: the participant step period in master ticks (1 for the mechanical FMU, 10 for Pulse).
  explicit PipelinedExchange(std::uint64_t period_ticks);

  // True when the participant has a step point at this tick.
  bool due(std::uint64_t tick) const;

  // Called at a step point before the request is published. Returns the value the master holds for the
  // participant at this exchange point: the reply of the previous step (zero-order hold). The first step has no
  // previous value, so the result is valid = false.
  Sample exchange_point(std::uint64_t tick);

  // Called when the reply for step index step_index arrives. Only the reply for the step in flight is accepted.
  // Returns false for a reply that does not match the step in flight (a stale or duplicate message).
  bool receive_reply(std::uint64_t step_index, double value);

  // The step index in flight (the request sent and not yet answered), or -1 when none.
  std::int64_t in_flight() const { return in_flight_; }

  std::uint64_t requests_sent() const { return requests_sent_; }
  std::uint64_t replies_accepted() const { return replies_accepted_; }
  std::uint64_t replies_rejected() const { return replies_rejected_; }

  // Records that a request for the next step was published. Returns false when a step is still in flight, in which
  // case no request is recorded.
  bool request_sent(std::uint64_t tick);

private:
  std::uint64_t period_ticks_;
  std::int64_t in_flight_ = -1;
  Sample held_;
  std::uint64_t requests_sent_ = 0;
  std::uint64_t replies_accepted_ = 0;
  std::uint64_t replies_rejected_ = 0;
};

}  // namespace srtra_fmi_master

#endif  // SRTA_FMI_MASTER_PIPELINED_EXCHANGE_HPP_
