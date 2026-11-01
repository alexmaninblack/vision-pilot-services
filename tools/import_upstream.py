#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Import the immutable fusion/planning cut, never engine/vehicle/ROS/weights."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

PIN='e7e5c614832f175f1f9f10a0d0c0df2559ff2c38'
PATHS=['LICENSE','VisionPilot/modules/common/include/common/types.hpp']
PATHS += ['VisionPilot/modules/models/include/models/'+name+'.hpp' for name in ('auto_drive','auto_steer','auto_speed')]
for component,names in (('fusion',('lateral_fusion','longitudinal_fusion')),('planning',('planning','lateral_planning','longitudinal_planning'))):
    for name in names:
        PATHS += ['VisionPilot/modules/safety_guardian/'+component+'/include/'+component+'/'+name+'.hpp',
                  'VisionPilot/modules/safety_guardian/'+component+'/src/'+name+'.cpp']


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    assert subprocess.check_output(['git','-C',str(a.source),'rev-parse','HEAD'],text=True).strip()==PIN
    assert not subprocess.check_output(['git','-C',str(a.source),'status','--porcelain'],text=True)
    root=Path(__file__).resolve().parents[1];target=root/'third_party/vision_pilot'
    assert not target.exists(),'UPSTREAM_IMPORT_EXISTS_RECONCILE';target.mkdir(parents=True)
    records=[]
    for name in PATHS:
        raw=subprocess.check_output(['git','-C',str(a.source),'show',PIN+':'+name]);text=raw.decode();changes=[]
        if '/models/include/models/' in name:
            # Preserve upstream DTO declarations/comments, remove the inference
            # class and its engine/ORT dependencies from Assessment's headers.
            assert text.count('// ─── Model')==1
            text=text.split('// ─── Model')[0]+'} // namespace visionpilot::models\n'
            text='\n'.join(row for row in text.splitlines() if not row.startswith(('#include <engine/','#include <onnxruntime_')))+'\n'
            changes.append('Retain raw output types only; omit inference/ORT class dependency')
        if name.endswith('/planning/include/planning/planning.hpp'):
            assert text.count('double cipo_distance);')==1
            text=text.replace('double cipo_distance);','double cipo_distance,\n        double elapsed_seconds);')
            changes.append('Require actual processing-cycle elapsed time separately from horizon step')
        if name.endswith('/planning/src/planning.cpp'):
            assert text.count('const double cipo_distance)')==1 and text.count('ego_v * dt')==1
            text=text.replace('const double cipo_distance)','const double cipo_distance,\n    const double elapsed_seconds)').replace('ego_v * dt','ego_v * elapsed_seconds')
            changes.append('Use explicit processing elapsed time only for inter-cycle displacement; preserve prediction horizon dt')
        if name.endswith('.hpp') and 'struct Config {' in text and '/fusion/' in name:
            assert text.count('struct Config {')==1
            text=text.replace('struct Config {','struct Config {\n        unsigned int test_seed = 0; // 0: production random_device; nonzero: isolated reference fixture')
            changes.append('Optional nonzero deterministic reference-fixture seed; production default unchanged')
        if '/fusion/src/' in name:
            assert text.count('rng_(std::random_device{}())')==1
            text=text.replace('rng_(std::random_device{}())','rng_(cfg.test_seed ? cfg.test_seed : std::random_device{}())')
            changes.append('Honor isolated reference-fixture seed; production default unchanged')
        content=text.encode()
        if changes:
            banner='// Derived from VisionPilot '+PIN+' (Apache-2.0).\n// Modified for SDV Lab: '+'; '.join(changes)+'.\n'
            content=banner.encode()+content
        relative=Path(name);destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
        records.append(dict(upstreamPath=name,upstreamSha256=hashlib.sha256(raw).hexdigest(),path=str(destination.relative_to(root)),sha256=hashlib.sha256(content).hexdigest(),modifications=changes))
    record=dict(schemaVersion=1,repository='https://github.com/autowarefoundation/vision_pilot',revision=PIN,license='Apache-2.0',
        importedFiles=records,excluded=['engine','models/weights','vehicle output','ROS','GUI','CMake automatic fetching'],
        productionAlgorithms='Original upstream fusion/planning; explicit actual cycle delta; deterministic seed nonzero only in isolated reference fixtures')
    (root/'dependencies/upstream.json').write_text(json.dumps(record,indent=2)+'\n');print('PINNED_ASSESSMENT_SOURCE_CUT_IMPORTED')


if __name__=='__main__':main()
