# -*- coding: utf-8 -*-
"""同源自检 —— 入口（薄壳）：转调 同源自检/自检.py 的 入口函数。

    python 扩展装载/开发标准/同源自检.py [扩展目录…]

不带参数 = 只看三套模板；带参数 = 连真实扩展一起看。零实现（只转调）。
零第三方依赖。退出码：0 = 全齐；1 = 有缺件；2 = 判不了。
"""
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 自量起表点（在导入本包之前）

本件目录 = Path(__file__).resolve().parent
if str(本件目录 / "同源自检") not in sys.path:
    sys.path.insert(0, str(本件目录 / "同源自检"))

from 自检 import 入口函数  # noqa: E402


if __name__ == "__main__":
    print(f"命令墙钟（自量）{int((time.monotonic() - 起始时刻) * 1000)} ms")
    sys.exit(入口函数(sys.argv[1:]))
