#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配色对拍 —— 参考图 vs 我方渲染图，只出可数的像素读数，不出观感判断。

为什么需要它：本地看图模型对「配色像不像」只给观感词（「更传统、更厚重」），
观感词没法施工、也没法验收。本脚本把「厚重」翻译成三个可数的量：
  ① 纯黑像素占比  —— 经典 Win32 界面的分隔线是**纯黑 1px**，现代平铺 CSS 常用浅灰
  ② 强边数（相邻行亮度差 > 30）—— 边框线的数量
  ③ 亮压暗对数（上亮下暗，差 > 12）—— **斜面**（bevel）的特征
再加逐行的黑像素分布，用来定位「黑线在哪几行」。

跑法（PIL 即可，无需 venv）：
    python 开发工具/取证/配色对拍.py <参考图.png> <我方图.png> [更多我方图...]
退出码：0 = 出完读数；1 = 图片打不开。
"""
import collections
import sys

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


def 打印(读数):
    w, h = 读数["尺寸"]
    print(f"=== {读数['路径']} ===")
    print(f"  尺寸 {w}x{h} · 采样色数 {读数['色数']}")
    print(f"  纯黑 {读数['黑']} px（{读数['黑占比']:.2f}%）· 强边 {读数['强边']} · 斜面 {读数['斜面']}")
    print("  前 8 众数色：")
    for c, n in 读数["众数"]:
        print(f"    rgb{c}  {n * 4} px  ({n * 4 * 100 // (w * h)}%)")
    print("  黑像素最多的 14 行：")
    for n, y in sorted(((n, y) for y, n in enumerate(读数["逐行黑"])), reverse=True)[:14]:
        print(f"    y={y:>3}  黑 {n:>4}  ({n * 100 // w}%)")
    print()


def main(参数):
    if len(参数) < 2:
        print(__doc__)
        return 1
    for 路径 in 参数:
        try:
            打印(分析(路径))
        except OSError as 错:
            print(f"打不开 {路径}：{错}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
