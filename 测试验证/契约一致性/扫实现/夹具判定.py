# -*- coding: utf-8 -*-
"""夹具判定 —— `#[cfg(test)]` 块 与 由 cfg(test) 引入的整份夹具文件。"""
from __future__ import annotations

import os
import re

from .小工具 import 配对
from .掩码 import 掩码

# `#[cfg(…)]` 属性：**括号配对**解析（`#[cfg(any(test, feature = "x"))]` 有两层括号，
# 早先用 `#\[\s*cfg\s*\([^)]*\btest\b[^)]*\)\s*\]` 会**漏**这一形状 ⇒ 那种文件被当生产代码。
CFG开头模式 = re.compile(r"#\[\s*cfg\s*\(")


def _cfg属性(掩: str, 起: int):
    """从 `起`（指向 `#`）解析一个 `#[cfg(…)]` 属性，返回 (属性文本, 结束位) 或 None。

    为什么不用一条正则：cfg 的条件里可以有嵌套括号（`any(test, feature = "x")`），
    `[^)]*` 这类正则在第一个 `)` 就断，漏判 ⇒ 扫描面不覆盖它声称的范围
    （判据的可信性.md §三.2）。
    """
    匹配 = CFG开头模式.match(掩, 起)
    if not 匹配:
        return None
    括号位 = 匹配.end()
    全长 = len(掩)
    深 = 1
    while 括号位 < 全长 and 深:
        if 掩[括号位] == "(":
            深 += 1
        elif 掩[括号位] == ")":
            深 -= 1
        括号位 += 1
    if 深:
        return None
    空白位 = 括号位
    while 空白位 < 全长 and 掩[空白位] in " \t\r\n":
        空白位 += 1
    if 空白位 >= 全长 or 掩[空白位] != "]":
        return None
    return 掩[起 : 空白位 + 1], 空白位 + 1


def 找cfg属性(掩: str) -> list:
    """返回 [(起, 止, 属性文本, 是否含 test)]，按位置序。"""
    结果 = []
    for 匹配 in CFG开头模式.finditer(掩):
        属 = _cfg属性(掩, 匹配.start())
        if 属 is None:
            continue
        属性文本, 止 = 属
        结果.append((匹配.start(), 止, 属性文本, bool(re.search(r"\btest\b", 属性文本))))
    return 结果


def _项头(掩: str, 位: int) -> tuple:
    """从 `位` 起扫到第一个 `{` 或 `;`，返回 (头文本, 终止位)。"""
    全长 = len(掩)
    终 = 位
    while 终 < 全长 and 掩[终] not in "{;":
        终 += 1
    return 掩[位:终], 终


def _属性窗起(掩: str, 位: int) -> int:
    """本项的起点：往回找最近的 `;` / `{` / `}`。

    `#[path = "…"]` 写在 `#[cfg(test)]` **之前**也合法（属性顺序不影响语义）；
    只看 cfg 之后那一段会漏 ⇒ 那种夹具文件被当生产代码。
    """
    起 = 位
    while 起 > 0 and 掩[起 - 1] not in ";{}":
        起 -= 1
    return 起


def 找夹具项(掩: str, 原文本: str) -> tuple:
    """返回 (块区间表[(起,止)], 外部夹具文件表[(名, 相对本文件的路径, 位)])。"""
    块 = []
    外 = []
    for 起, 属止, _属性文本, 含test in 找cfg属性(掩):
        if not 含test:
            continue
        头, 终 = _项头(掩, 属止)
        if 终 >= len(掩):
            continue
        if 掩[终] == ";":
            块.append((起, 终 + 1))
        else:
            止 = 配对(掩, 终)
            if 止 < 0:
                continue
            块.append((起, 止 + 1))
        名配 = re.search(r"\bmod\s+([^\s;{]+)", 头)
        if not 名配:
            continue
        名 = 名配.group(1)
        # `#[path = "…"]` 的字符串在掩码里是空格 ⇒ 回原文本取引号内的值。
        # 窗口取「本项起点 → 项尾」：`#[path]` 可以在 cfg 之前，也可以在 cfg 之后。
        窗起 = _属性窗起(掩, 起)
        路 = None
        for 路命 in re.finditer(r"#\[\s*path\b", 掩[窗起:终]):
            引 = 原文本.find('"', 窗起 + 路命.end(), 终)
            if 引 >= 0:
                终引 = 原文本.find('"', 引 + 1)
                if 终引 > 引:
                    路 = 原文本[引 + 1 : 终引]
                    break
        if 路 is not None:
            外.append((名, 路, 起))
            continue
        外.append((名, 名 + ".rs", 起))
    return 块, 外


def 建夹具集(件表: dict, 掩表: dict = None) -> dict:
    """返回 {"块": {键: [(起,止)]}, "整份夹具": set(键), "其它cfg": [(键,位)]}。

    `掩表` 是 `掩码()` 的**每趟缓存**：掩码是这一趟里最贵的一步（154 个文件 ≈ 250 ms），
    而夹具判定与实现面抽取都要它 ⇒ 一趟只算一次（这是秒级的手段，不是可选优化）。
    """
    Rs件 = {括号位: 原文 for 括号位, 原文 in 件表.items() if 括号位.endswith(".rs") and 原文 is not None}
    if 掩表 is None:
        掩表 = {括号位: 掩码(原文) for 括号位, 原文 in Rs件.items()}
    块表 = {}
    外部 = []
    其它 = []
    for 键, 掩 in 掩表.items():
        块, 外 = 找夹具项(掩, Rs件[键])
        块表[键] = 块
        for 名, 路, 位 in 外:
            外部.append((键, 路, 位))
        for 起, _止, _属性文本, 含test in 找cfg属性(掩):
            if not 含test:
                其它.append((键, 起))
    整份 = set()
    # 两趟：先按「父文件不是夹具文件」收集；父文件本身是夹具的，它的 mod 声明不算数。
    待定 = list(外部)
    for _ in range(2):
        新 = set()
        for 父, 路, 位 in 待定:
            if 父 in 整份:
                continue
            父目录 = 父.rsplit("/", 1)[0] if "/" in 父 else ""
            候选 = f"{父目录}/{路}" if 父目录 else 路
            候选 = os.path.normpath(候选).replace("\\", "/")
            if 候选 in 件表:
                新.add(候选)
                continue
            # `mod 名;` → 名.rs 或 名/mod.rs
            备 = 候选
            if 备.endswith(".rs") and 备 not in 件表:
                备2 = 备[:-3] + "/mod.rs"
                if 备2 in 件表:
                    新.add(备2)
        if not 新 - 整份:
            break
        整份 |= 新
    return {"块": 块表, "整份夹具": 整份, "其它cfg": 其它}


def 生产区(文本: str, 区间表: list) -> str:
    if not 区间表:
        return 文本
    结果 = list(文本)
    for 起, 止 in 区间表:
        for 位次 in range(起, min(止, len(结果))):
            if 结果[位次] != "\n":
                结果[位次] = " "
    return "".join(结果)
