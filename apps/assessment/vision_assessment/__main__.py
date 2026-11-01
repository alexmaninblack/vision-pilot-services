# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Native Assessment resource loop, no inference, key, network or motion input."""
import json
import os
from pathlib import Path
import signal
import sys
import threading
from vision_common import protocol as p
from vision_common.client import Client
from .core import Assessment
from .native import Native


def main():
    p.require(sys.platform=='linux' and os.uname().machine=='aarch64' and os.getuid()>0,'NATIVE_NONROOT_LINUX_ARM64_REQUIRED')
    root=Path('/app');manifest=json.loads((root/'service-manifest.json').read_bytes());version=p.version(manifest['version'])
    profile=json.loads((root/'config/calibration.json').read_bytes());algorithm=Native(root,profile);core=Assessment(algorithm,service_version=version)
    reader=Client('perception-read');context_reader=Client('context-read');publisher=Client('assessment-publish')
    stop=threading.Event();last=None;failure=None
    for name in (signal.SIGTERM,signal.SIGINT):signal.signal(name,lambda *_:stop.set())
    try:
        while not stop.is_set():
            try:
                for client in (reader,context_reader,publisher):client.request('status')
                raw=reader.request('latest',after=last)
                if raw.get('kind')!='perception':stop.wait(.02);continue
                last=raw['producer'];context=context_reader.request('context',binding=raw['binding'],frame=raw['frames'][-1])
                if context.get('kind')!='context':context=None
                value=core.process(raw,context);publisher.request('publish',value=value);failure=None
            except (p.Invalid,OSError) as error:
                code=str(error) if isinstance(error,p.Invalid) else 'RESOURCE_UNAVAILABLE'
                if code!=failure:print(json.dumps(dict(state='UNAVAILABLE',reason=code)),flush=True);failure=code
                stop.wait(.1)
        return 0
    finally:algorithm.close()


if __name__=='__main__':raise SystemExit(main())
