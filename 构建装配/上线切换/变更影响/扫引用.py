"""扫引用 —— 数「有多少件引用了这个符号」（影响面的机器可读口径）。"""

import os
from pathlib import Path

from .基线口径常量 import 仓根, 扫描后缀, 跳过目录, 本评估面


def 走代码件():
    输出缓冲 = []
    for 根目录, 目录表, 文件表 in os.walk(仓根):
        目录表[:] = [目录名 for 目录名 in 目录表 if 目录名 not in 跳过目录]
        输出缓冲.extend(
            Path(根目录) / 名称 for 名称 in 文件表 if 名称.endswith(扫描后缀)
        )
    return 输出缓冲


def 数引用件(符号名清单) -> dict:
    """→ `{符号名: [引用了它的件相对路径, ...]}`（同一件只记一次；本评估面自身不算）。"""
    待查符号 = sorted({符号名 for 符号名 in 符号名清单 if 符号名})
    引用表 = {符号名: set() for 符号名 in 待查符号}
    for 件路径 in 走代码件():
        件相对路径 = 件路径.relative_to(仓根).as_posix()
        if 件相对路径.startswith(本评估面):
            continue
        try:
            当前文本 = 件路径.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for 符号名 in 待查符号:
            if 符号名 in 当前文本:
                引用表[符号名].add(件相对路径)
    return {符号名: sorted(引用件表) for 符号名, 引用件表 in 引用表.items()}
