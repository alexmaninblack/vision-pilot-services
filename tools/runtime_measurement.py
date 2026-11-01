#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Synthetic isolated ARM64 closure characterization, not native-Aos acceptance.

Run only inside the campaign's unprivileged, network-isolated target root.
These generated images/geometry are unit inputs, never CARLA calibration or
evidence of model accuracy, live cadence, allocated resources or UI delivery.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import time


def summary(values):
    ordered=sorted(values)
    return dict(samples=len(values),mean=statistics.mean(values),maximum=max(values),p95=ordered[min(len(ordered)-1,int(.95*len(ordered)))])


def identity():
    assert sys.platform=='linux' and os.uname().machine=='aarch64'
    assert os.getuid()==os.geteuid()==os.getgid()==os.getegid()==5000
    values=dict(row.split(':',1) for row in Path('/proc/self/status').read_text().splitlines() if ':' in row)
    assert values['NoNewPrivs'].strip()=='1'
    assert all(int(values[k].strip(),16)==0 for k in ('CapEff','CapPrm','CapInh','CapBnd','CapAmb'))
    assert not Path('/run/credentials').exists() and not Path('/run/aosedge/vision').exists()
    return dict(uid=os.getuid(),gid=os.getgid(),noNewPrivileges=True,capabilitiesZero=True,applicationCredentials=False)


def perception():
    from vision_perception.runtime import Runtime
    runtime=Runtime(Path('/app'));samples=[];cpu=[]
    try:
        np,cv2=runtime.np,runtime.cv2
        # A deterministic nonuniform synthetic image exercises all decode,
        # preprocess, FP32 model and bounded postprocess paths, without claiming
        # learned accuracy or a physically calibrated moving scene.
        y,x=np.indices((720,1280));image=np.stack(((x%256),(y%256),((x+y)%256)),axis=2).astype(np.uint8)
        ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,85]);assert ok
        jpeg=encoded.tobytes();mapping=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
        for cycle in range(20):
            before=time.process_time();models,timings=runtime.run([jpeg,jpeg],[mapping,mapping]);elapsed=(time.process_time()-before)*1000
            assert all(value['valid'] for value in models.values())
            if cycle>=5:samples.append(timings);cpu.append(elapsed)
        return dict(wallMs={key:summary([row[key] for row in samples]) for key in samples[0]},cpuMs=summary(cpu),
            modelCount=len(runtime.sessions),providers=['CPUExecutionProvider'],syntheticImages=True)
    finally:runtime.close()


def assessment():
    import ctypes as c
    from vision_assessment.native import Input,Output,decode
    library=c.CDLL('/app/lib/libvision_assessment.so')
    library.vision_assessment_create.argtypes=[c.c_uint32];library.vision_assessment_create.restype=c.c_void_p
    library.vision_assessment_destroy.argtypes=[c.c_void_p];library.vision_assessment_destroy.restype=None
    library.vision_assessment_step.argtypes=[c.c_void_p,c.POINTER(Input),c.POINTER(Output)];library.vision_assessment_step.restype=c.c_int
    state=library.vision_assessment_create(0);assert state
    try:
        value=Input();value.abi=1;value.flags=1;value.elapsed_seconds=.2
        value.homography[:]=[0.,-30/512,30.,-.01,0.,5.12,0.,0.,1.]
        value.distance_normalized=.5;value.curvature_raw=0.;value.presence_probability=0.
        value.xp[:]=[.5]*64;value.confidence[:]=[1.]*64
        wall=[];cpu=[]
        for cycle in range(105):
            out=Output();began=time.perf_counter();before=time.process_time()
            assert library.vision_assessment_step(state,c.byref(value),c.byref(out))==0
            elapsed=(time.perf_counter()-began)*1000;spent=(time.process_time()-before)*1000
            result=decode(out);assert result['lead']['valid'] and not result['lead']['present'] and result['path']['valid'] and not result['plan']['valid']
            if cycle>=5:wall.append(elapsed);cpu.append(spent)
        return dict(wallMs=summary(wall),cpuMs=summary(cpu),syntheticGeometry=True,planWithheld=True,actuatorAccess=False)
    finally:library.vision_assessment_destroy(state)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('role',choices=('perception','assessment'));args=parser.parse_args()
    identity_facts=identity();sys.path[:0]=['/app/common','/app','/app/libraries']
    started=time.monotonic();value=(perception if args.role=='perception' else assessment)()
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    print(json.dumps(dict(outcome='PASS_SYNTHETIC_ARM64_CLOSURE_MEASUREMENT',role=args.role,identity=identity_facts,
        measurements=value,peakRssBytes=peak,seconds=round(time.monotonic()-started,3),nativeAos='NOT_RUN',liveCamera='NOT_RUN',ui='NOT_RUN')),flush=True)


if __name__=='__main__':main()
