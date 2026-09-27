# -*- coding: utf-8 -*-
"""小工具 —— 括号配对 · 顶层拆分 · 行号与相对路径（纯函数）。"""
from __future__ import annotations

from pathlib import Path

def 是整数(值) -> bool:
    """真整数（bool 不算——它是 int 的子类，会把 True 当 1 蒙过去）。"""
    return isinstance(值, int) and not isinstance(值, bool)


def 行号(文本: str, 位: int) -> int:
    return 文本.count("\n", 0, 位) + 1


def 相对(仓根, 路径) -> str:
    路径 = Path(路径)
    仓根 = Path(仓根)
    try:
        return 路径.relative_to(仓根).as_posix()
    except ValueError:
        return 路径.as_posix()


对括号 = {"{": "}", "(": ")", "[": "]"}


def 配对(文: str, 起: int) -> int:
    """`起` 处是一个开括号；返回与它配对的闭括号下标（找不到返回 -1）。

    按**同种括号**计数即可：Rust 的括号各自成对，跨种嵌套不影响各自的配对。
    """
    开 = 文[起]
    闭 = 对括号.get(开)
    if 闭 is None:
        return -1
    深 = 0
    for i in range(起, len(文)):
        c = 文[i]
        if c == 开:
            深 += 1
        elif c == 闭:
            深 -= 1
            if 深 == 0:
                return i
    return -1


def 拆顶层项(文: str) -> list:
    """按顶层逗号拆（括号内不算）。用于数组字面量的项、函数的实参。"""
    出 = []
    深 = 0
    起 = 0
    for i, c in enumerate(文):
        if c in "([{":
            深 += 1
        elif c in ")]}":
            深 -= 1
        elif c == "," and 深 == 0:
            出.append(文[起:i])
            起 = i + 1
    if 文[起:].strip():
        出.append(文[起:])
    return [x.strip() for x in 出 if x.strip()]


def 找顶层终止(文: str, 起: int, 终止=";") -> int:
    深 = 0
    i = 起
    while i < len(文):
        c = 文[i]
        if c in "([{":
            深 += 1
        elif c in ")]}":
            深 -= 1
        elif c == 终止 and 深 == 0:
            return i
        i += 1
    return -1
