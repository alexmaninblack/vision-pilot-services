# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Closed C ABI for the pinned upstream algorithms; no vehicle I/O."""
import ctypes as c
import os
from pathlib import Path
import sys
from vision_common import protocol as p
from .core import absent


class Box(c.Structure):
    _fields_=[('x1',c.c_float),('y1',c.c_float),('x2',c.c_float),('y2',c.c_float),('score',c.c_float),('class_id',c.c_int32)]


class Input(c.Structure):
    _fields_=[('abi',c.c_uint32),('flags',c.c_uint32),('box_count',c.c_uint32),
        ('elapsed_seconds',c.c_double),('speed_mps',c.c_double),('front_axle_to_cog_m',c.c_double),('speed_limit_mps',c.c_double),
        ('homography',c.c_double*9),('distance_normalized',c.c_float),('curvature_raw',c.c_float),('presence_probability',c.c_float),
        ('xp',c.c_float*64),('confidence',c.c_float*64),('boxes',Box*128)]


class Output(c.Structure):
    _fields_=[(key,c.c_uint32) for key in ('abi','lead_valid','lead_present','path_valid','plan_valid','path_count','steering_count')]
    _fields_ += [(key,c.c_double) for key in ('distance_m','relative_speed_mps','distance_stddev_m','cte_m','yaw_rad','curvature')]
    _fields_ += [('path',c.c_double*128),('acceleration',c.c_double),('steering',c.c_double*64)]


def encode(raw,context,seconds,homography):
    p.perception(raw);p.context(context);p.number(seconds,1e-9,1.)
    p.require(raw['binding']==context['binding'] and raw['frames'][-1]==context['frame'],'CONTEXT_CAPTURE_MISMATCH')
    p.require(all(v['valid'] for v in raw['models'].values()),'ALGORITHM_INPUT_UNAVAILABLE')
    value=Input();value.abi=1;value.flags=1;value.elapsed_seconds=seconds
    if context['dynamics']['available']:value.flags|=2;value.speed_mps=context['dynamics']['speedMps']
    if context['vehicleProfile']['available']:
        value.flags|=4;value.front_axle_to_cog_m=context['vehicleProfile']['frontAxleToCogM'];value.speed_limit_mps=context['vehicleProfile']['speedLimitMps']
    value.homography[:]=[v for row in homography for v in row]
    drive=raw['models']['autodrive'];steer=raw['models']['autosteer'];boxes=raw['models']['autospeed']['detections']
    value.distance_normalized=drive['distanceNormalized'];value.curvature_raw=drive['curvatureRaw'];value.presence_probability=drive['presenceProbability']
    value.xp[:]=steer['xp'];value.confidence[:]=steer['confidence'];value.box_count=len(boxes)
    for i,box in enumerate(boxes):value.boxes[i]=Box(*box['box'],box['score'],box['classId'])
    return value


def decode(value):
    p.require(value.abi==1 and value.path_count<=64 and value.steering_count<=64
        and all(getattr(value,k) in (0,1) for k in ('lead_valid','lead_present','path_valid','plan_valid')),'NATIVE_OUTPUT_ABI_INVALID')
    result=absent()
    if value.lead_valid:
        present=bool(value.lead_present)
        result['lead']=dict(valid=True,present=present,distanceMetres=value.distance_m if present else None,
            relativeSpeedMps=value.relative_speed_mps if present else None,distanceStddevMetres=value.distance_stddev_m if present else None)
    if value.path_valid:
        result['path']=dict(valid=True,points=[[value.path[2*i],value.path[2*i+1]] for i in range(value.path_count)],
            crossTrackMetres=value.cte_m,yawRadians=value.yaw_rad,curvaturePerMetre=value.curvature)
    if value.plan_valid:result['plan']=dict(valid=True,accelerationMps2=value.acceleration,steeringRadians=list(value.steering[:value.steering_count]))
    return result


class Native:
    def __init__(self,root,calibration):
        p.require(sys.platform=='linux' and os.uname().machine=='aarch64','LINUX_ARM64_REQUIRED')
        self.calibration=calibration;self.library=c.CDLL(str(Path(root)/'lib/libvision_assessment.so'));self.state=None
        lib=self.library;lib.vision_assessment_abi.restype=c.c_uint32
        lib.vision_assessment_input_size.restype=c.c_uint32;lib.vision_assessment_output_size.restype=c.c_uint32
        p.require(lib.vision_assessment_abi()==1 and lib.vision_assessment_input_size()==c.sizeof(Input)
            and lib.vision_assessment_output_size()==c.sizeof(Output),'NATIVE_LIBRARY_ABI_CHANGED')
        lib.vision_assessment_create.argtypes=[c.c_uint32];lib.vision_assessment_create.restype=c.c_void_p
        lib.vision_assessment_destroy.argtypes=[c.c_void_p];lib.vision_assessment_destroy.restype=None
        lib.vision_assessment_step.argtypes=[c.c_void_p,c.POINTER(Input),c.POINTER(Output)];lib.vision_assessment_step.restype=c.c_int
        self.reset()

    def reset(self):
        self.close();self.state=self.library.vision_assessment_create(0);p.require(bool(self.state),'NATIVE_STATE_CREATE_FAILED')

    def close(self):
        if self.state:self.library.vision_assessment_destroy(self.state);self.state=None

    def update(self,raw,context,seconds):
        value=encode(raw,context,seconds,self.calibration['modelToVehicle']);output=Output()
        p.require(self.library.vision_assessment_step(self.state,c.byref(value),c.byref(output))==0,'NATIVE_ALGORITHM_FAILED')
        return decode(output)
