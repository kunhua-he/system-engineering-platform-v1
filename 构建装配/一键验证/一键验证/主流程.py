# -*- coding: utf-8 -*-
"""路由主流程：找仓根 · 退出码语义 · 命令行分发。"""

from __future__ import annotations

import sys
from pathlib import Path

from . import 常量

from .常量 import 检查名, 契约目录名
from .打印 import 打印, 打印缺口
from .承重证明 import 承重证明
from .自测 import 自测
from .退出码 import 算退出码
from .验证 import 验证


def 解析只跑(词表: list) -> tuple:
    """`--只跑` 后面那串（逗号分隔的**判据名子串**）⇒ `(判据名集, 错误或 None)`。

    认**子串**不认编号：判据名在读数里是逐字可见的（如 `㊲ 超时设置上限五秒：…`），
    拿它的一段来点单最省事 —— 编号（`㊲`）与序数（37）之间还要人做一次映射，那是白加的负担。
    一个词都没命中 ⇒ **报错**（不许静默退回全量 —— 那会让「只跑」变成假象）。
    """
    词表 = [词.strip() for 词 in 词表 if 词.strip()]
    if not 词表:
        return set(), "`--只跑` 后面要给判据名的一段（逗号分隔），如 `--只跑 超时设置,命名防回潮`"
    没命中表 = [词 for 词 in 词表 if not any(词 in 名 for 名 in 检查名)]
    if 没命中表:
        return set(), "这些词一条判据也没命中：%s" % " · ".join(没命中表)
    return {名 for 名 in 检查名 if any(词 in 名 for 词 in 词表)}, None


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
    只跑集 = None
    if "--只跑" in 参数:
        只跑集, 错 = 解析只跑(参数[参数.index("--只跑") + 1].split(","))
        if 错:
            print("一键验证：%s" % 错, file=sys.stderr)
            return 2
    结果 = 验证(仓根, 只跑=只跑集)
    打印(结果)
    if "--缺口" in 参数:
        print("")
        打印缺口()
    return 算退出码(结果)
