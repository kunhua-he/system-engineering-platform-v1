# -*- coding: utf-8 -*-
"""像素 —— 逐像素/逐行的可数读数（原 `配色对拍.py::亮/暗/分析`，纯搬家）。"""

import collections

from PIL import Image


def 亮(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def 暗(c):
    return c[0] < 40 and c[1] < 40 and c[2] < 40


def 分析(路径):
    im = Image.open(路径).convert("RGB")
    w, h = im.size
    px = im.load()
    色 = collections.Counter()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            色[px[x, y]] += 1
    黑 = 0
    强边 = 0
    斜面 = 0
    逐行黑 = []
    for y in range(h):
        此行黑 = 0
        for x in range(0, w, 2):
            if 暗(px[x, y]):
                此行黑 += 1
            if y:
                a, b = 亮(px[x, y - 1]), 亮(px[x, y])
                if abs(a - b) > 30:
                    强边 += 1
                if a - b > 12:
                    斜面 += 1
        逐行黑.append(此行黑 * 2)
        黑 += 此行黑 * 2
    return {
        "路径": 路径,
        "尺寸": (w, h),
        "色数": len(色),
        "众数": 色.most_common(8),
        "黑": 黑,
        "黑占比": 黑 * 100.0 / (w * h),
        "强边": 强边,
        "斜面": 斜面,
        "逐行黑": 逐行黑,
    }
