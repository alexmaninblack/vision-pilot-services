// SPDX-FileCopyrightText: 2026 maninblack
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <stdint.h>

struct VisionBox { float x1,y1,x2,y2,score; int32_t class_id; };
struct VisionInput {
    uint32_t abi,flags,box_count;
    double elapsed_seconds,speed_mps,front_axle_to_cog_m,speed_limit_mps;
    double homography[9];
    float distance_normalized,curvature_raw,presence_probability;
    float xp[64],confidence[64];
    VisionBox boxes[128];
};
struct VisionOutput {
    uint32_t abi,lead_valid,lead_present,path_valid,plan_valid,path_count,steering_count;
    double distance_m,relative_speed_mps,distance_stddev_m,cte_m,yaw_rad,curvature;
    double path[128],acceleration,steering[64];
};
extern "C" {
    uint32_t vision_assessment_abi();
    uint32_t vision_assessment_input_size();
    uint32_t vision_assessment_output_size();
    void* vision_assessment_create(uint32_t reference_test_seed);
    void vision_assessment_destroy(void* state);
    int vision_assessment_step(void* state,const VisionInput* input,VisionOutput* output);
}
