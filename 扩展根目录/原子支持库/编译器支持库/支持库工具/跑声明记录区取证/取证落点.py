# -*- coding: utf-8 -*-
"""跑声明记录区取证 · 常量 —— 工具目录 · 扩展根 · 仓根 · 取证器路径/样本路径/源码根（取值逐字不变）。"""
import os
import sys
from pathlib import Path

# 本件 = <仓根>/扩展根目录/原子支持库/编译器支持库/支持库工具/跑声明记录区取证/取证落点.py
本件路径 = Path(__file__).resolve()
工具目录 = str(本件路径.parents[1])   # <扩展根>/工具/（与拆分前 dirname(__file__) 同值）
扩展根路径 = str(本件路径.parents[2])     # <扩展根>
仓根 = str(本件路径.parents[5])     # 仓根

取证器路径 = os.path.join(仓根, "开发工具", "取证", "声明记录区反解.py")
样本路径 = os.path.join(扩展根路径, "语料", "样本", "第一个程序.e")

# 语料源头 —— **不再写死 `/tmp`**（易失路径；实测 2026-10-01 源头已被大幅清空）。落点走
# **运行数据根**（唯一解析器 `运行内核/运行数据根/`；Python 侧入口 `开发工具/运行数据根.py`，
# **不自持第二份解析**）：默认 = `<运行数据根>/临时件/易语言源码`；`V1_CORPUS_ROOT`（ASCII）
# 非空则原样覆盖。解析器不在 / 解析不出 ⇒ 空串（调用方按「未判」报，**不猜路径**）。
源码根 = ""
sys.path.insert(0, os.path.join(仓根, "开发工具"))
try:
    from 运行数据根 import 解析当前环境, 子目录路径
    源码根 = str(子目录路径(解析当前环境(), "临时件") / "易语言源码")
except Exception:
    源码根 = ""
if os.environ.get("V1_CORPUS_ROOT"):
    源码根 = os.environ["V1_CORPUS_ROOT"]
