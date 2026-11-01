#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Offline ARM64 closure measurement from a clean build root, never a live VM.

No inference, signing, Cloud, image or simulator operation. Calibration and
native quota measurement are still required before these become packages.
All symlinks are resolved inside their declared immutable input, then emitted
as regular files; never copy a provisioned guest's filesystem or credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import subprocess
import tarfile


def require(ok,code):
    if not ok:raise ValueError(code)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()


def package_owner(source,query=subprocess.check_output):
    """Resolve both usr-merge spellings by exact file identity, not a guess."""
    rows=query(['dpkg-query','-S','*/'+source.name],text=True).strip().splitlines();owners=set()
    for row in rows:
        if ': ' not in row:continue
        package,raw=row.split(': ',1);path=Path(raw)
        if path.is_file() and path.resolve()==source:owners.add(package)
    require(len(owners)==1,'NATIVE_LIBRARY_PACKAGE_AMBIGUOUS');return owners.pop()


def package_fields(text,name):
    result={};qualified={}
    for line in text.splitlines():
        key,separator,value=line.partition(': ')
        if not separator:continue
        if key in ('PN','PV','LICENSE','FILES_INFO'):result[key]=value
        elif key in ('LICENSE:'+name,'FILES_INFO:'+name):qualified[key.split(':',1)[0]]=value
    result.update(qualified);return result


def resolve(root,relative):
    """Resolve absolute target links relative to the target root, not Builder /."""
    pending=list(PurePosixPath('/'+str(relative).lstrip('/')).parts[1:]);current=root;links=0
    while pending:
        part=pending.pop(0)
        if part=='.':continue
        if part=='..':require(current!=root,'INPUT_LINK_ESCAPE');current=current.parent;continue
        current=current/part
        if current.is_symlink():
            links+=1;require(links<=32,'INPUT_LINK_CYCLE');target=PurePosixPath(os.readlink(current))
            current=root if target.is_absolute() else current.parent
            pending=list(target.parts[1:] if target.is_absolute() else target.parts)+pending
    require(current.is_relative_to(root) and current.is_file(),'INPUT_FILE_ABSENT');return current


