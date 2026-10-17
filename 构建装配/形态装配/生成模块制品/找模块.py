# -*- coding: utf-8 -*-
"""找模块 —— 扫模块库，认「有 `<目录名><程序文本后缀>`」的子目录（本生成器不认识任何模块名）。"""

from pathlib import Path

from .路径形状 import 程序文本后缀


def 找模块(模块库根: Path) -> list:
    """扫 `模块库根` 下每个子目录 ⇒ `[模块目录]`（只认有 `<目录名><程序文本后缀>` 的，按名排序）。"""
    if not 模块库根.is_dir():
        return []
    return [模块目录 for 模块目录 in sorted(模块库根.iterdir())
            if 模块目录.is_dir() and (模块目录 / (模块目录.name + 程序文本后缀)).is_file()]


def 模块名表(模块库根: Path) -> list:
    """`[模块名]`（给帮助文本与回执用）。"""
    return [模块目录.name for 模块目录 in 找模块(模块库根)]
