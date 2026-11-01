// Derived from VisionPilot e7e5c614832f175f1f9f10a0d0c0df2559ff2c38 (Apache-2.0).
// Modified for SDV Lab: Retain raw output types only; omit inference/ORT class dependency.
#pragma once


#include <array>
#include <memory>
#include <string>
#include <vector>

namespace visionpilot::models {

// ─── Output ───────────────────────────────────────────────────────────────────
// Both tensors are (1, 64) in the ONNX model, flattened here:
//   xp[i] = lateral x at fixed image row i (normalized [0,1], ×1024 for px)
//   NOT (u,v) pairs — v comes from linspace(0, H-1, 64) in the visualizer.
struct AutoSteerOutput {
    std::array<float, 64> xp{};        // (1, 64) ego-path waypoints
    std::array<float, 64> h_vector{};  // (1, 64) waypoint confidence/mask
    bool                   valid = false;
};

} // namespace visionpilot::models
