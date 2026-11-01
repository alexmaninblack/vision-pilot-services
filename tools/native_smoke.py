#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Synthetic target-algorithm units, not model/native-Aos/live acceptance."""
import argparse
import ctypes as c
import json
import os
from pathlib import Path
import sys


def library(path,Input,Output):
    lib=c.CDLL(str(path));lib.vision_assessment_abi.restype=c.c_uint32
    assert lib.vision_assessment_abi()==1
    assert lib.vision_assessment_input_size()==c.sizeof(Input) and lib.vision_assessment_output_size()==c.sizeof(Output)
    lib.vision_assessment_create.argtypes=[c.c_uint32];lib.vision_assessment_create.restype=c.c_void_p
    lib.vision_assessment_destroy.argtypes=[c.c_void_p];lib.vision_assessment_destroy.restype=None
    lib.vision_assessment_step.argtypes=[c.c_void_p,c.POINTER(Input),c.POINTER(Output)];lib.vision_assessment_step.restype=c.c_int
    return lib


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,required=True);args=parser.parse_args()
    assert sys.platform=='linux' and os.uname().machine=='aarch64'
    root=Path(__file__).resolve().parents[1]
    for part in ('common','apps/assessment','tests'):sys.path.insert(0,str(root/part))
    import fixtures as f
    from vision_assessment.native import Input,Output,encode,decode
    lib=library(args.library,Input,Output);state=lib.vision_assessment_create(42);assert state
    cases=[]
    # Unit geometry only, not borrowed or claimed as the live CARLA calibration.
    h=[[0.,-30/512,30.],[-.01,0.,5.12],[0.,0.,1.]]
    try:
        raw=f.perception();raw['models']['autodrive']['presenceProbability']=0.
        context=f.context();context['dynamics']['speedMps']=0.
        value=encode(raw,context,.1,h);out=Output()
        assert lib.vision_assessment_step(state,c.byref(value),c.byref(out))==0
        result=decode(out);assert result['lead']['valid'] and result['lead']['present'] is False and result['lead']['distanceMetres'] is None
        cases.append('FREE_ROAD_SENTINEL_IS_ABSENCE')
        assert out.path_valid and out.path_count==32 and out.plan_valid and out.steering_count==19
        cases.append('REAL_UPSTREAM_PATH_AND_STATIONARY_SHADOW_PLAN')
        assert all(out.steering[i]==0 for i in range(out.steering_count));cases.append('STATIONARY_PLAN_NO_ACTUATOR')
        value.box_count=129;assert lib.vision_assessment_step(state,c.byref(value),c.byref(out))==1;value.box_count=0
        value.elapsed_seconds=0.;assert lib.vision_assessment_step(state,c.byref(value),c.byref(out))==1;value.elapsed_seconds=.3
        assert lib.vision_assessment_step(state,c.byref(value),c.byref(out))==0;cases.append('EXPLICIT_DELTA_AND_BOUNDS')
        value.flags=1
        assert lib.vision_assessment_step(state,c.byref(value),c.byref(out))==0
        assert out.lead_valid and out.path_valid and not out.plan_valid
        cases.append('FUSION_WITHOUT_FABRICATED_DYNAMICS_OR_PLAN')
        value.confidence[0]=-.2;value.confidence[1]=2.
        assert lib.vision_assessment_step(state,c.byref(value),c.byref(out))==0
        cases.append('RAW_AUTOSTEER_HEIGHT_MASK_IS_NOT_PROBABILITY')
    finally:lib.vision_assessment_destroy(state)
    # Identical isolated reference seeds must reproduce the same filter path.
    states=[lib.vision_assessment_create(61),lib.vision_assessment_create(61)]
    try:
        raw=f.perception();context=f.context();context['dynamics']['speedMps']=0.;value=encode(raw,context,.1,h)
        for _ in range(12):
            outputs=[Output(),Output()]
            for s,o in zip(states,outputs):assert lib.vision_assessment_step(s,c.byref(value),c.byref(o))==0
            assert bytes(outputs[0])==bytes(outputs[1]);assert outputs[0].lead_present
        cases.append('DETERMINISTIC_REFERENCE_FILTER_SEQUENCE')
    finally:
        for state in states:lib.vision_assessment_destroy(state)
    print(json.dumps(dict(outcome='PASS_TARGETED_ARM64_UPSTREAM_ALGORITHM_UNITS',cases=cases,nativeAos='NOT_RUN',models='NOT_RUN',liveCalibration='NOT_RUN')))


if __name__=='__main__':main()
