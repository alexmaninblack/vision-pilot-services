# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Native Perception resource loop; fixed paths, bounded diagnostics, no actuation."""
import json
import os
from pathlib import Path
import signal
import sys
import threading
from uuid import uuid4
from vision_common import protocol as p
from vision_common.client import Client,camera_pair
from .runtime import Runtime,calibration


def main():
    p.require(sys.platform=='linux' and os.uname().machine=='aarch64' and os.getuid()>0,'NATIVE_NONROOT_LINUX_ARM64_REQUIRED')
    root=Path('/app');manifest=json.loads((root/'service-manifest.json').read_bytes());version=p.version(manifest['version'])
    profile=json.loads((root/'config/calibration.json').read_bytes());runtime=Runtime(root);publisher=Client('perception-publish')
    stop=threading.Event();epoch=str(uuid4());sequence=0;last=None;failure=None
    for name in (signal.SIGTERM,signal.SIGINT):signal.signal(name,lambda *_:stop.set())
    try:
        while not stop.is_set():
            try:
                publisher.request('status');pair=camera_pair()
                if pair is None:stop.wait(.02);continue
                binding,frames,jpegs=pair;key=(binding['sourceEpoch'],frames[-1]['frame'])
                p.require(key!=last,'CAMERA_PAIR_REPEATED');last=key;calibration(profile,binding['calibrationId'])
                models,timings=runtime.run(jpegs,profile);sequence+=1
                value=dict(schemaVersion=1,kind='perception',binding=binding,frames=frames,
                    producer=dict(epoch=epoch,sequence=sequence,serviceVersion=version),modelProfile=p.MODEL_PROFILE,
                    preprocessingProfile=p.PREPROCESSING_PROFILE,models=models,timingsMs=timings)
                p.perception(value);publisher.request('publish',value=value);failure=None
            except (p.Invalid,OSError) as error:
                code=str(error) if isinstance(error,p.Invalid) else 'RESOURCE_UNAVAILABLE'
                if code!=failure:print(json.dumps(dict(state='UNAVAILABLE',reason=code)),flush=True);failure=code
                stop.wait(.1)
        return 0
    finally:runtime.close()


if __name__=='__main__':raise SystemExit(main())
