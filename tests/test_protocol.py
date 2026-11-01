# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import copy
import json
from pathlib import Path
import unittest
from vision_common import protocol as p
from vision_common.temporal import Temporal
import fixtures as f


class ProtocolTests(unittest.TestCase):
    def test_golden_roundtrips_and_semantic_digest(self):
        for value in (f.perception(),f.context(),f.assessment()):
            self.assertEqual(p.validate(p.loads(p.dumps(value))),value)
            self.assertEqual(p.digest(value),p.digest(dict(reversed(list(value.items())))))

    def test_closed_fields_and_strict_scalars(self):
        for make in (f.perception,f.context,f.assessment):
            for mutate in (lambda v:v.update(control='throttle'),lambda v:v.update(schemaVersion=True),
                    lambda v:v['binding'].update(privateKey='forbidden'),lambda v:v['binding'].update(sourceId='foreign')):
                value=make();mutate(value)
                with self.subTest(kind=value['kind']),self.assertRaises(p.Invalid):p.validate(value)

    def test_pair_time_and_frame_guards(self):
        for mutate in (lambda v:v['frames'][1].update(frame=1),lambda v:v['frames'][1].update(simulationTimeNs=350000000),
                lambda v:v['frames'][0].update(sha256='not-a-hash'),lambda v:v['frames'][0].update(sensorSimulationTimeNs=999999999),
                lambda v:v['producer'].update(sequence=True)):
            value=f.perception();mutate(value)
            with self.assertRaises(p.Invalid):p.validate(value)

    def test_nonfinite_duplicate_and_byte_limits(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'{} trailing',b'\xff'):
            with self.subTest(raw=raw),self.assertRaises(p.Invalid):p.loads(raw)
        with self.assertRaises(p.Invalid):p.loads(b' '*65537)
        with self.assertRaises(p.Invalid):p.dumps(dict(value=float('nan')))
        value=f.perception();value['models']['autodrive']['curvatureRaw']=float('inf')
        with self.assertRaises(p.Invalid):p.validate(value)

    def test_raw_shapes_counts_and_probability_consistency(self):
        for mutate in (lambda v:v['models']['autosteer'].update(xp=[0.]*65),lambda v:v['models']['autosteer'].update(confidence=[float('inf')]*64),
                lambda v:v['models']['autospeed'].update(detections=[{}]*129),lambda v:v.update(modelProfile='int8'),
                lambda v:v['models']['autodrive'].update(distanceNormalized=1.1)):
            value=f.perception();mutate(value)
            with self.assertRaises(p.Invalid):p.validate(value)
        value=f.perception();d=dict(box=[1.,2.,3.,4.],score=.9,classId=1,probabilities=[.1,.9,.2,.1])
        value['models']['autospeed']['detections']=[d];p.validate(value)
        d['classId']=2
        with self.assertRaises(p.Invalid):p.validate(value)

    def test_missing_is_nullable_not_zero_or_a_150m_target(self):
        value=f.context();value['dynamics']=dict(available=False,speedMps=None,simulationTimeNs=None);p.validate(value)
        value['dynamics']['speedMps']=0.
        with self.assertRaises(p.Invalid):p.validate(value)
        value=f.assessment();value.update(state='AVAILABLE',deltaSimulationNs=100000000)
        value['lead']=dict(valid=True,present=False,distanceMetres=None,relativeSpeedMps=None,distanceStddevMetres=None);p.validate(value)
        value['lead']['distanceMetres']=150.
        with self.assertRaises(p.Invalid):p.validate(value)

    def test_stale_or_warming_cannot_publish_valid_estimates(self):
        value=f.assessment();value['lead']=dict(valid=True,present=False,distanceMetres=None,relativeSpeedMps=None,distanceStddevMetres=None)
        with self.assertRaises(p.Invalid):p.validate(value)
        value=f.assessment();value['plan']=dict(valid=True,accelerationMps2=0.,steeringRadians=[0.])
        with self.assertRaises(p.Invalid):p.validate(value)

    def test_approved_projection_pin_and_shape_match(self):
        root=Path(__file__).resolve().parents[1];profile=p.load_profile(root)
        self.assertEqual(set(profile['dtos']['common']['bindingFields']),set(p.BINDING))
        self.assertEqual(set(profile['dtos']['common']['frameFields']),set(p.FRAME))
        for make in (f.perception,f.context,f.assessment):
            value=make();self.assertEqual(set(value),set(profile['dtos'][value['kind']]['fields']))
        self.assertEqual(profile['upstream']['precision'],'FP32')


class TemporalTests(unittest.TestCase):
    def test_first_and_real_inter_output_delta_not_pair_interval(self):
        gate=Temporal();self.assertTrue(gate.admit(f.perception())['warming'])
        result=gate.admit(f.perception(2,5))
        self.assertEqual(result['deltaSimulationNs'],300000000);self.assertFalse(result['warming'])

    def test_epoch_calibration_and_gap_reset_without_fabricated_delta(self):
        for change in ('sourceEpoch','componentEpoch','calibrationId','producer','gap'):
            gate=Temporal();gate.admit(f.perception());value=f.perception(2,3)
            if change=='producer':value['producer']['epoch']=f.uid(99)
            elif change=='gap':value=f.perception(2,15)
            else:value['binding'][change]='other-calibration' if change=='calibrationId' else f.uid(99)
            with self.subTest(change=change):self.assertTrue(gate.admit(value)['warming'])

    def test_regression_does_not_erase_high_water_mark(self):
        gate=Temporal();gate.admit(f.perception(5,10))
        for _ in range(2):
            with self.assertRaisesRegex(p.Invalid,'TEMPORAL_REGRESSION'):gate.admit(f.perception(4,9))
        self.assertTrue(gate.admit(f.perception(6,11))['warming'])
        self.assertFalse(gate.admit(f.perception(7,12))['warming'])


if __name__=='__main__':unittest.main()