class Closure:
    def __init__(self,destination,clean):self.root=destination;self.clean=clean;self.origins={};self.queue=[];self.scanned=set()

    def copy(self,source,relative,origin):
        relative=PurePosixPath(relative);require(not relative.is_absolute() and '..' not in relative.parts,'OUTPUT_PATH_INVALID')
        require(source.is_file() and not source.is_symlink(),'SOURCE_NOT_REGULAR')
        target=self.root/relative
        if target.exists():require(not target.is_symlink() and digest(target)==digest(source),'CLOSURE_FILE_CONFLICT')
        else:
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);target.chmod(0o555 if os.access(source,os.X_OK) else 0o444)
        self.origins[str(relative)]=origin
        with target.open('rb') as stream:magic=stream.read(20)
        if magic.startswith(b'\x7fELF'):
            require(magic[:5]==b'\x7fELF\x02' and magic[18:20]==b'\xb7\x00','ELF_NOT_LINUX_ARM64');self.queue.append(target)

    def tree(self,source,relative,origin):
        for path in sorted(source.rglob('*')):
            rel=path.relative_to(source)
            if '__pycache__' in rel.parts or path.suffix in ('.pyc','.pyo'):continue
            if origin['kind']=='clean-vision-rootfs' and any(name in rel.parts for name in ('site-packages','test','ensurepip','idlelib','tkinter','turtledemo')):continue
            if path.is_symlink():
                # The selected model/runtime tree is already a link-free lock.
                raise ValueError('RUNTIME_TREE_LINK_FORBIDDEN')
            if path.is_file():
                item=dict(origin)
                if item['kind']=='clean-vision-rootfs':item['path']=str(PurePosixPath(item['path'])/rel.as_posix())
                self.copy(path,str(PurePosixPath(relative)/rel.as_posix()),item)

    def emit(self,relative,value,origin):
        target=self.root/relative;require(not target.exists(),'GENERATED_FILE_EXISTS')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value,indent=2)+'\n');target.chmod(0o444);self.origins[relative]=origin

    def licenses(self,pkgdata,licenses,model_lock=None):
        """Use recipe/package ownership, not a synthesized license guess."""
        require((pkgdata/'runtime').is_dir() and licenses.is_dir(),'BUILD_LICENSE_INPUT_ABSENT')
        owners={};recipes={}
        for path in sorted((pkgdata/'runtime').iterdir()):
            if not path.is_file() or path.is_symlink() or path.stat().st_size>4*1024**2:continue
            data=package_fields(path.read_text(),path.name)
            if 'FILES_INFO' not in data:continue
            files=json.loads(data['FILES_INFO']);require(type(files) is dict,'PKGDATA_FILES_INVALID')
            recipes[path.name]=data
            for filename in files:owners.setdefault(filename,set()).add(path.name)
        require(owners,'PKGDATA_OWNERS_EMPTY')
        selected={}
        for origin in list(self.origins.values()):
            if origin['kind']!='clean-vision-rootfs':continue
            name='/'+origin['path'].lstrip('/');aliases={name}
            if name.startswith('/usr/lib/'):aliases.add(name.removeprefix('/usr'))
            elif name.startswith('/lib/'):aliases.add('/usr'+name)
            packages=set().union(*(owners.get(alias,set()) for alias in aliases));require(len(packages)==1,'CLEAN_RUNTIME_PACKAGE_OWNER_AMBIGUOUS_'+name)
            package=packages.pop();record=recipes[package]
            require(all(record.get(key) for key in ('PN','PV','LICENSE')) and record['LICENSE']!='CLOSED','CLEAN_RUNTIME_LICENSE_MISSING')
            selected[package]=dict(recipe=record['PN'],version=record['PV'],license=record['LICENSE'])
        for recipe in sorted({row['recipe'] for row in selected.values()}):
            require(re.fullmatch('[A-Za-z0-9_.+-]+',recipe) is not None,'LICENSE_RECIPE_INVALID')
            candidates=[p for arch in ('allarch','cortexa57','qemuarm64') if (p:=licenses/arch/recipe).is_dir()]
            require(len(candidates)==1,'RECIPE_NOTICE_ABSENT_OR_AMBIGUOUS_'+recipe);directory=candidates[0]
            copied=0
            for path in sorted(directory.iterdir()):
                if not path.is_file():continue
                source=path.resolve();require(source.stat().st_size<=4*1024**2,'LICENSE_FILE_LIMIT')
                self.copy(source,'app/notices/yocto/'+recipe+'/'+path.name,dict(kind='recipe-license',recipe=recipe,path=path.name));copied+=1
            require(copied>0,'RECIPE_NOTICES_EMPTY')
        debs={r['package']:dict(version=r['version']) for r in self.origins.values() if r['kind']=='pinned-builder-deb'}
        headers={}
        if model_lock is None:
            # Header-only code is incorporated in Assessment's ELF even though
            # it does not appear in DT_NEEDED. Retain those notices as well.
            for package,expected in {'libeigen3-dev':'3.4.0-2ubuntu2','libcppad-dev':'2021.00.00.8-1'}.items():
                version=subprocess.check_output(['dpkg-query','-W','-f=${Version}',package],text=True)
                require(version==expected,'HEADER_BUILD_DEPENDENCY_CHANGED')
                notice=Path('/usr/share/doc')/package/'copyright';require(not notice.is_symlink() and notice.is_file() and notice.stat().st_size<=4*1024**2,'HEADER_BUILD_NOTICE_ABSENT')
                self.copy(notice,'app/notices/build-headers/'+package+'.copyright',dict(kind='header-build-copyright',package=package,version=version))
                headers[package]=dict(version=version,noticeSha256=digest(notice))
        sbom=dict(schemaVersion=1,kind='vision-service-runtime-sbom',yoctoPackages=selected,builderDebs=debs,headerBuildDependencies=headers,
            serviceSourceLicense='Apache-2.0',modelRuntimeInput=model_lock,
            note='Recipe notices, Debian copyright and wheel/upstream license files are retained; this is not a safety/accuracy qualification')
        self.emit('app/notices/sbom.json',sbom,dict(kind='generated-runtime-sbom'))

    def elf_closure(self):
        while self.queue:
            binary=self.queue.pop()
            if binary in self.scanned:continue
            self.scanned.add(binary)
            needed=subprocess.check_output(['readelf','-d',str(binary)],text=True,stderr=subprocess.PIPE)
            names=re.findall(r'\(NEEDED\).*\[([^\]]+)\]',needed)
            rpaths=re.findall(r'\((?:RPATH|RUNPATH)\).*\[([^\]]+)\]',needed)
            search=[binary.parent]
            for row in rpaths:
                for part in row.split(':'):
                    part=part.replace('${ORIGIN}',str(binary.parent)).replace('$ORIGIN',str(binary.parent))
                    path=Path(part)
                    if path.is_absolute() and path.is_relative_to(self.root):search.append(path)
            program=subprocess.check_output(['readelf','-l',str(binary)],text=True,stderr=subprocess.PIPE)
            interpreters=re.findall(r'Requesting program interpreter: ([^\]]+)\]',program)
            for name in names+interpreters:
                require(re.fullmatch(r'[A-Za-z0-9_.+/-]+',name) is not None and '..' not in PurePosixPath(name).parts,'ELF_DEPENDENCY_NAME_INVALID')
                if not name.startswith('/') and any((parent/name).is_file() for parent in search):continue
                candidates=[name.lstrip('/')] if name.startswith('/') else ['usr/lib/'+name,'lib/'+name]
                selected=None
                for candidate in candidates:
                    try:selected=resolve(self.clean,candidate);break
                    except ValueError:pass
                if selected is not None:
                    relative=name.lstrip('/') if name.startswith('/') else 'usr/lib/'+name
                    self.copy(selected,relative,dict(kind='clean-vision-rootfs',path=str(selected.relative_to(self.clean))))
                else:
                    require(not name.startswith('/'),'TARGET_LOADER_ABSENT')
                    # Assessment's target build uses pinned Ubuntu packages.
                    # Core libc/libstdc++ above always come from the clean
                    # target image first; no provisioned-guest fallback.
                    rows=subprocess.check_output(['ldconfig','-p'],text=True).splitlines()
                    paths=[Path(row.split(' => ')[1]) for row in rows if ' => ' in row and row.strip().split()[0]==name and 'aarch64' in row.lower()]
                    require(len(set(paths))==1,'TARGET_DEPENDENCY_UNRESOLVED_'+name)
                    source=paths[0].resolve();require(source.is_file(),'TARGET_DEPENDENCY_ABSENT')
                    # Ubuntu usr-merge: ldconfig may spell /lib while dpkg
                    # owns the same inode under /usr/lib. Query real input.
                    package=package_owner(source);version=subprocess.check_output(['dpkg-query','-W','-f=${Version}',package],text=True)
                    self.copy(source,'usr/lib/'+name,dict(kind='pinned-builder-deb',package=package,version=version,path=str(source)))
                    notice=Path('/usr/share/doc')/package.split(':')[0]/'copyright'
                    require(notice.is_file(),'NATIVE_LIBRARY_NOTICE_ABSENT')
                    self.copy(notice.resolve(),'app/notices/debian/'+package.replace(':','_')+'.copyright',dict(kind='package-copyright',package=package))

    def finish(self):
        files=[]
        for relative,origin in sorted(self.origins.items()):
            path=self.root/relative;files.append(dict(path=relative,bytes=path.stat().st_size,sha256=digest(path),origin=origin))
        return dict(files=files,bytes=sum(row['bytes'] for row in files),count=len(files),elfFiles=len(self.scanned))


