// SPDX-FileCopyrightText: 2026 maninblack
// SPDX-License-Identifier: Apache-2.0
#include "assessment.h"
#include <fusion/lateral_fusion.hpp>
#include <fusion/longitudinal_fusion.hpp>
#include <planning/planning.hpp>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <memory>
#include <new>

namespace {
struct State {
    visionpilot::fusion::LongitudinalFusion longitudinal;
    visionpilot::fusion::LateralFusion lateral;
    std::unique_ptr<Planner> planner;
    double geometry=0,speed_limit=0;
    explicit State(uint32_t seed):longitudinal([&]{visionpilot::fusion::LongitudinalFusion::Config c;c.test_seed=seed;return c;}()),
        lateral([&]{visionpilot::fusion::LateralFusion::Config c;c.test_seed=seed;return c;}()){}
};
bool finite_input(const VisionInput& in) {
    if (in.abi!=1 || (in.flags&1)==0 || (in.flags&~7)!=0 || in.box_count>128 || !(in.elapsed_seconds>0 && in.elapsed_seconds<=1)
        || ((in.flags&2)!=0 && (!std::isfinite(in.speed_mps) || in.speed_mps<0 || in.speed_mps>120))
        || ((in.flags&4)!=0 && (!std::isfinite(in.front_axle_to_cog_m) || in.front_axle_to_cog_m<.1 || in.front_axle_to_cog_m>10
            || !std::isfinite(in.speed_limit_mps) || in.speed_limit_mps<=0 || in.speed_limit_mps>120))
        || !std::isfinite(in.distance_normalized) || in.distance_normalized<0 || in.distance_normalized>1
        || !std::isfinite(in.curvature_raw) || !std::isfinite(in.presence_probability) || in.presence_probability<0 || in.presence_probability>1) return false;
    for (double v:in.homography) if (!std::isfinite(v)) return false;
    for (float v:in.xp) if (!std::isfinite(v)) return false;
    // Raw h_vector is a finite mask/height, not a bounded probability.
    for (float v:in.confidence) if (!std::isfinite(v)) return false;
    for (uint32_t n=0;n<in.box_count;++n) {
        const auto& b=in.boxes[n];
        if (!std::isfinite(b.x1)||!std::isfinite(b.x2)||!std::isfinite(b.y1)||!std::isfinite(b.y2)||!std::isfinite(b.score)
            || b.x2<=b.x1 || b.y2<=b.y1 || b.score<0 || b.score>1 || b.class_id<0 || b.class_id>3) return false;
    }
    return true;
}
}

extern "C" uint32_t vision_assessment_abi(){return 1;}
extern "C" uint32_t vision_assessment_input_size(){return sizeof(VisionInput);}
extern "C" uint32_t vision_assessment_output_size(){return sizeof(VisionOutput);}
extern "C" void* vision_assessment_create(uint32_t seed){try{return new State(seed);}catch(...){return nullptr;}}
extern "C" void vision_assessment_destroy(void* state){delete static_cast<State*>(state);}
extern "C" int vision_assessment_step(void* opaque,const VisionInput* input,VisionOutput* output) {
    if (!opaque || !input || !output || !finite_input(*input)) return 1;
    std::memset(output,0,sizeof(*output));output->abi=1;
    try {
        auto& state=*static_cast<State*>(opaque);const auto& in=*input;
        cv::Mat h(3,3,CV_64F);std::memcpy(h.data,in.homography,sizeof(in.homography));
        if (std::abs(cv::determinant(h))<1e-12) return 1;
        state.longitudinal.set_H(h);state.lateral.set_H(h);
        visionpilot::models::AutoDriveOutput drive;
        drive.valid=true;drive.dist_normalized=in.distance_normalized;drive.curvature_raw=in.curvature_raw;drive.flag_prob=in.presence_probability;
        visionpilot::models::AutoSteerOutput steer;steer.valid=true;
        std::copy(std::begin(in.xp),std::end(in.xp),steer.xp.begin());std::copy(std::begin(in.confidence),std::end(in.confidence),steer.h_vector.begin());
        visionpilot::models::AutoSpeedOutput speed;speed.valid=true;
        for (uint32_t i=0;i<in.box_count;++i) {
            const auto& b=in.boxes[i];visionpilot::models::Detection d;
            d.x1=b.x1;d.y1=b.y1;d.x2=b.x2;d.y2=b.y2;d.score=b.score;d.class_id=b.class_id;speed.detections.push_back(d);
        }
        const auto lead=state.longitudinal.update(drive,speed,cv::Mat{},static_cast<float>(in.elapsed_seconds));
        const auto path=state.lateral.update(steer,drive,static_cast<float>(in.elapsed_seconds));
        output->lead_valid=lead.valid;
        // The upstream 150-m free-road sentinel denotes absence, not a target.
        output->lead_present=lead.valid && lead.distance_m<150.f;
        if (output->lead_present) {
            if (!std::isfinite(lead.distance_m)||!std::isfinite(lead.velocity_ms)||!std::isfinite(lead.distance_stddev_m)) return 2;
            output->distance_m=lead.distance_m;output->relative_speed_mps=lead.velocity_ms;output->distance_stddev_m=lead.distance_stddev_m;
        }
        output->path_valid=path.valid && path.path_valid;
        if (output->path_valid) {
            if (!std::isfinite(path.cte_m)||!std::isfinite(path.yaw_rad)||!std::isfinite(path.curvature)
                || !std::isfinite(path.path_a)||!std::isfinite(path.path_b)||!std::isfinite(path.path_c)
                || !(path.path_x_max_m>path.path_x_min_m)) return 2;
            output->cte_m=path.cte_m;output->yaw_rad=path.yaw_rad;output->curvature=path.curvature;output->path_count=32;
            for (unsigned i=0;i<32;++i) {
                const double x=path.path_x_min_m+(path.path_x_max_m-path.path_x_min_m)*i/31.;
                output->path[2*i]=x;output->path[2*i+1]=path.path_a*x*x+path.path_b*x+path.path_c;
            }
        }
        if (in.flags==7 && output->lead_valid && output->path_valid) {
            if (!state.planner || state.geometry!=in.front_axle_to_cog_m || state.speed_limit!=in.speed_limit_mps) {
                state.planner=std::make_unique<Planner>(in.speed_limit_mps,in.front_axle_to_cog_m);
                state.geometry=in.front_axle_to_cog_m;state.speed_limit=in.speed_limit_mps;
            }
            const auto plan=state.planner->compute_plan(path.cte_m,path.yaw_rad,path.curvature,in.speed_mps,
                output->lead_present,output->lead_present?lead.velocity_ms:in.speed_limit_mps,lead.distance_m,in.elapsed_seconds);
            if (plan.steering.empty() || plan.steering.size()>64 || !std::isfinite(plan.acceleration)) return 0;
            for (double angle:plan.steering) if (!std::isfinite(angle)||std::abs(angle)>1.571) return 0;
            output->plan_valid=1;output->acceleration=plan.acceleration;output->steering_count=static_cast<uint32_t>(plan.steering.size());
            std::copy(plan.steering.begin(),plan.steering.end(),output->steering);
        }
        return 0;
    } catch(...) {std::memset(output,0,sizeof(*output));output->abi=1;return 2;}
}
