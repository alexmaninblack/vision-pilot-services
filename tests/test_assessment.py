# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest
from unittest.mock import Mock
from vision_assessment.core import Assessment
from vision_common.protocol import Invalid
import fixtures as f


def estimate():
    return dict(lead=dict(valid=True,present=False,distanceMetres=None,relativeSpeedMps=None,distanceStddevMetres=None),
        path=dict(valid=True,points=[[1.,0.],[2.,0.]],crossTrackMetres=0.,yawRadians=0.,curvaturePerMetre=0.),
        plan=dict(valid=True,accelerationMps2=0.,steeringRadians=[0.]*20))


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.algorithm=Mock();self.algorithm.update.return_value=estimate()
        self.core=Assessment(self.algorithm,epoch=f.uid(5),clock=lambda:1.)

    def test_first_warms_then_actual_elapsed_time_is_given_to_upstream(self):
        first=self.core.process(f.perception(),f.context());self.assertEqual(first['state'],'WARMING');self.algorithm.update.assert_not_called()
        second=self.core.process(f.perception(2,5),f.context(5));self.assertEqual(second['state'],'AVAILABLE')
        self.assertEqual(self.algorithm.update.call_args.args[-1],.3)
        self.assertFalse(second['lead']['present']);self.assertIsNone(second['lead']['distanceMetres'])

    def test_missing_speed_or_geometry_never_invents_a_plan(self):
        for field in ('dynamics','vehicleProfile'):
            core=Assessment(self.algorithm,epoch=f.uid(5),clock=lambda:1.);core.process(f.perception(),None)
            c=f.context(3);c[field]['available']=False
            for name in c[field]:
                if name!='available':c[field][name]=None
            value=core.process(f.perception(2,3),c)
            self.assertEqual(value['state'],'UNAVAILABLE');self.assertFalse(value['plan']['valid'])
        self.algorithm.update.assert_not_called()

    def test_wrong_source_or_frame_does_not_reach_algorithm(self):
        self.core.process(f.perception(),None);context=f.context(3);context['binding']['sourceEpoch']=f.uid(88)
        with self.assertRaisesRegex(Invalid,'CONTEXT_CAPTURE_MISMATCH'):self.core.process(f.perception(2,3),context)
        self.algorithm.update.assert_not_called()

    def test_gap_and_producer_restart_reset_upstream_and_warm(self):
        self.core.process(f.perception(),None)
        value=self.core.process(f.perception(2,20),f.context(20));self.assertEqual(value['state'],'WARMING')
        next_raw=f.perception(1,21);next_raw['producer']['epoch']=f.uid(90)
        value=self.core.process(next_raw,f.context(21));self.assertEqual(value['state'],'WARMING')
        self.algorithm.update.assert_not_called();self.assertEqual(self.algorithm.reset.call_count,3)

    def test_context_recovery_does_not_resurrect_old_tracking(self):
        self.core.process(f.perception(),None)
        self.assertEqual(self.core.process(f.perception(2,3),None)['state'],'UNAVAILABLE')
        self.assertEqual(self.core.process(f.perception(3,4),f.context(4))['state'],'WARMING')
        self.algorithm.update.assert_not_called()
        self.assertEqual(self.core.process(f.perception(4,5),f.context(5))['state'],'AVAILABLE')

    def test_upstream_cut_is_not_a_second_copy_of_the_inference_executable(self):
        import json,hashlib
        root=Path(__file__).resolve().parents[1];lock=json.loads((root/'dependencies/upstream.json').read_bytes())
        self.assertEqual(lock['revision'],'e7e5c614832f175f1f9f10a0d0c0df2559ff2c38')
        for row in lock['importedFiles']:
            data=(root/row['path']).read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
        headers=list((root/'third_party/vision_pilot/VisionPilot/modules/models/include/models').glob('*.hpp'))
        self.assertEqual(len(headers),3)
        for header in headers:
            text=header.read_text();self.assertNotIn('#include <engine/',text);self.assertNotIn('#include <onnxruntime_',text)
        planner=(root/'third_party/vision_pilot/VisionPilot/modules/safety_guardian/planning/src/planning.cpp').read_text()
        self.assertIn('ego_v * elapsed_seconds',planner);self.assertIn('v_plan + a_plan * dt',planner)


if __name__=='__main__':unittest.main()
