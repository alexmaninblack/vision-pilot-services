# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Pure chronological gate; no clock-domain subtraction or timestamp repair."""
from .protocol import perception,Invalid


class Temporal:
    def __init__(self):self.reset()

    def reset(self):self.key=None;self.last_time=None;self.last_frame=None;self.last_sequence=None;self.needs_warm=False

    def admit(self,value):
        perception(value);b=value['binding'];p=value['producer'];f=value['frames'][-1]
        key=tuple(b[k] for k in ('componentEpoch','sourceId','sourceEpoch','cameraId','calibrationId'))+(p['epoch'],value['modelProfile'],value['preprocessingProfile'])
        stamp=f['simulationTimeNs'];reason='FIRST_INPUT';delta=None
        if self.key==key:
            if p['sequence']<=self.last_sequence or f['frame']<=self.last_frame or stamp<=self.last_time:
                self.needs_warm=True;raise Invalid('TEMPORAL_REGRESSION')
            elapsed=stamp-self.last_time
            if self.needs_warm:reason='RECOVERY_AFTER_REGRESSION'
            elif elapsed>1000000000:reason='CAPTURE_GAP'
            else:reason='CURRENT';delta=elapsed
        elif self.key is not None:reason='EPOCH_CHANGED'
        self.key=key;self.last_time=stamp;self.last_frame=f['frame'];self.last_sequence=p['sequence'];self.needs_warm=False
        return dict(warming=delta is None,reason=reason,deltaSimulationNs=delta)
