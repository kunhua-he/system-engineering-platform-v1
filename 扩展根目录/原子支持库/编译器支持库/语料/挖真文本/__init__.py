# -*- coding: utf-8 -*-
"""挖真文本 —— 包（实现按关注点分文件）；入口 `../挖真文本.py` 只做路由。

**公开面与拆分前逐字不变**（`开发规范.md` §六）：拆分前本件是单文件，下列模块级名字
是它的公开面；这里把它们**全导一遍**，调用地址 `from 挖真文本 import <名>` 逐字不变。
"""
from .常量 import (
    CONST_RE,
    CTRL,
    DECL,
    DECL_RE,
    DST,
    HDR,
    HDR_END,
    HERE,
    MAXLINE,
    MIN_DECL,
    OUTJSON,
    SRC,
    VER,
    VER_LINE,
    WEAK_FILES,
)
from .容器段表 import const_name, seg_of, seg_table
from .行判定 import check_value, classify, decl_lines, expand, gbk_ok, line_at
from .主流程 import main

__all__ = [
    "CONST_RE", "CTRL", "DECL", "DECL_RE", "DST", "HDR", "HDR_END", "HERE",
    "MAXLINE", "MIN_DECL", "OUTJSON", "SRC", "VER", "VER_LINE", "WEAK_FILES",
    "const_name", "seg_of", "seg_table",
    "check_value", "classify", "decl_lines", "expand", "gbk_ok", "line_at",
    "main",
]
