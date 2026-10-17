# -*- coding: utf-8 -*-
"""重跑指纹 · 命令行 —— 按 `--检查` 分派（签名与拆分前逐字一致：`main()` 读 `sys.argv`）。"""
import sys

from .刷新 import 刷新指纹, 检查指纹


def 入口函数():
    检查档 = "--检查" in sys.argv[1:]
    return 检查指纹() if 检查档 else 刷新指纹()
