# -*- coding: utf-8 -*-
"""判据 65 的反向样本：把夹具台账行的 `验证命令` 改成散文。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .判据基线 import 库相对路径


def 注入_台账散文命令(临根: Path) -> str:
    """夹具台账那一行的第四栏由可跑命令改成**散文**（验收口径的描述）⇒ 判据 65 当场红。

    为什么挑这一处：散文是这条判据的头号对象 —— 它看着像内容、也能被人读，唯独**跑不动**
    （实测那 8 条就是这么来的）。改完别的判据照样绿（散文只在台账第四栏里，不在任何扫描面上）
    ⇒ 反向样本正好只打这一个断言，不误伤别的。
    """
    库件 = 临根 / 库相对路径
    连接 = sqlite3.connect(库件)
    try:
        连接.execute("update 未完成 set 验证命令 = ? where 号 = ?",
                   ("全过程不得覆盖未证明成果，失配拒绝推进主干", 900003))
        连接.commit()
    finally:
        连接.close()
    return "开发工具/信息核心/信息核心.db"
