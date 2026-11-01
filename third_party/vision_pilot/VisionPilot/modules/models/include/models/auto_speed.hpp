// Derived from VisionPilot e7e5c614832f175f1f9f10a0d0c0df2559ff2c38 (Apache-2.0).
// Modified for SDV Lab: Retain raw output types only; omit inference/ORT class dependency.
#pragma once


#include <memory>
#include <string>
#include <vector>

namespace visionpilot::models {

// ─── Output ───────────────────────────────────────────────────────────────────
// Bounding boxes in model-input pixel space (1024 × 512) after NMS.
// Coordinate mapping back to original image coordinates is the caller's job
// (reverse the letterbox: subtract pad, divide by scale).
struct Detection {
    float x1 = 0.f, y1 = 0.f;  // top-left
    float x2 = 0.f, y2 = 0.f;  // bottom-right
    float score    = 0.f;
    int   class_id = 0;
};

struct AutoSpeedOutput {
    std::vector<Detection> detections;
    bool valid = false;
};

} // namespace visionpilot::models
