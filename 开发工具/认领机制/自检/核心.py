# -*- coding: utf-8 -*-
"""核心装载 —— 按路径 importlib 加载**同一份**核心实现（认领机制.py），无测试专用旁路。

★ 本件与命令行用的是**同一份**核心实现（加载 认领机制.py，不是复制一份）。
★ 样本里的时间全部**显式传 now**（T0 起算），不 sleep ⇒ 到期判据可复现，且不靠等。
"""

import importlib.util
import os

# 拆前入口（自检.py）所在目录：加载的 认领机制.py 与账本路径基准都锚在这里。
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_core():
    spec = importlib.util.spec_from_file_location(
        "claim_core", os.path.join(HERE, "认领机制.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = load_core()

T0 = 1700000000.0                                   # 固定基准时刻：样本可复现
P1 = "开发工具/认领机制/说明.md"
P2 = "开发工具/认领机制/账本.json"
P3 = "开发工具/并行工作树.sh"
P4 = "项目文档/设计文档/并行开发与工作区.md"
