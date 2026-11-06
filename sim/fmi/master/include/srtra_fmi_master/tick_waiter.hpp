// SPDX-License-Identifier: MIT
#ifndef SRTA_FMI_MASTER_TICK_WAITER_HPP_
#define SRTA_FMI_MASTER_TICK_WAITER_HPP_

#include <chrono>
#include <thread>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <mmsystem.h>
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif
#endif

namespace srtra_fmi_master
{

// Waits until a target time on the steady clock. Same mechanism as the bridge node (sim/bridge/src/bridge_node.cpp):
// a high-resolution waitable timer created once, or sleep_until with timeBeginPeriod(1) as the fallback.
class TickWaiter
{
public:
  using Clock = std::chrono::steady_clock;

  explicit TickWaiter(bool prefer_high_resolution)
  {
#ifdef _WIN32
    if (prefer_high_resolution) {
      timer_ = CreateWaitableTimerExW(
        nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
    }
    if (timer_ == nullptr) {
      timeBeginPeriod(1U);
      timer_resolution_raised_ = true;
    }
#else
    (void)prefer_high_resolution;
#endif
  }

  ~TickWaiter()
  {
#ifdef _WIN32
    if (timer_ != nullptr) {
      CloseHandle(timer_);
    }
    if (timer_resolution_raised_) {
      timeEndPeriod(1U);
    }
#endif
  }

  TickWaiter(const TickWaiter &) = delete;
  TickWaiter & operator=(const TickWaiter &) = delete;

  const char * mechanism() const
  {
#ifdef _WIN32
    if (timer_ != nullptr) {
      return "high_resolution_waitable_timer";
    }
    return "sleep_until_timeBeginPeriod_1ms";
#else
    return "sleep_until";
#endif
  }

  void wait_until(Clock::time_point target) const
  {
#ifdef _WIN32
    if (timer_ != nullptr) {
      while (Clock::now() < target) {
        const std::int64_t remaining_100ns =
          std::chrono::duration_cast<std::chrono::nanoseconds>(target - Clock::now()).count() / 100;
        LARGE_INTEGER due;
        due.QuadPart = -(remaining_100ns > 0 ? remaining_100ns : 1);
        if (!SetWaitableTimer(timer_, &due, 0, nullptr, nullptr, FALSE)) {
          std::this_thread::sleep_until(target);
          return;
        }
        WaitForSingleObject(timer_, INFINITE);
      }
      return;
    }
#endif
    std::this_thread::sleep_until(target);
  }

private:
#ifdef _WIN32
  HANDLE timer_ = nullptr;
  bool timer_resolution_raised_ = false;
#endif
};

}  // namespace srtra_fmi_master

#endif  // SRTA_FMI_MASTER_TICK_WAITER_HPP_
