// SPDX-License-Identifier: MIT
#include "srtra_bridge/bridge_node.hpp"

#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

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

namespace srtra_bridge
{

namespace
{

constexpr double kTwoPi = 6.283185307179586;
constexpr double kPathHz = 0.2;
constexpr std::int64_t kNanosPerSecond = 1000000000LL;
constexpr std::chrono::seconds kSubscriberWaitLimit(30);

// Replay schema: tick, time_s, pos_x..quat_w (7), force_x..torque_z (6), then mode_0..mode_(n-1).
constexpr std::size_t kReplayFixedColumns = 15U;
constexpr double kReplayTimeToleranceS = 1e-6;
constexpr double kReplayUnitNormTolerance = 1e-6;

using Clock = std::chrono::steady_clock;

std::vector<std::string> split_csv_line(const std::string & line)
{
  std::vector<std::string> fields;
  std::size_t start = 0U;
  while (true) {
    const std::size_t comma = line.find(',', start);
    if (comma == std::string::npos) {
      fields.push_back(line.substr(start));
      break;
    }
    fields.push_back(line.substr(start, comma - start));
    start = comma + 1U;
  }
  return fields;
}

void strip_cr(std::string & line)
{
  if (!line.empty() && line.back() == '\r') {
    line.pop_back();
  }
}

// Windows tools often write a UTF-8 byte-order mark at the start of a CSV file.
void strip_utf8_bom(std::string & line)
{
  if (line.size() >= 3U && line.compare(0U, 3U, "\xEF\xBB\xBF") == 0) {
    line.erase(0U, 3U);
  }
}

double parse_finite(const std::string & text, std::size_t line_no, const std::string & column)
{
  const std::string where = "replay line " + std::to_string(line_no) + " column " + column;
  char * end = nullptr;
  const double value = std::strtod(text.c_str(), &end);
  if (text.empty() || end == text.c_str() || *end != '\0') {
    throw std::runtime_error(where + " is not a number: '" + text + "'");
  }
  if (!std::isfinite(value)) {
    throw std::runtime_error(where + " is not finite");
  }
  return value;
}

// Waits until a target time on the steady clock.
//
// Preferred mechanism: a high-resolution waitable timer (CreateWaitableTimerExW with
// CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, Windows 10 1803 or later). The timer is created once
// in the constructor and re-armed with a relative due time per tick, so the loop does not
// allocate.
//
// Fallback mechanism: std::this_thread::sleep_until with timeBeginPeriod(1) raising the system
// timer resolution from about 15.6 ms to 1 ms for the lifetime of this object. This is the
// slice 1 path. It is used when the high-resolution timer is not requested or cannot be created.
class TickWaiter
{
public:
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

}  // namespace

BridgeNode::BridgeNode(const rclcpp::NodeOptions & options)
: Node("srtra_bridge", options),
  rate_hz_(declare_parameter<std::int64_t>("rate_hz", 500)),
  duration_s_(declare_parameter<std::int64_t>("duration_s", 0)),
  period_ns_(0),
  reference_frame_(declare_parameter<std::string>("reference_frame", "srtra_world")),
  mesh_node_count_(0U),
  wait_for_subscribers_(declare_parameter<bool>("wait_for_subscribers", true)),
  prefer_high_resolution_(false),
  replay_(false),
  replay_loop_(false),
  mode_count_(kModeCount),
  late_ticks_(0U)
{
  if (rate_hz_ < kMinRateHz || rate_hz_ > kMaxRateHz) {
    throw std::invalid_argument("rate_hz must be in [1, 1000]");
  }
  if (duration_s_ < 0) {
    throw std::invalid_argument("duration_s must be 0 (unbounded) or positive");
  }
  const std::int64_t node_count = declare_parameter<std::int64_t>("mesh_node_count", 4096);
  if (node_count <= 0 || node_count > static_cast<std::int64_t>(UINT32_MAX)) {
    throw std::invalid_argument("mesh_node_count must be in [1, 4294967295]");
  }
  mesh_node_count_ = static_cast<std::uint32_t>(node_count);
  period_ns_ = kNanosPerSecond / rate_hz_;

  const std::string timer_mode = declare_parameter<std::string>("timer_mode", "high_resolution");
  if (timer_mode == "high_resolution") {
    prefer_high_resolution_ = true;
  } else if (timer_mode == "sleep") {
    prefer_high_resolution_ = false;
  } else {
    throw std::invalid_argument("timer_mode must be high_resolution or sleep");
  }

  const std::string source = declare_parameter<std::string>("source", "synthetic");
  replay_file_ = declare_parameter<std::string>("replay_file", "");
  replay_loop_ = declare_parameter<bool>("replay_loop", false);
  if (source == "replay") {
    if (replay_file_.empty()) {
      throw std::invalid_argument("source=replay requires replay_file");
    }
    replay_ = true;
    load_replay_file();
  } else if (source != "synthetic") {
    throw std::invalid_argument("source must be synthetic or replay");
  }

  const rclcpp::QoS qos = rclcpp::QoS(rclcpp::KeepLast(kQueueDepth)).reliable();
  pose_pub_ = create_publisher<geometry_msgs::msg::PoseStamped>(kTopicToolTipPose, qos);
  wrench_pub_ = create_publisher<geometry_msgs::msg::WrenchStamped>(kTopicToolWrench, qos);
  mesh_pub_ = create_publisher<srtra_bridge::msg::MeshDeformationState>(kTopicMeshDeformation, qos);

  pose_msg_.header.frame_id = reference_frame_;
  wrench_msg_.header.frame_id = reference_frame_;
  mesh_msg_.header.frame_id = reference_frame_;
  mesh_msg_.reference_frame = reference_frame_;
  mesh_msg_.node_count = mesh_node_count_;
  mesh_msg_.mode_coefficients.assign(mode_count_, 0.0F);

  RCLCPP_INFO(
    get_logger(),
    "bridge configured: rate_hz=%lld duration_s=%lld reference_frame=%s mesh_node_count=%u "
    "timer_mode=%s source=%s mode_count=%zu",
    static_cast<long long>(rate_hz_), static_cast<long long>(duration_s_), reference_frame_.c_str(),
    mesh_node_count_, timer_mode.c_str(), source.c_str(), mode_count_);
  if (replay_) {
    RCLCPP_INFO(
      get_logger(), "replay source: file=%s rows=%zu loop=%s", replay_file_.c_str(),
      replay_rows_.size(), replay_loop_ ? "true" : "false");
  }
}

// Reads the capture in two passes: the first counts data rows so the table is reserved once, and
// the second parses and validates each row. Validation covers the header, the tick index (0 to
// N-1, consecutive), the time grid (time_s equals tick / rate_hz within 1 us), finite values, and
// a unit quaternion within 1e-6.
void BridgeNode::load_replay_file()
{
  std::ifstream counting(replay_file_);
  if (!counting) {
    throw std::runtime_error("cannot open replay_file: " + replay_file_);
  }
  std::string line;
  if (!std::getline(counting, line)) {
    throw std::runtime_error("replay_file is empty: " + replay_file_);
  }
  strip_utf8_bom(line);
  strip_cr(line);
  const std::vector<std::string> columns = split_csv_line(line);
  if (columns.size() <= kReplayFixedColumns ||
    columns.size() - kReplayFixedColumns > kModeCountMax)
  {
    throw std::runtime_error(
            "replay header must have 1 to 16 mode columns after the 15 fixed columns");
  }
  const std::vector<std::string> fixed = {
    "tick", "time_s", "pos_x", "pos_y", "pos_z", "quat_x", "quat_y", "quat_z", "quat_w",
    "force_x", "force_y", "force_z", "torque_x", "torque_y", "torque_z"};
  for (std::size_t c = 0U; c < kReplayFixedColumns; ++c) {
    if (columns[c] != fixed[c]) {
      throw std::runtime_error("replay header column " + std::to_string(c) + " must be " + fixed[c]);
    }
  }
  for (std::size_t c = kReplayFixedColumns; c < columns.size(); ++c) {
    const std::string expected = "mode_" + std::to_string(c - kReplayFixedColumns);
    if (columns[c] != expected) {
      throw std::runtime_error("replay header column " + std::to_string(c) + " must be " + expected);
    }
  }
  mode_count_ = columns.size() - kReplayFixedColumns;

  std::size_t data_rows = 0U;
  while (std::getline(counting, line)) {
    strip_cr(line);
    if (!line.empty()) {
      ++data_rows;
    }
  }
  if (data_rows == 0U) {
    throw std::runtime_error("replay_file has no data rows: " + replay_file_);
  }
  replay_rows_.clear();
  replay_rows_.reserve(data_rows);

  std::ifstream in(replay_file_);
  std::getline(in, line);
  std::size_t line_no = 1U;
  const double rate = static_cast<double>(rate_hz_);
  while (std::getline(in, line)) {
    ++line_no;
    strip_cr(line);
    if (line.empty()) {
      continue;
    }
    const std::vector<std::string> f = split_csv_line(line);
    if (f.size() != columns.size()) {
      throw std::runtime_error(
              "replay line " + std::to_string(line_no) + " has " + std::to_string(f.size()) +
              " fields, expected " + std::to_string(columns.size()));
    }
    const std::size_t index = replay_rows_.size();
    char * end = nullptr;
    const unsigned long long tick = std::strtoull(f[0].c_str(), &end, 10);
    if (f[0].empty() || *end != '\0' || tick != static_cast<unsigned long long>(index)) {
      throw std::runtime_error(
              "replay line " + std::to_string(line_no) + " tick must be " + std::to_string(index));
    }
    const double time_s = parse_finite(f[1], line_no, "time_s");
    if (std::fabs(time_s - static_cast<double>(index) / rate) > kReplayTimeToleranceS) {
      throw std::runtime_error(
              "replay line " + std::to_string(line_no) + " time_s is off the " +
              std::to_string(rate_hz_) + " Hz grid");
    }

    ReplayRow row{};
    row.position = {
      parse_finite(f[2], line_no, "pos_x"), parse_finite(f[3], line_no, "pos_y"),
      parse_finite(f[4], line_no, "pos_z")};
    row.orientation = {
      parse_finite(f[5], line_no, "quat_x"), parse_finite(f[6], line_no, "quat_y"),
      parse_finite(f[7], line_no, "quat_z"), parse_finite(f[8], line_no, "quat_w")};
    const double norm2 = row.orientation[0] * row.orientation[0] +
      row.orientation[1] * row.orientation[1] + row.orientation[2] * row.orientation[2] +
      row.orientation[3] * row.orientation[3];
    if (std::fabs(norm2 - 1.0) > kReplayUnitNormTolerance) {
      throw std::runtime_error("replay line " + std::to_string(line_no) + " quaternion is not unit");
    }
    row.force = {
      parse_finite(f[9], line_no, "force_x"), parse_finite(f[10], line_no, "force_y"),
      parse_finite(f[11], line_no, "force_z")};
    row.torque = {
      parse_finite(f[12], line_no, "torque_x"), parse_finite(f[13], line_no, "torque_y"),
      parse_finite(f[14], line_no, "torque_z")};
    for (std::size_t k = 0U; k < mode_count_; ++k) {
      const std::size_t c = kReplayFixedColumns + k;
      row.modes[k] = static_cast<float>(parse_finite(f[c], line_no, columns[c]));
    }
    replay_rows_.push_back(row);
  }
}

void BridgeNode::fill_tick(std::uint64_t tick, const builtin_interfaces::msg::Time & stamp)
{
  if (replay_) {
    fill_replay_tick(tick, stamp);
    return;
  }

  const double t = static_cast<double>(tick) / static_cast<double>(rate_hz_);
  const double w = kTwoPi * kPathHz * t;

  const double yaw = 0.3 * std::sin(w);
  pose_msg_.header.stamp = stamp;
  pose_msg_.pose.position.x = 0.02 * std::sin(w);
  pose_msg_.pose.position.y = 0.01 * std::sin(2.0 * w);
  pose_msg_.pose.position.z = 0.10 + 0.005 * std::cos(w);
  pose_msg_.pose.orientation.x = 0.0;
  pose_msg_.pose.orientation.y = 0.0;
  pose_msg_.pose.orientation.z = std::sin(0.5 * yaw);
  pose_msg_.pose.orientation.w = std::cos(0.5 * yaw);

  wrench_msg_.header.stamp = stamp;
  wrench_msg_.wrench.force.x = 1.5 * std::sin(w + 0.5);
  wrench_msg_.wrench.force.y = 0.8 * std::cos(w);
  wrench_msg_.wrench.force.z = 2.0 + 0.5 * std::sin(2.0 * w);
  wrench_msg_.wrench.torque.x = 0.02 * std::cos(w);
  wrench_msg_.wrench.torque.y = 0.01 * std::sin(2.0 * w);
  wrench_msg_.wrench.torque.z = 0.005 * std::sin(w + 1.0);

  mesh_msg_.header.stamp = stamp;
  mesh_msg_.tick = tick;
  for (std::size_t k = 0U; k < kModeCount; ++k) {
    const double f = static_cast<double>(k + 1U);
    mesh_msg_.mode_coefficients[k] = static_cast<float>((0.002 / f) * std::sin(f * w + 0.3 * f));
  }
}

// The replay row index is tick modulo the row count, so loop mode repeats the capture while the
// tick index in the messages keeps counting up. The message stamp is the node clock at publish,
// as in synthetic mode. The capture time_s is validated at load and is not published.
void BridgeNode::fill_replay_tick(std::uint64_t tick, const builtin_interfaces::msg::Time & stamp)
{
  const ReplayRow & row = replay_rows_[static_cast<std::size_t>(tick % replay_rows_.size())];

  pose_msg_.header.stamp = stamp;
  pose_msg_.pose.position.x = row.position[0];
  pose_msg_.pose.position.y = row.position[1];
  pose_msg_.pose.position.z = row.position[2];
  pose_msg_.pose.orientation.x = row.orientation[0];
  pose_msg_.pose.orientation.y = row.orientation[1];
  pose_msg_.pose.orientation.z = row.orientation[2];
  pose_msg_.pose.orientation.w = row.orientation[3];

  wrench_msg_.header.stamp = stamp;
  wrench_msg_.wrench.force.x = row.force[0];
  wrench_msg_.wrench.force.y = row.force[1];
  wrench_msg_.wrench.force.z = row.force[2];
  wrench_msg_.wrench.torque.x = row.torque[0];
  wrench_msg_.wrench.torque.y = row.torque[1];
  wrench_msg_.wrench.torque.z = row.torque[2];

  mesh_msg_.header.stamp = stamp;
  mesh_msg_.tick = tick;
  for (std::size_t k = 0U; k < mode_count_; ++k) {
    mesh_msg_.mode_coefficients[k] = row.modes[k];
  }
}

void BridgeNode::publish_tick()
{
  pose_pub_->publish(pose_msg_);
  wrench_pub_->publish(wrench_msg_);
  mesh_pub_->publish(mesh_msg_);
}

void BridgeNode::wait_for_matched_subscribers()
{
  const Clock::time_point deadline = Clock::now() + kSubscriberWaitLimit;
  while (rclcpp::ok() &&
    (pose_pub_->get_subscription_count() == 0U || wrench_pub_->get_subscription_count() == 0U ||
    mesh_pub_->get_subscription_count() == 0U))
  {
    if (Clock::now() > deadline) {
      throw std::runtime_error("no subscriber matched all three topics within 30 s");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  RCLCPP_INFO(get_logger(), "matched subscribers on all three topics, starting tick schedule");
}

std::uint64_t BridgeNode::run()
{
  const std::chrono::nanoseconds period(period_ns_);
  const std::chrono::nanoseconds limit(static_cast<std::int64_t>(duration_s_) * kNanosPerSecond);

  if (wait_for_subscribers_) {
    wait_for_matched_subscribers();
  }

  const TickWaiter waiter(prefer_high_resolution_);
  RCLCPP_INFO(get_logger(), "tick timer mechanism: %s", waiter.mechanism());

  const Clock::time_point start = Clock::now();
  Clock::time_point next = start;
  std::uint64_t tick = 0U;

  while (rclcpp::ok()) {
    if (duration_s_ > 0 && (next - start) >= limit) {
      break;
    }
    if (replay_ && !replay_loop_ && tick >= replay_rows_.size()) {
      break;
    }
    waiter.wait_until(next);
    if (!rclcpp::ok()) {
      break;
    }
    if (Clock::now() - next >= period) {
      ++late_ticks_;
    }

    const rclcpp::Time now = get_clock()->now();
    const builtin_interfaces::msg::Time stamp = now;
    fill_tick(tick, stamp);
    publish_tick();

    ++tick;
    next += period;
  }

  const double elapsed_s =
    std::chrono::duration<double>(Clock::now() - start).count();
  RCLCPP_INFO(
    get_logger(),
    "publish loop finished: ticks=%llu late_ticks=%llu elapsed_s=%.3f timer=%s",
    static_cast<unsigned long long>(tick), static_cast<unsigned long long>(late_ticks_),
    elapsed_s, waiter.mechanism());
  return tick;
}

}  // namespace srtra_bridge
