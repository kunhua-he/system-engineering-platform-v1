# -*- coding: utf-8 -*-
"""像素 —— 逐像素/逐行的可数读数（原 `配色对拍.py::亮/暗/分析`，纯搬家）。"""

import collections

from PIL import Image


def 亮(通道值):
    return 0.299 * 通道值[0] + 0.587 * 通道值[1] + 0.114 * 通道值[2]


def 暗(通道值):
    return 通道值[0] < 40 and 通道值[1] < 40 and 通道值[2] < 40


def 分析(路径):
    im = Image.open(路径).convert("RGB")
    宽, 高 = im.size
    px = im.load()
    色 = collections.Counter()
    for 纵 in range(0, 高, 2):
        for 横 in range(0, 宽, 2):
            色[px[横, 纵]] += 1
    黑 = 0
    强边 = 0
    斜面 = 0
    逐行黑 = []
    for 纵 in range(高):
        此行黑 = 0
        for 横 in range(0, 宽, 2):
            if 暗(px[横, 纵]):
                此行黑 += 1
            if 纵:
                上行亮, 本行亮 = 亮(px[横, 纵 - 1]), 亮(px[横, 纵])
                if abs(上行亮 - 本行亮) > 30:
                    强边 += 1
                if 上行亮 - 本行亮 > 12:
                    斜面 += 1
        逐行黑.append(此行黑 * 2)
        黑 += 此行黑 * 2
    return {
        "路径": 路径,
        "尺寸": (宽, 高),
        "色数": len(色),
        "众数": 色.most_common(8),
        "黑": 黑,
        "黑占比": 黑 * 100.0 / (宽 * 高),
        "强边": 强边,
        "斜面": 斜面,
        "逐行黑": 逐行黑,
    }
