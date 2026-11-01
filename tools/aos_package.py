#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Isolated Vision package profile; never alter the existing Lab parser limits.

Only exact Perception/Assessment rootfs files and fixed resource configuration
are admitted. Native quotas are supplied by a frozen integration receipt, not
invented here. This module neither starts a model nor signs/uploads a bundle.
"""
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import tarfile

QUOTAS=('cpuLimit','ramLimit','storageLimit','stateLimit','tmpLimit','noFileLimit','pidsLimit')
PROFILES={
    'perception':dict(compressed=256*1024**2,expanded=512*1024**2,resources=['vision-camera-read','vision-perception-publish']),
    'assessment':dict(compressed=128*1024**2,expanded=256*1024**2,resources=['vision-perception-read','vision-context-read','vision-assessment-publish'])}


def require(ok,code):
    if not ok:raise ValueError(code)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def files(raw,role):
    require(role in PROFILES,'VISION_PACKAGE_PROFILE_INVALID');profile=PROFILES[role]
    require(type(raw) is bytes and len(raw)<=profile['compressed'],'VISION_PACKAGE_COMPRESSED_LIMIT')
    result={};seen=set();total=0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r|*') as archive:
            for index,row in enumerate(archive):
                path=PurePosixPath(row.name);name=path.as_posix()
                require(index<10000 and not path.is_absolute() and '..' not in path.parts and '\\' not in row.name
                    and name==row.name and 0<len(name)<=512 and all(ord(c)>=32 for c in name)
                    and (row.isfile() or row.isdir()) and row.sparse is None and not row.mode&0o7000,'VISION_PACKAGE_MEMBER_UNSAFE')
                require(name not in seen,'VISION_PACKAGE_MEMBER_DUPLICATE');seen.add(name)
                if row.isdir():continue
                total+=row.size;require(0<=row.size and total<=profile['expanded'],'VISION_PACKAGE_EXPANSION_LIMIT')
                data=archive.extractfile(row).read(row.size+1);require(len(data)==row.size,'VISION_PACKAGE_MEMBER_TRUNCATED')
                result[name]=(data,0o555 if row.mode&0o111 else 0o444)
    except (tarfile.TarError,EOFError,OSError):raise ValueError('VISION_PACKAGE_ARCHIVE_INVALID') from None
    require(not any(parent.as_posix() in result for name in result for parent in PurePosixPath(name).parents),'VISION_PACKAGE_PATH_CONFLICT')
    return result


def configuration(role,quotas):
    require(role in PROFILES and type(quotas) is dict and set(quotas)==set(QUOTAS)
        and all(type(v) is int and v>0 for v in quotas.values()),'VISION_PACKAGE_QUOTAS_INVALID')
    require(quotas['noFileLimit']==1024 and 16<=quotas['pidsLimit']<=128,'VISION_PACKAGE_NATIVE_SETUP_BOUNDS')
    return dict(schemaVersion=2,publisher=dict(author='maninblack'),items=[dict(
        identity=dict(type='service',codename='vision-'+role,title='Vision '+role.title()),version='0.1.0',sourceFolder='service',
        images=[dict(sourceFolder='arm64',archInfo=dict(architecture='arm64'))],
        configuration=dict(workingDir='/',cmd='/usr/bin/vision-'+role,instances=dict(minInstances=1,priority=10),offlineTTL='P7D',
            quotas=dict(quotas),alertRules=None,resources=[dict(name=name) for name in PROFILES[role]['resources']],allowedConnections=[]),dependencies=[])])


def validate_rootfs(payload,manifest,role):
    require(role in PROFILES and type(manifest) is dict and manifest['service']=='vision-'+role and manifest['version']=='0.1.0'
        and manifest['licenseNoticesIncluded'] is True and manifest['maximumExtractedBytes']==PROFILES[role]['expanded'],'VISION_PACKAGE_CLOSURE_PROFILE_CHANGED')
    expected={row['path']:row for row in manifest['files']}
    require(len(expected)==manifest['count']==len(manifest['files']) and set(payload)==set(expected),'VISION_PACKAGE_CLOSURE_FILE_SET_CHANGED')
    require(sum(len(data) for data,_ in payload.values())==manifest['bytes']<=PROFILES[role]['expanded'],'VISION_PACKAGE_CLOSURE_SIZE_CHANGED')
    for name,(data,mode) in payload.items():
        row=expected[name];require(len(data)==row['bytes'] and sha(data)==row['sha256'],'VISION_PACKAGE_CLOSURE_DIGEST_CHANGED')
        if data.startswith(b'\x7fELF'):
            require(data[:6]==b'\x7fELF\x02\x01' and data[18:20]==b'\xb7\x00','VISION_PACKAGE_NOT_ARM64')
    required={'usr/bin/vision-'+role,'usr/bin/python3.12','app/entry.py','app/service-manifest.json','app/notices/sbom.json'}
    require(required<=payload.keys() and payload['usr/bin/vision-'+role][1]==0o555,'VISION_PACKAGE_FIXED_ENTRY_MISSING')
    identity=json.loads(payload['app/service-manifest.json'][0])
    require(identity['codename']=='vision-'+role and identity['version']=='0.1.0','VISION_PACKAGE_IDENTITY_CHANGED')
    if role=='assessment':require(not any(name.startswith('app/models/') for name in payload),'VISION_ASSESSMENT_MODELS_FORBIDDEN')
    return identity


def prepare(archive,manifest,role,quotas,output,expected_sha256):
    require(output.is_absolute() and not output.exists() and not output.is_symlink(),'VISION_PACKAGE_OUTPUT_EXISTS')
    require(archive.is_file() and not archive.is_symlink() and archive.stat().st_size<=PROFILES[role]['compressed'],'VISION_PACKAGE_INPUT_UNSAFE')
    raw=archive.read_bytes();require(sha(raw)==expected_sha256,'VISION_PACKAGE_INPUT_CHANGED')
    payload=files(raw,role);identity=validate_rootfs(payload,manifest,role);config=configuration(role,quotas)
    output.mkdir(mode=0o700)
    prepared={}
    for name,(data,mode) in payload.items():
        target=output/'service/arm64'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(mode)
        prepared['service/arm64/'+name]=dict(sha256=sha(data),bytes=len(data),mode=mode)
    encoded=(json.dumps(config,indent=2)+'\n').encode();(output/'config.yaml').write_bytes(encoded);(output/'config.yaml').chmod(0o444)
    prepared['config.yaml']=dict(sha256=sha(encoded),bytes=len(encoded),mode=0o444)
    receipt=dict(schemaVersion=1,role=role,version='0.1.0',profile='vision-'+role+'-arm64-v1',rootfsSha256=expected_sha256,
        sourceRevision=identity['sourceRevision'],files=prepared,quotas=quotas,signing='NOT_RUN',publication='NOT_RUN')
    (output/'prepared.json').write_text(json.dumps(receipt,indent=2)+'\n');(output/'prepared.json').chmod(0o444)
    return receipt


def verify_signed(bundle,credential,role,prepared,expected_sha256=None):
    """Same official RS256/SHA3 envelope, with this one explicit size profile."""
    import jwt
    from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
    require(role in PROFILES and prepared['role']==role,'VISION_PACKAGE_PROFILE_INVALID')
    require(bundle.is_file() and not bundle.is_symlink() and bundle.stat().st_size<=PROFILES[role]['compressed'],'VISION_SIGNED_PATH_INVALID')
    raw=bundle.read_bytes();require(expected_sha256 is None or sha(raw)==expected_sha256,'VISION_SIGNED_DIGEST_CHANGED')
    outer=files(raw,role);require(set(outer)=={'package.sign','config.yaml','batch.tar.gz'},'VISION_SIGNED_ENVELOPE_INVALID')
    require(credential.is_file() and not credential.is_symlink() and not credential.stat().st_mode&0o077 and credential.stat().st_size<=1024**2,'VISION_SP_CREDENTIAL_UNSAFE')
    _,certificate,_=load_key_and_certificates(credential.read_bytes(),b'');require(certificate is not None,'VISION_SP_CERTIFICATE_MISSING')
    value=jwt.decode(outer['package.sign'][0],certificate.public_key(),algorithms=['RS256'])
    expected=[dict(name=name,size=len(outer[name][0]),hash=hashlib.sha3_512(outer[name][0]).hexdigest()) for name in ('batch.tar.gz','config.yaml')]
    require(type(value.get('data')) is list and sorted(value['data'],key=lambda row:row['name'])==sorted(expected,key=lambda row:row['name']),'VISION_SIGNED_HASH_MISMATCH')
    inner=files(outer['batch.tar.gz'][0],role)
    require(set(inner)==set(prepared['files']) and inner['config.yaml'][0]==outer['config.yaml'][0],'VISION_SIGNED_FILE_SET_CHANGED')
    for name,(data,mode) in inner.items():
        pin=prepared['files'][name];require(sha(data)==pin['sha256'] and len(data)==pin['bytes'] and mode==pin['mode'],'VISION_SIGNED_PAYLOAD_CHANGED')
    require(json.loads(inner['config.yaml'][0])==configuration(role,prepared['quotas']),'VISION_SIGNED_SCOPE_CHANGED')
    return dict(sha256=sha(raw),bytes=len(raw),signatureVerification='VERIFIED_RS256',payloadMatchesPrepared=True,verificationTrust='CONFIGURED_SP_SIGNING_CERTIFICATE')
