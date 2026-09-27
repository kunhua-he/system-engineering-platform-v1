# -*- coding: utf-8 -*-
"""自检包（入口：只做再导出，零实现）。

公开面：核心装载（`load_core` · `core` · `HERE` · `T0` · `P1`–`P4`）·
样本表（`CASES`）· 元判据（`meta_check`）· 跑（`main`）。
"""

from .核心 import HERE, P1, P2, P3, P4, T0, core, load_core
from .判据_元 import meta_check
from .样本表 import CASES
from .跑 import main

__all__ = [
    "HERE",
    "T0",
    "P1",
    "P2",
    "P3",
    "P4",
    "core",
    "load_core",
    "meta_check",
    "CASES",
    "main",
]