def main():
    p=argparse.ArgumentParser()
    for name in ('clean-rootfs','models','assessment-library','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--pkgdata-root',type=Path);p.add_argument('--license-root',type=Path)
    p.add_argument('--source-revision')
    p.add_argument('--models-sha256',required=True);p.add_argument('--assessment-sha256',required=True)
    p.add_argument('--resume-owned',action='store_true');a=p.parse_args()
    require(os.uname().sysname=='Linux' and os.uname().machine=='aarch64','SSD_ARM64_BUILDER_REQUIRED')
    require(a.clean_rootfs.is_dir() and (not a.output.exists() or (a.resume_owned and a.output.is_dir() and not a.output.is_symlink()
        and (a.output/'perception/closure.json').is_file() and not (a.output/'result.json').exists())),'CLOSURE_OUTPUT_EXISTS_OR_INPUT_INVALID')
    require((a.clean_rootfs/'etc/aos/version').read_text().strip()=='VERSION="6.1.1-vision-camera.5"','CLEAN_IMAGE_VERSION_REQUIRED')
    require(not list(a.clean_rootfs.rglob('*.p12')) and not list(a.clean_rootfs.rglob('client-key.pem')),'PROVISIONED_IMAGE_FORBIDDEN')
    require(digest(a.models)==a.models_sha256 and digest(a.assessment_library)==a.assessment_sha256,'INPUT_DIGEST_CHANGED')
    require(a.output.is_absolute() and '..' not in a.output.parts,'OUTPUT_SCOPE_INVALID');a.output.mkdir(mode=0o700,parents=True,exist_ok=a.resume_owned)
    root=Path(__file__).resolve().parents[1];outputs={}
    # Explicit archive lock, bounds, links, duplicates and member digest checks
    # precede extraction. Acquisition is never performed here.
    model_root=a.output/'model-input';reused=model_root.exists()
    require(not reused or a.resume_owned,'MODEL_INPUT_EXISTS_RECONCILE');model_root.mkdir(exist_ok=a.resume_owned)
    with tarfile.open(a.models) as archive:
        rows=archive.getmembers();names=[r.name for r in rows]
        require(len(rows)<10000 and len(names)==len(set(names)) and sum(r.size for r in rows)<350*1024**2,'MODEL_ARCHIVE_LIMIT')
        for row in rows:
            relative=PurePosixPath(row.name)
            require(not relative.is_absolute() and '..' not in relative.parts and relative.parts[0]=='payload' and (row.isfile() or row.isdir()),'MODEL_ARCHIVE_UNSAFE')
            if row.isdir():continue
            destination=model_root/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            if reused:require(destination.is_file() and not destination.is_symlink() and destination.stat().st_size==row.size,'MODEL_INPUT_CHANGED')
            else:
                with archive.extractfile(row) as src,destination.open('xb') as dst:shutil.copyfileobj(src,dst)
    lock=json.loads((model_root/'payload/input-lock.json').read_bytes());require(lock['upstream']=='e7e5c614832f175f1f9f10a0d0c0df2559ff2c38','MODEL_SOURCE_CHANGED')
    for row in lock['files']:
        path=model_root/'payload'/row['path'];require(path.is_file() and path.stat().st_size==row['bytes'] and digest(path)==row['sha256'],'MODEL_MEMBER_CHANGED')
    for service in ('perception','assessment'):
        destination=a.output/service/'rootfs'
        if a.resume_owned and (a.output/service/'closure.json').is_file():
            result=json.loads((a.output/service/'closure.json').read_bytes())
            require({str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()}=={r['path'] for r in result['files']},'COMPLETED_CLOSURE_FILE_SET_CHANGED')
            for row in result['files']:
                path=destination/row['path'];require(not path.is_symlink() and path.stat().st_size==row['bytes'] and digest(path)==row['sha256'],'COMPLETED_CLOSURE_CHANGED')
            outputs[service]={k:v for k,v in result.items() if k!='files'};continue
        destination.mkdir(parents=True,exist_ok=a.resume_owned);closure=Closure(destination,a.clean_rootfs)
        if a.source_revision:
            require(re.fullmatch('[a-f0-9]{40}',a.source_revision) is not None and root.name=='source' and '.tmp' in root.parts,'OWNED_SOURCE_EXPORT_REQUIRED')
            executable=root.parent/(service+'-launcher')
            subprocess.run(['gcc','-O2','-Wall','-Wextra','-Werror','-fstack-protector-strong','-Wl,-z,relro,-z,now',
                str(root/'apps/common/launcher.c'),'-o',str(executable)],env=dict(os.environ,TMPDIR=str(root.parent)),check=True,capture_output=True,timeout=30)
            closure.copy(executable,'usr/bin/vision-'+service,dict(kind='vision-service-launcher',sourceRevision=a.source_revision,source='apps/common/launcher.c'))
            closure.emit('app/service-manifest.json',dict(schemaVersion=1,codename='vision-'+service,version='0.1.0',sourceRevision=a.source_revision,
                upstream=lock['upstream']),dict(kind='generated-service-identity'))
            entry='''# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import sys
sys.path[:0]=['/app/common','/app','/app/libraries']
from vision_SERVICE.__main__ import main
raise SystemExit(main())
'''.replace('SERVICE',service)
            (destination/'app').mkdir(exist_ok=True);(destination/'app/entry.py').write_text(entry);(destination/'app/entry.py').chmod(0o444)
            closure.origins['app/entry.py']=dict(kind='generated-fixed-entry',sourceRevision=a.source_revision)
        closure.copy(resolve(a.clean_rootfs,'usr/bin/python3.12'),'usr/bin/python3.12',dict(kind='clean-vision-rootfs',path='usr/bin/python3.12'))
        closure.tree(a.clean_rootfs/'usr/lib/python3.12','usr/lib/python3.12',dict(kind='clean-vision-rootfs',path='usr/lib/python3.12'))
        closure.tree(root/'common','app/common',dict(kind='vision-pilot-services',path='common'))
        closure.tree(root/'apps'/service/('vision_'+service),'app/vision_'+service,dict(kind='vision-pilot-services',path='apps/'+service))
        for notice in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md'):
            closure.copy(root/notice,'app/notices/'+notice,dict(kind='vision-pilot-services',path=notice))
        if service=='perception':
            closure.tree(model_root/'payload/libraries','app/libraries',dict(kind='verified-model-runtime',archiveSha256=a.models_sha256))
            closure.tree(model_root/'payload/models','app/models',dict(kind='verified-model-runtime',archiveSha256=a.models_sha256))
            closure.copy(model_root/'payload/UPSTREAM-LICENSE','app/notices/VisionPilot-LICENSE',dict(kind='verified-model-runtime',archiveSha256=a.models_sha256))
        else:closure.copy(a.assessment_library,'app/lib/libvision_assessment.so',dict(kind='ssd-native-assessment',sha256=a.assessment_sha256))
        closure.elf_closure()
        if a.pkgdata_root or a.license_root:
            require(a.pkgdata_root is not None and a.license_root is not None,'BOTH_LICENSE_INPUTS_REQUIRED')
            closure.licenses(a.pkgdata_root,a.license_root,dict(archiveSha256=a.models_sha256,upstream=lock['upstream']) if service=='perception' else None)
        result=closure.finish();ceiling=512*1024**2 if service=='perception' else 256*1024**2
        require(result['bytes']<=ceiling and result['count']<10000,'CLOSURE_PROFILE_OVERFLOW')
        result.update(service='vision-'+service,version='0.1.0',maximumExtractedBytes=ceiling,licenseNoticesIncluded=bool(a.pkgdata_root),
            status='MEASURED_CLOSURE_NOT_SIGNABLE_WITHOUT_NATIVE_MEASUREMENTS_AND_DELIVERY_GATES')
        (a.output/service/'closure.json').write_text(json.dumps(result,indent=2)+'\n');outputs[service]={k:v for k,v in result.items() if k!='files'}
    # Model input remains a retained, hash-verified build input, not anonymous
    # scratch. No program starts and no interpreted/model output is claimed.
    (a.output/'result.json').write_text(json.dumps(dict(outcome='MEASURED_ARM64_CLOSURES_NOT_DEPLOYED',services=outputs,modelsExecuted=False,imageTasks=False),indent=2)+'\n')
    print(json.dumps(dict(outcome='MEASURED_ARM64_CLOSURES_NOT_DEPLOYED',services=outputs,modelsExecuted=False,imageTasks=False)))


if __name__=='__main__':main()
