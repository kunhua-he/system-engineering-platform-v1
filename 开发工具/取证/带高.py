#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""带高 —— 逐行主导色换色，数每条带的高度。只用标准库 + PIL。
用法：python3 带高.py 图1 [图2 ...]   退出码：0 = 出完读数。
"""
import collections
import sys

from PIL import Image


def 带(路径):
    im = Image.open(路径).convert("RGB")
    w, h = im.size
    px = im.load()
    主 = []
    for y in range(h):
        c = collections.Counter(px[x, y] for x in range(0, w, 2))
        主.append(c.most_common(1)[0][0])
    # 合并相邻同色行；1~2 像素的过渡行并进前一条带（避免抗锯齿缝把带切碎）
    段 = []
    for y, c in enumerate(主):
        if 段 and 段[-1][0] == c:
            段[-1][2] = y
        else:
            段.append([c, y, y])
    print(f"=== {路径} ({w}x{h}) ===")
    for c, a, b in 段:
        if b - a + 1 >= 2:
            print(f"  y={a:>3}..{b:>3}  高 {b - a + 1:>3}  主导 rgb{c}")
    print()


def main(argv):
    if len(argv) < 1:
        print(__doc__)
        return 1
    for p in argv:
        try:
            带(p)
        except OSError as e:
            print(f"打不开 {p}：{e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
