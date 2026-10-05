# -*- coding: utf-8 -*-
"""MCP 服务启动入口 —— `python3 -m 开发工具.MCP服务` 的入口点。

不放在 `协议.py` 的 `if __name__ == "__main__"` 里,避免 runpy 的 RuntimeWarning。
"""

import sys
from pathlib import Path

from .协议 import 跑主循环
from .工具 import 工具表


if __name__ == "__main__":
    # 仓根 = MCP 服务的 cwd（.mcp.json 里配的）
    仓根 = Path.cwd()
    sys.exit(跑主循环(仓根, 工具表))
