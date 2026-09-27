# -*- coding: utf-8 -*-
"""小工具 —— 括号配对 · 顶层拆分 · 行号与相对路径（纯函数）。"""
from __future__ import annotations

from pathlib import Path

def 是整数(待处理值) -> bool:
    """真整数（bool 不算——它是 int 的子类，会把 True 当 1 蒙过去）。"""
    return isinstance(待处理值, int) and not isinstance(待处理值, bool)


def 行号(文本: str, 位置: int) -> int:
    return 文本.count("\n", 0, 位置) + 1


def 相对(仓根, 路径) -> str:
    路径 = Path(路径)
    仓根 = Path(仓根)
    try:
        return 路径.relative_to(仓根).as_posix()
    except ValueError:
        return 路径.as_posix()


对括号 = {"{": "}", "(": ")", "[": "]"}


def 配对(文本: str, 区间起点: int) -> int:
    """`区间起点` 处是一个开括号；返回与它配对的闭括号下标（找不到返回 -1）。

    按**同种括号**计数即可：Rust 的括号各自成对，跨种嵌套不影响各自的配对。
    """
    开符 = 文本[区间起点]
    闭符 = 对括号.get(开符)
    if 闭符 is None:
        return -1
    括号深度 = 0
    for 位次 in range(区间起点, len(文本)):
        字符表 = 文本[位次]
        if 字符表 == 开符:
            括号深度 += 1
        elif 字符表 == 闭符:
            括号深度 -= 1
            if 括号深度 == 0:
                return 位次
    return -1


def 拆顶层项(文本: str) -> list:
    """按顶层逗号拆（括号内不算）。用于数组字面量的项、函数的实参。"""
    结果 = []
    括号深度 = 0
    区间起点 = 0
    for 位次, 字 in enumerate(文本):
        if 字 in "([{":
            括号深度 += 1
        elif 字 in ")]}":
            括号深度 -= 1
        elif 字 == "," and 括号深度 == 0:
            结果.append(文本[区间起点:位次])
            区间起点 = 位次 + 1
    if 文本[区间起点:].strip():
        结果.append(文本[区间起点:])
    return [片段.strip() for 片段 in 结果 if 片段.strip()]


def 找顶层终止(文本: str, 区间起点: int, 终止=";") -> int:
    括号深度 = 0
    位次 = 区间起点
    while 位次 < len(文本):
        字符表 = 文本[位次]
        if 字符表 in "([{":
            括号深度 += 1
        elif 字符表 in ")]}":
            括号深度 -= 1
        elif 字符表 == 终止 and 括号深度 == 0:
            return 位次
        位次 += 1
    return -1
