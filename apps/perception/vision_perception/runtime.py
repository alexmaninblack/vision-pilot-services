# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Linux ARM64 CPU sessions with exact model hashes, never a host fallback."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from vision_common.protocol import require,fields,label,number,Invalid
from vision_common.jpeg import dimensions
from . import outputs
from .preprocessing import tensors

MODEL_SHA={
    'autodrive':'196a82289ba7d96f574cc4dfa8815dadb9f104397c7c2bec7c98333e5ee8762d',
    'autosteer':'770d26f431467bbcc7fe3e794411cac36d8dfbd1658e4eb4a37d48342db7cbf6',
    'autospeed':'adff7dd9fa9c2d306d9228a87edcf2ae256edbdc9e4b9541fd471880aa5c1451'}


def calibration(value,expected_id):
    fields(value,('schemaVersion','id','profile','rawToModel','modelToVehicle','scope'))
    require(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['id']==expected_id,'CALIBRATION_BINDING_INVALID')
    require(value['profile']=='carla-forward-720p-fov50-v1' and value['scope']=='PLANAR_REFERENCE_ONLY','CALIBRATION_PROFILE_INVALID')
    for name in ('rawToModel','modelToVehicle'):
        matrix=value[name];require(type(matrix) is list and len(matrix)==3 and all(type(row) is list and len(row)==3 for row in matrix),'CALIBRATION_SHAPE_INVALID')
        for row in matrix:
            for v in row:number(v)
        a,b,c=matrix
        determinant=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
        require(abs(determinant)>1e-12,'CALIBRATION_SINGULAR')
    return value


class Runtime:
    def __init__(self,root):
        require(sys.platform=='linux' and os.uname().machine=='aarch64','LINUX_ARM64_REQUIRED')
        import numpy as np
        import cv2
        import onnxruntime as ort
        require((np.__version__,cv2.__version__,ort.__version__)==('2.4.4','4.13.0','1.26.0'),'RUNTIME_VERSION_CHANGED')
        ort.disable_telemetry_events();cv2.setNumThreads(1)
        self.np=np;self.cv2=cv2;self.ort=ort;self.root=Path(root);self.sessions={};self.names={}
        for name,digest in MODEL_SHA.items():
            path=self.root/'models'/(name+'_fp32.onnx')
            require(path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,'MODEL_DIGEST_CHANGED')
            options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
            options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            options.add_session_config_entry('session.intra_op.allow_spinning','0');options.log_severity_level=3
            session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider'])
            require(session.get_providers()==['CPUExecutionProvider'],'CPU_PROVIDER_REQUIRED');inputs=session.get_inputs()
            require(len(inputs)==(2 if name=='autodrive' else 1) and all(row.type=='tensor(float)' and row.shape==['batch_size',3,512,1024] for row in inputs),'MODEL_INPUT_SHAPE_CHANGED')
            self.sessions[name]=session;self.names[name]=[row.name for row in inputs]
        self.pool=ThreadPoolExecutor(max_workers=3)

    def close(self):self.pool.shutdown(wait=True,cancel_futures=True)

    def run(self,jpegs,profile):
        np,cv2=self.np,self.cv2;start=time.perf_counter();require(len(jpegs)==2,'PAIR_INVALID')
        for raw in jpegs:dimensions(raw)
        decoded=[cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR) for raw in jpegs]
        require(all(image is not None and image.shape==(720,1280,3) for image in decoded),'PIXEL_DECODE_INVALID')
        after_decode=time.perf_counter()
        plain,temporal=tensors(decoded,profile,np,cv2)
        preprocessed=time.perf_counter()
        def infer(name,tensors):
            began=time.perf_counter();options=self.ort.RunOptions();options.add_run_config_entry('memory.enable_memory_arena_shrinkage','cpu:0')
            values=self.sessions[name].run(None,dict(zip(self.names[name],tensors)),options)
            require(all(np.isfinite(v).all() for v in values),'MODEL_NONFINITE_OUTPUT')
            shapes=[v.shape for v in values]
            expected={'autodrive':[(1,1)]*3,'autosteer':[(1,1,64,1)]*2,'autospeed':[(1,8,10752)]}[name]
            require(shapes==expected,'MODEL_OUTPUT_SHAPE_CHANGED')
            if name=='autodrive':result=outputs.autodrive([float(v.ravel()[0]) for v in values])
            elif name=='autosteer':result=outputs.autosteer(values[0].ravel().tolist(),values[1].ravel().tolist())
            else:result=outputs.autospeed(values[0][0].tolist())
            return result,(time.perf_counter()-began)*1000
        jobs={name:self.pool.submit(infer,name,temporal if name=='autodrive' else [plain]) for name in self.sessions}
        results={name:job.result() for name,job in jobs.items()}
        return {name:row[0] for name,row in results.items()},dict(decode=(after_decode-start)*1000,preprocess=(preprocessed-after_decode)*1000,
            total=(time.perf_counter()-start)*1000,**{name:row[1] for name,row in results.items()})
