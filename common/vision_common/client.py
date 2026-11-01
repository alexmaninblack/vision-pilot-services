# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Fixed native resource client. No URL, credential, network or role override."""
import hashlib
from pathlib import Path
import socket
import time
from . import ipc,protocol as p
from .jpeg import dimensions

ROLES={'perception-publish':('status','publish'),'perception-read':('status','latest'),
    'context-read':('status','context'),'assessment-publish':('status','publish')}
ROOT=Path('/run/aosedge/vision')
CAMERA=Path('/run/aosedge/platform/camera/camera.sock')


class Client:
    def __init__(self,role):
        p.require(role in ROLES,'RESOURCE_ROLE_INVALID');self.role=role;self.path=ROOT/role/'exchange.sock';self.epoch=None

    def request(self,operation,*,value=None,after=None,binding=None,frame=None,frames=None):
        p.require(operation in ROLES[self.role],'RESOURCE_OPERATION_DENIED')
        request=dict(schemaVersion=1,operation=operation)
        capture_status=operation=='status' and (binding is not None or frames is not None)
        if capture_status:
            p.require(self.role=='perception-publish','RESOURCE_OPERATION_DENIED');p.binding(binding);p.frames(frames)
            request.update(binding=binding,frames=frames)
        if operation!='status':p.identity(self.epoch);request['exchangeEpoch']=self.epoch
        if operation=='publish':
            p.validate(value);raw=p.dumps(value);request['payloadBytes']=len(raw)
        elif operation=='latest':
            request.update(afterEpoch=None if after is None else after['epoch'],afterSequence=0 if after is None else after['sequence'])
        elif operation=='context':p.binding(binding);p.frame(frame);request.update(binding=binding,frame=frame)
        deadline=time.monotonic()+2
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(2);connection.connect(str(self.path));ipc.send(connection,request,deadline,p.MAX_REQUEST)
            if operation=='publish':ipc.send(connection,value,deadline)
            response=ipc.receive(connection,deadline,p.MAX_REQUEST)
            p.fields(response,('schemaVersion','exchangeEpoch','state','reason'))
            p.require(type(response['schemaVersion']) is int and response['schemaVersion']==1,'EXCHANGE_RESPONSE_INVALID')
            p.label(response['reason'])
            if response.get('state')=='REJECTED':raise p.Invalid(p.label(response.get('reason')))
            p.identity(response.get('exchangeEpoch'))
            if operation=='status':self.epoch=response['exchangeEpoch']
            else:p.require(self.epoch==response['exchangeEpoch'],'EXCHANGE_EPOCH_CHANGED')
            if response.get('state') in ('RESULT','CONTEXT','CALIBRATION'):
                p.require((operation,response['state']) in (('latest','RESULT'),('context','CONTEXT'),('status','CALIBRATION')),'EXCHANGE_STATE_INVALID')
                p.require(response['state']!='CALIBRATION' or capture_status,'EXCHANGE_STATE_INVALID')
                message=ipc.receive(connection,deadline,p.MAX_RESULT if operation=='latest' else p.MAX_REQUEST);p.validate(message)
                p.require(message['kind']=={'latest':'perception','context':'context','status':'calibration'}[operation],'EXCHANGE_KIND_INVALID');return message
            p.require(response['state'] in {'status':('STATUS',),'publish':('ACCEPTED',),'latest':('UNCHANGED','UNAVAILABLE'),'context':('UNAVAILABLE',)}[operation],'EXCHANGE_STATE_INVALID')
            return response


def camera_pair():
    deadline=time.monotonic()+2
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(2);connection.connect(str(CAMERA));ipc.send(connection,dict(schemaVersion=1,operation='pair'),deadline,p.MAX_REQUEST)
        response=ipc.receive(connection,deadline,p.MAX_REQUEST)
        p.require(response.get('schemaVersion')==1 and response.get('state') in ('PAIR','NO_PAIR'),'CAMERA_RESPONSE_INVALID')
        if response['state']=='NO_PAIR':return None
        p.fields(response,('schemaVersion','componentEpoch','status','state','frames'));p.identity(response['componentEpoch'])
        metadata=response['frames'];p.require(type(metadata) is list and len(metadata)==2,'CAMERA_PAIR_INVALID')
        wanted=('schemaVersion','profile','sourceId','sourceEpoch','cameraId','calibrationId','frame','simulationTimeNs','sensorSimulationTimeNs','clock','encoding','width','height','payloadBytes','sha256')
        binding=None;frames=[];jpegs=[]
        for row in metadata:
            p.fields(row,wanted)
            p.require(type(row['schemaVersion']) is int and row['schemaVersion']==1 and row['profile']=='front-rgb-jpeg-720p-v1'
                and row['clock']=='CARLA_WORLD_SNAPSHOT_FRAME_MATCH' and row['encoding']=='JPEG'
                and type(row['width']) is int and row['width']==1280 and type(row['height']) is int and row['height']==720,'CAMERA_PROFILE_INVALID')
            current=dict(componentEpoch=response['componentEpoch'],**{k:row[k] for k in p.BINDING if k!='componentEpoch'});p.binding(current)
            if binding is None:binding=current
            p.require(binding==current,'CAMERA_BINDING_MISMATCH')
            frame={k:row[k] for k in p.FRAME};p.frame(frame);frames.append(frame)
            size=p.integer(row['payloadBytes'],1,4194304);raw=ipc.exact(connection,size,deadline)
            p.require(hashlib.sha256(raw).hexdigest()==row['sha256'],'CAMERA_BODY_HASH_MISMATCH');dimensions(raw);jpegs.append(raw)
        p.frames(frames);return binding,frames,jpegs
