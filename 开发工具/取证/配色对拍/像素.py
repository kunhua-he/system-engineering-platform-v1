# -*- coding: utf-8 -*-
"""像素 —— 逐像素/逐行的可数读数（原 `配色对拍.py::亮/暗/分析`，纯搬家）。"""

import collections

from PIL import Image


def 提亮(通道值):
    return 0.299 * 通道值[0] + 0.587 * 通道值[1] + 0.114 * 通道值[2]


def 压暗(通道值):
    return 通道值[0] < 40 and 通道值[1] < 40 and 通道值[2] < 40


def 分析(路径):
    im = Image.open(路径).convert("RGB")
    宽, 高 = im.size
    px = im.load()
    颜色 = collections.Counter()
    for 纵坐标 in range(0, 高, 2):
        for 横坐标 in range(0, 宽, 2):
            颜色[px[横坐标, 纵坐标]] += 1
    黑像素数 = 0
    强边 = 0
    斜面 = 0
    逐行黑 = []
    for 纵坐标 in range(高):
        此行黑 = 0
        for 横坐标 in range(0, 宽, 2):
            if 压暗(px[横坐标, 纵坐标]):
                此行黑 += 1
            if 纵坐标:
                上行亮, 本行亮 = 提亮(px[横坐标, 纵坐标 - 1]), 提亮(px[横坐标, 纵坐标])
                if abs(上行亮 - 本行亮) > 30:
                    强边 += 1
                if 上行亮 - 本行亮 > 12:
                    斜面 += 1
        逐行黑.append(此行黑 * 2)
        黑像素数 += 此行黑 * 2
    return {
        "路径": 路径,
        "尺寸": (宽, 高),
        "色数": len(颜色),
        "众数": 颜色.most_common(8),
        "黑": 黑像素数,
        "黑占比": 黑像素数 * 100.0 / (宽 * 高),
        "强边": 强边,
        "斜面": 斜面,
        "逐行黑": 逐行黑,
    }
