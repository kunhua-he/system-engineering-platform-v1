#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""长活原语考题 runner —— 给 `跨语言适配/边界协议/边界协议.md` §四 判据 7–10 出真读数。

    python3 测试验证/准入判据/长活原语.py --预编译考题   # 环境步：编单文件考题（不碰 cargo 锁）
    python3 测试验证/准入判据/长活原语.py          # 命令体：跑它，打 判据 7–10 的读数
    python3 测试验证/准入判据/长活原语.py --自测   # runner 自身的三组正/反向样本

本文件是**路由**：解析参数 → 调包里的公开面 → 打印 → 退出码。实现按关注点在同名包
`长活原语`（实现落在 `准入判据/长活原语.py`）—— **本件零实现**。
"""

import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓根：取共享门禁
from 构建装配.门禁 import 报告环境步, 自门禁  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 准入判据.长活原语 import 跑长活原语考题, 找仓根, 自测, 预编译考题  # noqa: E402


def 入口函数(参数: list) -> int:
    """命令行入口：分发到 `长活原语` 的公开面。阈值与注入只从 `构建装配/门禁/` 取。"""
    if "--自测" in 参数:
        return 自测()
    if "--预编译考题" in 参数:
        return 预编译考题(找仓根())
    return 跑长活原语考题(找仓根())


if __name__ == "__main__":
    命令行参数 = sys.argv[1:]
    if "--预编译考题" in 命令行参数:
        sys.exit(
            报告环境步(
                起始时刻, 入口函数(命令行参数), "单文件 Rust 考题的一次性编译（rustc --test，不碰 cargo 锁）"
            )
        )
    sys.exit(
        自门禁(
            起始时刻,
            入口函数(命令行参数),
            尾巴余量毫秒=200,
            修法="考题只编 / 跑一个单文件（~0.7 s）；慢了先查 rustc 是不是在重编依赖",
        )
    )
