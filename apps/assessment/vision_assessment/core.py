# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Pure identity/time/validity owner around an injected upstream algorithm."""
import time
from uuid import uuid4
from vision_common import protocol as p
from vision_common.temporal import Temporal


def absent():
    return dict(lead=dict(valid=False,present=None,distanceMetres=None,relativeSpeedMps=None,distanceStddevMetres=None),
        path=dict(valid=False,points=None,crossTrackMetres=None,yawRadians=None,curvaturePerMetre=None),
        plan=dict(valid=False,accelerationMps2=None,steeringRadians=None))


class Assessment:
    def __init__(self,algorithm,epoch=None,clock=time.monotonic,service_version='0.1.0'):
        p.version(service_version)
        self.algorithm=algorithm;self.temporal=Temporal();self.epoch=epoch or str(uuid4());self.sequence=0;self.clock=clock;self.recovering=False;self.version=service_version

    def process(self,raw,context):
        p.perception(raw);began=self.clock();current=raw['frames'][-1];binding=raw['binding'];source=raw['producer']
        try:temporal=self.temporal.admit(raw)
        except p.Invalid:self.algorithm.reset();self.recovering=True;raise
        self.sequence+=1
        result=dict(schemaVersion=1,kind='assessment',binding=dict(binding),frames=list(raw['frames']),
            producer=dict(epoch=self.epoch,sequence=self.sequence,serviceVersion=self.version),
            input=dict(source,modelProfile=raw['modelProfile'],preprocessingProfile=raw['preprocessingProfile']),
            state='UNAVAILABLE',reason='CONTEXT_UNAVAILABLE',deltaSimulationNs=temporal['deltaSimulationNs'],**absent(),timingsMs=dict(total=0.))
        if temporal['warming']:
            self.algorithm.reset();self.recovering=False;result.update(state='WARMING',reason=temporal['reason'])
        else:
            matched=False
            if context is not None:
                p.context(context)
                matched=context['binding']==binding and context['frame']==current
                if not matched:self.algorithm.reset();self.recovering=True;raise p.Invalid('CONTEXT_CAPTURE_MISMATCH')
            models_valid=all(value['valid'] for value in raw['models'].values())
            if not models_valid:self.algorithm.reset();self.recovering=True;result['reason']='PERCEPTION_INVALID'
            elif matched and not context['calibration']['available']:
                self.algorithm.reset();self.recovering=True;result['reason']='CALIBRATION_UNAVAILABLE'
            elif not matched:
                self.algorithm.reset();self.recovering=True;result['reason']='CONTEXT_UNAVAILABLE'
            elif self.recovering:
                self.algorithm.reset();self.recovering=False;result.update(state='WARMING',reason='INPUT_RECOVERED')
            else:
                try:
                    value=self.algorithm.update(raw,context,temporal['deltaSimulationNs']/1e9)
                    p.fields(value,('lead','path','plan'))
                    if not context['dynamics']['available'] or not context['vehicleProfile']['available']:
                        # Factual model/fusion outputs remain distinct from a
                        # plan requiring measured dynamics and geometry.
                        value=dict(value,plan=absent()['plan'])
                    result.update(state='AVAILABLE',reason='CURRENT',**value)
                    p.assessment(result)
                except p.Invalid:
                    self.algorithm.reset();self.recovering=True;result.update(state='UNAVAILABLE',reason='ALGORITHM_INVALID',**absent())
        result['timingsMs']['total']=(self.clock()-began)*1000;p.assessment(result);return result
