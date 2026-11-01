# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Pure array transformation; NumPy is injected in isolated unit tests."""


def chw(image,np,normalized=False):
    value=np.ascontiguousarray((image[:,:,::-1].astype(np.float32)/np.float32(255)).transpose(2,0,1)[None])
    if normalized:
        mean=np.asarray([.485,.456,.406],np.float32).reshape(1,3,1,1)
        std=np.asarray([.229,.224,.225],np.float32).reshape(1,3,1,1)
        value=np.ascontiguousarray((value-mean)/std)
    return value


def tensors(decoded,profile,np,cv2):
    plain=chw(cv2.resize(decoded[1][80:],(1024,512),interpolation=cv2.INTER_LINEAR),np)
    warp=np.asarray(profile['rawToModel'],np.float64)
    temporal=[chw(cv2.warpPerspective(image,warp,(1024,512),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101),np,True) for image in decoded]
    return plain,temporal
