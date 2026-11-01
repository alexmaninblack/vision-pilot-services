# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import math
import unittest
from vision_common.protocol import Invalid
from vision_common.jpeg import dimensions
from vision_perception import outputs as o
from vision_perception.runtime import calibration


class PerceptionTests(unittest.TestCase):
    def test_sigmoid_raw_distance_and_curvature_are_not_shadow_planning(self):
        value=o.autodrive([.25,-.1,0.]);self.assertEqual(value,dict(valid=True,distanceNormalized=.25,curvatureRaw=-.1,presenceProbability=.5))
        self.assertEqual(o.sigmoid(-1000),0.);self.assertEqual(o.sigmoid(1000),1.)
        for values in ([.5,0.],[-.1,0.,1.],[.5,float('nan'),1.]):
            with self.assertRaises(Invalid):o.autodrive(values)

    def test_all_raw_path_positions_retained_even_outside_image(self):
        positions=[.5]*64;positions[0]=-1.
        value=o.autosteer(positions,[.8]*64);self.assertEqual(value['xp'],positions)
        with self.assertRaises(Invalid):o.autosteer([0.]*63,[1.]*64)

    def test_class_agnostic_nms_matches_upstream_thresholds(self):
        rows=[dict(box=[0.,0.,10.,10.],score=.9,classId=1),dict(box=[1.,1.,11.,11.],score=.8,classId=2),dict(box=[20.,20.,30.,30.],score=.7,classId=0)]
        self.assertEqual([r['classId'] for r in o.nms(rows)],[1,0])
        self.assertEqual(o.iou([0.,0.,1.,1.],[2.,2.,3.,3.]),0.)

    def test_actual_export_anchor_count_and_four_raw_probabilities(self):
        rows=[[0.]*10752 for _ in range(4)]+[[-20.]*10752 for _ in range(4)]
        for c,v in enumerate((100.,50.,20.,10.)):rows[c][0]=v
        rows[5][0]=2.
        result=o.autospeed(rows);self.assertEqual(len(result['detections']),1)
        d=result['detections'][0];self.assertEqual(d['box'],[90.,45.,110.,55.]);self.assertEqual(d['classId'],1)
        self.assertEqual(len(d['probabilities']),4)
        with self.assertRaises(Invalid):o.autospeed([[0.]*3 for _ in range(8)])

    def test_calibration_is_bound_nonsingular_and_not_foreign_geometry(self):
        import fixtures as f
        import json,hashlib
        value=f.profile();calibration(value,value['id'])
        with self.assertRaises(Invalid):calibration(value,'foreign')
        data=json.loads(value['document']);data['modelToVehicle']=[[0.]*3 for _ in range(3)]
        value['document']=json.dumps(data);value['id']=hashlib.sha256(value['document'].encode()).hexdigest()
        with self.assertRaises(Invalid):calibration(value,value['id'])

    def test_dimensions_checked_without_decode_allocation(self):
        raw=b'\xff\xd8\xff\xc0\x00\x11\x08\x02\xd0\x05\x00\x03'+b'\x01\x11\x00'*3+b'\xff\xd9'
        self.assertEqual(dimensions(raw),(1280,720))
        for value in (b'not jpeg',raw.replace(b'\x05\x00',b'\x50\x00'),raw[:-2],raw.replace(b'\x02\xd0',b'\x00\x01')):
            with self.assertRaises(Invalid):dimensions(value)


if __name__=='__main__':unittest.main()
