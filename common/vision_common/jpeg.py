# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Small JPEG envelope check before allocating any pixel decoder."""
from .protocol import require


def dimensions(raw):
    require(type(raw) is bytes and 4<=len(raw)<=4194304 and raw[:2]==b'\xff\xd8' and raw[-2:]==b'\xff\xd9','JPEG_ENVELOPE_INVALID')
    at=2;seen=None;segments=0
    while at<len(raw)-2:
        segments+=1;require(segments<=1024 and raw[at]==255,'JPEG_MARKER_INVALID')
        while at<len(raw) and raw[at]==255:at+=1
        require(at<len(raw),'JPEG_TRUNCATED');marker=raw[at];at+=1
        require(marker not in (0,0xd8,0xd9),'JPEG_MARKER_INVALID')
        if marker==0xda:break
        require(at+2<=len(raw),'JPEG_TRUNCATED');size=int.from_bytes(raw[at:at+2],'big')
        require(size>=2 and at+size<=len(raw),'JPEG_SEGMENT_INVALID')
        if marker in (0xc0,0xc1,0xc2):
            require(seen is None and size>=8 and raw[at+2]==8,'JPEG_SOF_INVALID')
            height=int.from_bytes(raw[at+3:at+5],'big');width=int.from_bytes(raw[at+5:at+7],'big')
            require((width,height)==(1280,720) and raw[at+7]==3,'JPEG_DIMENSIONS_INVALID');seen=(width,height)
        at+=size
    require(seen is not None,'JPEG_SOF_MISSING');return seen
