# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Bounded postprocessing derived from the pinned upstream model semantics."""
import math
from vision_common.protocol import number,require,vector


def sigmoid(value):
    number(value)
    if value>=0:return 1/(1+math.exp(-value))
    e=math.exp(value);return e/(1+e)


def autodrive(values):
    vector(values,3);distance,curve,logit=values;number(distance,0,1)
    return dict(valid=True,distanceNormalized=distance,curvatureRaw=curve,presenceProbability=sigmoid(logit))


def autosteer(positions,confidence):
    vector(positions,64);vector(confidence,64)
    return dict(valid=True,xp=list(positions),confidence=list(confidence))


def iou(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=lambda box:(box[2]-box[0])*(box[3]-box[1])
    return intersection/(area(a)+area(b)-intersection+1e-6)


def nms(candidates):
    # Upstream is class-agnostic, confidence .6, IoU .45. Stable input order is
    # retained for score ties; there are never unbounded returned detections.
    candidates=sorted(candidates,key=lambda row:row['score'],reverse=True);keep=[]
    for candidate in candidates:
        if all(iou(candidate['box'],row['box'])<=.45 for row in keep):keep.append(candidate)
        if len(keep)==128:break
    return keep


def autospeed(channels):
    require(type(channels) is list and len(channels)==8 and all(type(row) is list and len(row)==10752 for row in channels),'AUTOSPEED_SHAPE_INVALID')
    candidates=[]
    for index in range(10752):
        cx,cy,w,h=[number(channels[c][index]) for c in range(4)]
        scores=[sigmoid(channels[c][index]) for c in range(4,8)];best=max(scores)
        if best<.6:continue
        require(w>0 and h>0,'AUTOSPEED_BOX_INVALID')
        candidates.append(dict(box=[cx-w/2,cy-h/2,cx+w/2,cy+h/2],score=best,classId=scores.index(best),probabilities=scores))
    return dict(valid=True,detections=nms(candidates))
