#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""装钩子 —— 入口（路由）：**零实现**（`开发规范.md` 第六节：声明子模块 · 再导出公开面 · 零实现）。

    python3 开发工具/MCP服务/装钩子.py          # 装（或刷新）
    python3 开发工具/MCP服务/装钩子.py --卸      # 卸（只摘自家那一条）

实现全在 `MCP服务/钩子.py`；钩子的形状、为什么放行 Bash、配置口径 —— 都在那里的文件头。
"""
import sys
import time
from pathlib import Path

进程起始时刻 = time.monotonic()   # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # 仓根：取 构建装配.门禁
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # 开发工具/：取 MCP服务 包

from 构建装配.门禁 import 自门禁  # noqa: E402
from MCP服务.钩子 import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(自门禁(进程起始时刻, main(), 尾巴余量毫秒=200,
                  修法="本件只读写一个 JSON 配置文件，不该慢。慢就是配置大到离谱或磁盘卡住 —— "
                      "别放宽超时，先量是哪一段。"))
