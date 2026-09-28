# -*- coding: utf-8 -*-
"""跑声明记录区取证 · 常量 —— 工具目录 · 扩展根 · 仓根 · 取证器路径/样本路径/源码根（取值逐字不变）。"""
import os
from pathlib import Path

# 本件 = <仓根>/扩展根目录/原子支持库/编译器支持库/工具/跑声明记录区取证/常量.py
本件路径 = Path(__file__).resolve()
工具目录 = str(本件路径.parents[1])   # <扩展根>/工具/（与拆分前 dirname(__file__) 同值）
扩展根 = str(本件路径.parents[2])     # <扩展根>
仓根 = str(本件路径.parents[5])     # 仓根

取证器路径 = os.path.join(仓根, "开发工具", "取证", "声明记录区反解.py")
样本路径 = os.path.join(扩展根, "语料", "样本", "第一个程序.e")
源码根 = "/tmp/易语言源码"
