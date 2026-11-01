# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
import unittest
from vision_common import protocol as p
import fixtures as f


class CalibrationTests(unittest.TestCase):
    def test_full_profile_document_digest_and_original_model_view(self):
        profile=f.profile();decoded=p.calibration_profile(profile,profile['id']);self.assertEqual(decoded['modelViewToVehicle'],p.MODEL_VIEW)
        for field in ('origin','camera','projection'):
            changed=copy.deepcopy(decoded)
            if field=='camera':changed[field]['mountTranslationMetres'][0]+=1
            elif field=='projection':changed[field]['maximumPlaneResidualMetres']=20
            else:changed[field]['sha256']='0'*64
            document=json.dumps(changed);wrong=dict(document=document,id=hashlib.sha256(document.encode()).hexdigest())
            with self.assertRaises(p.Invalid):p.calibration_profile(wrong,wrong['id'])
        profile['document']+=' '
        with self.assertRaisesRegex(p.Invalid,'DIGEST_MISMATCH'):p.calibration_profile(profile,profile['id'])

    def test_per_capture_pair_has_two_nonsingular_maps_and_no_dynamics(self):
        context=f.context();cal=copy.deepcopy(context['calibration']);cal['rawToModel']=[cal['rawToModel'],[[1.,0.,2.],[0.,1.,0.],[0.,0.,1.]]]
        cal['resizedToVehicle']=[p.resized_mapping(raw) for raw in cal['rawToModel']]
        value=dict(schemaVersion=1,kind='calibration',binding=f.binding(),frames=[f.frame(1),f.frame(2)],calibration=cal)
        p.calibration(value);self.assertLess(len(p.dumps(value)),4096)
        value['dynamics']=context['dynamics']
        with self.assertRaises(p.Invalid):p.calibration(value)
        value.pop('dynamics');value['calibration']['rawToModel'][1]=[[0.]*3]*3
        with self.assertRaisesRegex(p.Invalid,'SINGULAR'):p.calibration(value)

    def test_unavailable_is_explicit_null_not_old_profile_or_default_map(self):
        value=f.context();value['calibration']=dict(available=False,reason='PLANE_UNAVAILABLE',profile=None,rawToModel=None,resizedToVehicle=None);p.context(value)
        value['calibration']['profile']=f.profile()
        with self.assertRaises(p.Invalid):p.context(value)

    def test_training_view_is_not_a_valid_substitute_for_resized_fusion_pixels(self):
        value=f.context();value['calibration']['resizedToVehicle']=p.MODEL_VIEW
        with self.assertRaisesRegex(p.Invalid,'MAP_INCOMPATIBLE'):p.context(value)


if __name__=='__main__':unittest.main()
