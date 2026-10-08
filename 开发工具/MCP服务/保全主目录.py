#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主仓三件授权旧稿保护入口，默认只读预检；用 --help 查看调用形状。"""
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 报告环境步
from 开发工具.MCP服务.保全主目录编排 import 命令入口

if __name__ == "__main__":
    sys.exit(报告环境步(起始时刻,
        命令入口(sys.argv[1:], Path(__file__).resolve().parents[2]),
        说明="受控主仓保护环境步"))
