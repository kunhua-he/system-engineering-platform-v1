# -*- coding: utf-8 -*-
"""逐行 —— 逐行主导色换色，数每条带的高度（原 `带高.py::带`，纯搬家）。"""

import collections

from PIL import Image


def 带(路径):
    im = Image.open(路径).convert("RGB")
    宽, 高 = im.size
    px = im.load()
    主 = []
    for 纵 in range(高):
        主色 = collections.Counter(px[横, 纵] for 横 in range(0, 宽, 2))
        主.append(主色.most_common(1)[0][0])
    # 合并相邻同色行；1~2 像素的过渡行并进前一条带（避免抗锯齿缝把带切碎）
    段 = []
    for 纵, 主色 in enumerate(主):
        if 段 and 段[-1][0] == 主色:
            段[-1][2] = 纵
        else:
            段.append([主色, 纵, 纵])
    print(f"=== {路径} ({宽}x{高}) ===")
    for 主色, 段起, 段止 in 段:
        if 段止 - 段起 + 1 >= 2:
            print(f"  y={段起:>3}..{段止:>3}  高 {段止 - 段起 + 1:>3}  主导 rgb{主色}")
    print()
