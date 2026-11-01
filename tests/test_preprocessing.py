# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np
from vision_perception.preprocessing import chw,tensors


class PreprocessingTests(unittest.TestCase):
    def test_color_layout_scaling_and_distinct_normalization(self):
        image=np.asarray([[[0,0,255],[255,0,0]]],dtype=np.uint8)
        plain=chw(image,np);self.assertEqual(plain.shape,(1,3,1,2));self.assertEqual(plain.dtype,np.float32)
        np.testing.assert_array_equal(plain[0,:,0,0],[1.,0.,0.]);np.testing.assert_array_equal(plain[0,:,0,1],[0.,0.,1.])
        normalized=chw(image,np,True)
        np.testing.assert_allclose(normalized[0,:,0,0],[(1-.485)/.229,-.456/.224,-.406/.225],rtol=1e-6)
        self.assertTrue(plain.flags.c_contiguous);self.assertTrue(normalized.flags.c_contiguous)

    def test_plain_top_crop_and_temporal_homography_are_not_interchanged(self):
        image=np.zeros((720,1280,3),np.uint8);resized=np.zeros((512,1024,3),np.uint8)
        cv2=SimpleNamespace(resize=Mock(return_value=resized),warpPerspective=Mock(return_value=resized),INTER_LINEAR=1,BORDER_REFLECT_101=4)
        matrix=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
        plain,pair=tensors([image,image],dict(rawToModel=matrix),np,cv2)
        self.assertEqual(cv2.resize.call_args.args[0].shape,(640,1280,3));self.assertEqual(cv2.resize.call_args.args[1],(1024,512))
        self.assertEqual(cv2.warpPerspective.call_count,2)
        for call in cv2.warpPerspective.call_args_list:
            np.testing.assert_array_equal(call.args[1],matrix);self.assertEqual(call.kwargs['borderMode'],4)
        self.assertEqual(plain.shape,(1,3,512,1024));self.assertEqual(len(pair),2)


if __name__=='__main__':unittest.main()
