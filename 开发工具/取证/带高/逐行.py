# -*- coding: utf-8 -*-
"""逐行 —— 逐行主导色换色，数每条带的高度（原 `带高.py::带`，纯搬家）。

**依赖（例外，如实登记）**：本件要 `Pillow`（`PIL`）。仓内 venv（`构建环境/python`）是
`--without-pip`，且 `构建环境/自检.sh` ④ 要求 site-packages 空（只用标准库）⇒ **本件只在
系统 `python3` 下跑**。为何是例外：它是**取证 / 视觉**工具链的依赖，不进闸 0、不参与
「Python 只用标准库」那条口径；装进 venv 反而会把那条口径破在 venv 里（自检 ④ 当场红）。
"""

import collections

from PIL import Image


def 带高逐行(路径):
    im = Image.open(路径).convert("RGB")
    宽度, 高度 = im.size
    px = im.load()
    主版本 = []
    for 纵坐标 in range(高度):
        主色 = collections.Counter(px[横坐标, 纵坐标] for 横坐标 in range(0, 宽度, 2))
        主版本.append(主色.most_common(1)[0][0])
    # 合并相邻同色行；1~2 像素的过渡行并进前一条带（避免抗锯齿缝把带切碎）
    号段 = []
    for 纵坐标, 主色 in enumerate(主版本):
        if 号段 and 号段[-1][0] == 主色:
            号段[-1][2] = 纵坐标
        else:
            号段.append([主色, 纵坐标, 纵坐标])
    print(f"=== {路径} ({宽度}x{高度}) ===")
    for 主色, 段起, 段止 in 号段:
        if 段止 - 段起 + 1 >= 2:
            print(f"  y={段起:>3}..{段止:>3}  高 {段止 - 段起 + 1:>3}  主导 rgb{主色}")
    print()
