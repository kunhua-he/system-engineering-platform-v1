# -*- coding: utf-8 -*-
"""路由主流程：找仓根 · 退出码语义 · 命令行分发。"""

from __future__ import annotations

import sys
from pathlib import Path

from . import 常量

from .常量 import 检查名, 契约目录名
from .打印 import 打印验证结果, 打印缺口
from .承重证明 import 承重证明
from .编译自检 import 编译自检
from .自测 import 跑自测
from .退出码 import 算退出码
from .验证 import 跑全量判据


def 解析只跑(词表: list) -> tuple:
    """`--只跑` 后面那串（逗号分隔的**判据名子串**）⇒ `(判据名集, 错误或 None)`。

    认**子串**不认编号：判据名在读数里是逐字可见的（如 `㊲ 超时设置上限五秒：…`），
    拿它的一段来点单最省事 —— 编号（`㊲`）与序数（37）之间还要人做一次映射，那是白加的负担。
    一个词都没命中 ⇒ **报错**（不许静默退回全量 —— 那会让「只跑」变成假象）。
    """
    词表 = [关键词.strip() for 关键词 in 词表 if 关键词.strip()]
    if not 词表:
        return set(), "`--只跑` 后面要给判据名的一段（逗号分隔），如 `--只跑 超时设置,命名防回潮`"
    没命中表 = [关键词 for 关键词 in 词表 if not any(关键词 in 名称 for 名称 in 检查名)]
    if 没命中表:
        return set(), "这些词一条判据也没命中：%s" % " · ".join(没命中表)
    return {名称 for 名称 in 检查名 if any(关键词 in 名称 for 关键词 in 词表)}, None


# ════════════════════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════════════════════


def 找仓根() -> Path:
    """仓根：本验证器在 构建装配/一键验证/ 下 ⇒ 由 `常量.仓根目录` 给出（上溯三级）。"""
    return 常量.仓根

def 入口函数(命令行参数: list) -> int:
    仓根 = 找仓根()
    if not (仓根 / 契约目录名).is_dir():
        print(f"定位不到仓根：{仓根} 下没有 {契约目录名}/", file=sys.stderr)
        return 1
    if "--自测" in 命令行参数:
        return 跑自测(仓根)
    if "--承重证明" in 命令行参数:
        return 承重证明(仓根)
    if "--编译自检" in 命令行参数:
        return 编译自检(仓根)
    只跑集 = None
    if "--只跑" in 命令行参数:
        只跑集, 错误 = 解析只跑(命令行参数[命令行参数.index("--只跑") + 1].split(","))
        if 错误:
            print("一键验证：%s" % 错误, file=sys.stderr)
            return 2
    判定汇总 = 跑全量判据(仓根, 只跑=只跑集)
    打印验证结果(判定汇总)
    if "--缺口" in 命令行参数:
        print("")
        打印缺口()
    return 算退出码(判定汇总)
