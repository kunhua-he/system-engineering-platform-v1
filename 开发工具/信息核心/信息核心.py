#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息核心 —— **单一入口**：建库 / 查看 / 验证（壳只做路由，零实现）。

用法：
    python3 开发工具/信息核心/信息核心.py 建库 [--读数]
    python3 开发工具/信息核心/信息核心.py 查看 [--端口 43130]
    python3 开发工具/信息核心/信息核心.py 验证 [--命名] [--契约]

**为什么合成一个入口**：`开发规范.md` §六 定「入口 ≤120 行 · 零实现」。三个件各自带
`__main__` 就各自算一个入口，而它们的实现在同目录的模块里 ⇒ 三个件全红。合成一个壳之后，
`建库.py` · `查看.py` · `验证.py` 退回**普通模块**（上限 400 行），壳只做参数路由。
"""
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(仓根))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402
import 建库  # noqa: E402
import 查看  # noqa: E402
import 验证  # noqa: E402

用法 = """信息核心 —— 建库 / 查看 / 验证

  python3 开发工具/信息核心/信息核心.py 建库 [--读数]
  python3 开发工具/信息核心/信息核心.py 查看 [--端口 N]     （永不返回，Ctrl-C 退）
  python3 开发工具/信息核心/信息核心.py 验证 [--命名] [--契约]
"""


def 入口函数(参数: list) -> int:
    子命令, 余参数 = (参数[0], 参数[1:]) if 参数 else ("", [])
    if 子命令 == "建库":
        return 建库.入口函数(余参数)
    if 子命令 == "验证":
        return 验证.入口函数(余参数)
    if 子命令 == "查看":
        端口 = 表定义.默认端口
        if "--端口" in 余参数:
            端口 = int(余参数[余参数.index("--端口") + 1])
        查看.起页面(端口)  # 永不返回
        return 0
    print(用法, file=sys.stderr)
    return 2


if __name__ == "__main__":
    from 构建装配.门禁 import 自门禁

    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="建库是秒级、验证是毫秒级；查看永不返回（那条不产生读数）。"))
