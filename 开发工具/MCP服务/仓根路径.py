"""把仓根补进 ``sys.path`` —— 让 `开发工具/MCP服务/**` 能 import `构建装配/`。

为什么必须有这一件（2026-10-27 实测两次踩）：共享的 Git 路径解析住在
``构建装配/门禁/git路径解析.py``（层序：`开发工具/` 可以 import `构建装配`，反向不行），
而 MCP 侧有两种入口，各自补的 `sys.path` 不一样：

- 网关子进程：只把 ``开发工具/`` 插进来（父包名 ``MCP服务``）；
- ``合并主干.py`` / 样本夹具：插的是**仓根**（父包名 ``开发工具.MCP服务``）。

同一句 ``from 构建装配.门禁.git路径解析 import …`` 在前者会 ``ModuleNotFoundError``。所以由
``MCP服务/__init__.py`` 先 ``from . import 仓根路径``，包一被导入就补齐仓根，一处管全部；
``__init__.py`` 本身保持「零实现」入口纪律（只声明子模块）。
"""

import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
if str(仓根) not in sys.path:
    sys.path.insert(0, str(仓根))
