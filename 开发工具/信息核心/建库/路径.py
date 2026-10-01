# -*- coding: utf-8 -*-
"""建库 · 路径 —— 仓根与取件路径。

本包比原入口深一层（`信息核心/建库/路径.py`）⇒ 上溯四级取仓根。抽取器要 `表定义`
（住 `开发工具/信息核心/`）与 `代码地图.落点`（住 `开发工具/`）—— 两段都得先挂 `sys.path`
才 import 得动。`信息核心.py` 起壳时已挂了**仓根**与**信息核心**两段，这里补**开发工具**
并兜住「不经壳直接 import 本包」的场合。
"""
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[3]

if str(仓根) not in sys.path:
    sys.path.insert(0, str(仓根))
if str(仓根 / "开发工具") not in sys.path:
    sys.path.insert(0, str(仓根 / "开发工具"))
if str(仓根 / "开发工具" / "信息核心") not in sys.path:
    sys.path.insert(0, str(仓根 / "开发工具" / "信息核心"))
