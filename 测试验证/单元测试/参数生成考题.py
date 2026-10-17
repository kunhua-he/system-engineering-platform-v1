#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参数生成考题 runner —— 给 `生成声明` 链出真读数（真生成 · 真编译 · 真读回）。

    python3 测试验证/单元测试/参数生成考题.py --预编译契约   # 环境步：编契约 rlib
    python3 测试验证/单元测试/参数生成考题.py              # 命令体：真生成 + 真编译 + 真读回
    python3 测试验证/单元测试/参数生成考题.py --自测        # runner 自身的成对样本

本文件是**路由**：解析参数 → 调包里的公开面 → 打印 → 退出码。实现按关注点在同名包
`生成考题`（实现落在 `单元测试/生成考题/考题.py`）—— **本件零实现**。

★ 为什么本 runner 不在闸 1 里：整条链真跑一次 ~3.3 s（生成器 1.8 s · rustc 编契约 0.9 s ·
  编探针并跑 0.5 s），而闸 1 全量已在 4.4–5.4 s（效率目标 5 s）⇒ 搬进闸 1 会顶穿。
  原先这段断言只活在 `构建装配/形态装配/生成声明/参数生成测试.py`（unittest 孤儿，
  全仓无人 import）⇒ 「写了没人跑」。本 runner 是它的**替代**：同一批断言，真编真跑。

★ 两档照 `测试验证/准入判据/长活原语.py` 的形状：编归环境步（`--预编译契约`），
  跑归命令体（缺件 / 与源不符即 fail-closed 指路）。
"""

import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/命令壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓根：取共享门禁
from 构建装配.门禁 import 报告环境步, 自门禁  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 生成考题 import 找仓根, 预编译契约, 跑参数生成考题, 跑自测  # noqa: E402


def 入口函数(命令行参数: list) -> int:
    """命令行入口：分发到 `生成考题` 的公开面。阈值与注入只从 `构建装配/门禁/` 取。"""
    if "--自测" in 命令行参数:
        return 跑自测()
    if "--预编译契约" in 命令行参数:
        return 预编译契约(找仓根())
    return 跑参数生成考题(找仓根())


if __name__ == "__main__":
    命令行参数 = sys.argv[1:]
    if "--预编译契约" in 命令行参数:
        sys.exit(
            报告环境步(
                起始时刻, 入口函数(命令行参数), "契约 crate 的一次性编译（rustc --crate-type rlib）"
            )
        )
    sys.exit(
        自门禁(
            起始时刻,
            入口函数(命令行参数),
            尾巴余量毫秒=200,
            修法="考题真编真跑（~3 s）；慢了先查 rustc 是不是在重编依赖",
        )
    )
