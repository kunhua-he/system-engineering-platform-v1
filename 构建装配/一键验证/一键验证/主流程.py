# -*- coding: utf-8 -*-
"""路由主流程：找仓根 · 退出码语义 · 命令行分发。"""

from __future__ import annotations

import sys
from pathlib import Path

from . import 常量

from .常量 import 契约目录名
from .打印 import 打印, 打印缺口
from .承重证明 import 承重证明
from .自测 import 自测
from .退出码 import 算退出码
from .验证 import 验证


# ════════════════════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════════════════════


def 找仓根() -> Path:
    """仓根：本验证器在 构建装配/一键验证/ 下 ⇒ 由 `常量.仓根目录` 给出（上溯三级）。"""
    return 常量.仓根目录

def main(参数: list) -> int:
    仓根 = 找仓根()
    if not (仓根 / 契约目录名).is_dir():
        print(f"定位不到仓根：{仓根} 下没有 {契约目录名}/", file=sys.stderr)
        return 1
    if "--自测" in 参数:
        return 自测(仓根)
    if "--承重证明" in 参数:
        return 承重证明(仓根)
    结果 = 验证(仓根)
    打印(结果)
    if "--缺口" in 参数:
        print("")
        打印缺口()
    return 算退出码(结果)
