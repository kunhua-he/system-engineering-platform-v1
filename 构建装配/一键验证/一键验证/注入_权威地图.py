# -*- coding: utf-8 -*-
"""注入样本 · 判据 66（权威地图路径存在）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .判据基线 import 库相对路径

# 悬空路径（反向样本的靶）：一个盘上没有、库 `条款` 里也没有的路径。
悬空路径样本 = "项目文档/这个权威件不存在.md"


def 注入_权威地图悬空路径(临根: Path) -> str:
    """把夹具库 `规则` 表一条权威地图的 `依据`（落点）改成不存在的路径 ⇒ 判据 66 当场红。"""
    库件 = 临根 / 库相对路径
    if not 库件.is_file():
        return 悬空路径样本
    连接 = sqlite3.connect(库件)
    try:
        连接.execute(
            "update 规则 set 依据 = ? where 类 = '权威地图' and 编号 = '权威地图-1'",
            (悬空路径样本,))
        连接.commit()
    finally:
        连接.close()
    return 悬空路径样本
