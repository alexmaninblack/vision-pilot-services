# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Small synthetic DTOs only; no recorded pixels or real identities."""
from uuid import UUID
import hashlib,json
from vision_common import protocol as p


def uid(value):return str(UUID(int=value))


def profile():
    value=dict(schemaVersion=1,profile=p.PREPROCESSING_PROFILE,scope='PLANAR_REFERENCE_ONLY',camera=dict(width=1280,height=720,horizontalFovDegrees=50.,
        mountTranslationMetres=[1.6,0.,1.5],mountRotationDegrees=[0.,0.,0.]),modelToVehicle=p.MODEL_VIEW,origin=p.CALIBRATION_ORIGIN,
        projection=dict(algorithm='CARLA_PINHOLE_LOCAL_PLANAR_V1',coordinates='forward-metres-left-positive',maximumPlaneResidualMetres=.02,maximumNormalAngleDegrees=.5,referenceDistancesMetres=[15,30,75,150]))
    document=json.dumps(value,separators=(',',':'));return dict(id=hashlib.sha256(document.encode()).hexdigest(),document=document)


def binding():return dict(componentEpoch=uid(1),sourceId=uid(2),sourceEpoch=uid(3),cameraId='front',calibrationId=profile()['id'])


def frame(number=2):return dict(frame=number,simulationTimeNs=number*100000000,sensorSimulationTimeNs=number*100000000,sha256='a'*64)


def producer(sequence=1):return dict(epoch=uid(4),sequence=sequence,serviceVersion='0.1.0')


def perception(sequence=1,current=2):
    return dict(schemaVersion=1,kind='perception',binding=binding(),frames=[frame(current-1),frame(current)],producer=producer(sequence),
        modelProfile='vision-pilot-fp32-v1',preprocessingProfile='carla-forward-720p-fov50-v1',
        models=dict(autodrive=dict(valid=True,distanceNormalized=.5,curvatureRaw=0.,presenceProbability=.9),
            autosteer=dict(valid=True,xp=[.5]*64,confidence=[1.]*64),autospeed=dict(valid=True,detections=[])),timingsMs=dict(total=1.))


def context(current=2):return dict(schemaVersion=1,kind='context',binding=binding(),frame=frame(current),
    dynamics=dict(available=True,speedMps=10.,simulationTimeNs=current*100000000),
    vehicleProfile=dict(id='unit-geometry',available=True,frontAxleToCogM=1.2,speedLimitMps=15.),
    calibration=dict(available=True,reason='CURRENT',profile=profile(),rawToModel=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]))


def assessment():
    p=perception()
    return dict(schemaVersion=1,kind='assessment',binding=p['binding'],frames=p['frames'],producer=producer(),
        input=dict(p['producer'],modelProfile=p['modelProfile'],preprocessingProfile=p['preprocessingProfile']),
        state='WARMING',reason='FIRST_INPUT',deltaSimulationNs=None,
        lead=dict(valid=False,present=None,distanceMetres=None,relativeSpeedMps=None,distanceStddevMetres=None),
        path=dict(valid=False,points=None,crossTrackMetres=None,yawRadians=None,curvaturePerMetre=None),
        plan=dict(valid=False,accelerationMps2=None,steeringRadians=None),timingsMs=dict(total=1.))
