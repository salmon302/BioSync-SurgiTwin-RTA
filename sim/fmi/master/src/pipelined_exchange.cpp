// SPDX-License-Identifier: MIT
#include "srtra_fmi_master/pipelined_exchange.hpp"

namespace srtra_fmi_master
{

PipelinedExchange::PipelinedExchange(std::uint64_t period_ticks)
: period_ticks_(period_ticks == 0 ? 1 : period_ticks)
{
}

bool PipelinedExchange::due(std::uint64_t tick) const
{
  return tick % period_ticks_ == 0;
}

PipelinedExchange::Sample PipelinedExchange::exchange_point(std::uint64_t tick)
{
  (void)tick;
  // The held value is the last accepted reply. It is returned unchanged until the next reply is accepted.
  return held_;
}

bool PipelinedExchange::request_sent(std::uint64_t tick)
{
  (void)tick;
  if (in_flight_ >= 0) {
    // One step in flight per participant. A second request is refused, so no step is ever skipped or doubled.
    return false;
  }
  in_flight_ = static_cast<std::int64_t>(requests_sent_);
  ++requests_sent_;
  return true;
}

bool PipelinedExchange::receive_reply(std::uint64_t step_index, double value)
{
  if (in_flight_ < 0 || step_index != static_cast<std::uint64_t>(in_flight_)) {
    ++replies_rejected_;
    return false;
  }
  held_.step_index = step_index;
  held_.value = value;
  held_.valid = true;
  in_flight_ = -1;
  ++replies_accepted_;
  return true;
}

}  // namespace srtra_fmi_master
