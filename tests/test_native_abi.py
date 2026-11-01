# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import ctypes
import unittest
from vision_assessment.native import encode,decode,Input,Output
from vision_common.protocol import Invalid
import fixtures as f


class NativeAbiTests(unittest.TestCase):
    def test_encoded_models_and_elapsed_time_have_no_control_transport(self):
        value=encode(f.perception(),f.context(),.3,[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
        self.assertEqual(value.abi,1);self.assertEqual(value.flags,7);self.assertEqual(value.elapsed_seconds,.3)
        self.assertEqual(value.speed_mps,10.);self.assertEqual(value.box_count,0);self.assertEqual(value.xp[0],.5)
        self.assertGreater(ctypes.sizeof(Input),3000);self.assertGreater(ctypes.sizeof(Output),1000)

    def test_free_road_sentinel_is_not_a_detected_object(self):
        value=Output();value.abi=1;value.lead_valid=1;value.lead_present=0;value.distance_m=150.
        result=decode(value);self.assertFalse(result['lead']['present']);self.assertIsNone(result['lead']['distanceMetres'])

    def test_native_output_cannot_overrun_fixed_arrays(self):
        value=Output();value.abi=1;value.path_count=65
        with self.assertRaises(Invalid):decode(value)
        value.path_count=0;value.steering_count=65
        with self.assertRaises(Invalid):decode(value)


if __name__=='__main__':unittest.main()
