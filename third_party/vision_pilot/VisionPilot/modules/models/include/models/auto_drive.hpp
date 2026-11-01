// Derived from VisionPilot e7e5c614832f175f1f9f10a0d0c0df2559ff2c38 (Apache-2.0).
// Modified for SDV Lab: Retain raw output types only; omit inference/ORT class dependency.
#pragma once


#include <memory>
#include <string>
#include <vector>

namespace visionpilot::models {

// ─── Output ───────────────────────────────────────────────────────────────────
// Raw scalars straight from the model. Domain conversion is the caller's job:
//   distance_m    = D_MAX_M * (1.0f - dist_normalized)   // D_MAX_M = 150.0
//   curvature_1pm = curvature_raw * CURV_SCALE
struct AutoDriveOutput {
    float dist_normalized = 0.f;  // normalised distance  [0, 1]
    float curvature_raw   = 0.f;  // raw curvature output
    float flag_prob       = 0.f;  // sigmoid(flag_logit), CIPO probability [0, 1]
    bool  valid           = false;
};

} // namespace visionpilot::models
