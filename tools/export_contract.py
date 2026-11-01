#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Explicit source-maintenance export; runtime never follows mutable siblings."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    raw=a.source.read_bytes();source=json.loads(raw)
    assert source['kind']=='vision-native-services-contract' and source['status']=='ACCEPTED_FOR_IMPLEMENTATION_AND_SAME_VM_VERIFICATION'
    root=Path(__file__).resolve().parents[1];destination=root/'contracts/vision-services.v1.json'
    destination.parent.mkdir(exist_ok=True);(root/'dependencies').mkdir(exist_ok=True)
    assert not destination.exists() and not (root/'dependencies/integration-contract.json').exists(),'EXPORT_EXISTS_RECONCILE'
    value={key:source[key] for key in ('schemaVersion','kind','exchange','dtos','bounds','temporal','upstream')}
    value['$comment']='SPDX-FileCopyrightText: 2026 maninblack; SPDX-License-Identifier: MIT; generated wire-only projection, not live mutation authority'
    content=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode();destination.write_bytes(content)
    record=dict(schemaVersion=1,sourceRepository='aosedge-sdv-demo',sourcePath='contracts/vision-vm/services.v1.json',
        sourceSha256=hashlib.sha256(raw).hexdigest(),projectionPath=str(destination.relative_to(root)),projectionSha256=hashlib.sha256(content).hexdigest(),
        sourceLicense='MIT',scope='Wire/model/resource projection only; no target identities, Cloud scope or publication authority')
    (root/'dependencies/integration-contract.json').write_text(json.dumps(record,indent=2)+'\n')
    print('PINNED_WIRE_CONTRACT_EXPORTED')


if __name__=='__main__':main()
