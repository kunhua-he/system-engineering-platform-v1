# -*- coding: utf-8 -*-
"""找模块 —— 扫模块库，按包声明与能力声明目录识别子目录（本生成器不认识任何模块名）。"""

from pathlib import Path



def 找模块(模块库根: Path) -> list:
    """扫 `模块库根` 下每个子目录 ⇒ `[模块目录]`（源码映射交给生成器校验，按名排序）。"""
    if not 模块库根.is_dir():
        return []
    return [模块目录 for 模块目录 in sorted(模块库根.iterdir())
            if 模块目录.is_dir() and (模块目录 / "包声明.json").is_file() and (模块目录 / "能力声明").is_dir()]


def 模块名表(模块库根: Path) -> list:
    """`[模块名]`（给帮助文本与回执用）。"""
    return [模块目录.name for 模块目录 in 找模块(模块库根)]
