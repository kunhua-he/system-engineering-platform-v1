#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使用面回归 runner —— 命令行界面 + 网页应用的**运行时**回归（不是静态自检）。

    python3 测试验证/准入判据/使用面回归.py

本文件是**路由**：调两个夹具 —— `使用面回归_命令行.py`（Python · 替身发请求）与
`使用面回归_网页.mjs`（Node · fetch 替身 + 最小 DOM 替身）。本件零实现。
退出码：0 = 两件夹具都全符；1 = 有断言不符 / 有夹具跑不起来（node 缺失时如实报未判）。
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

本目录 = Path(__file__).resolve().parent
sys.path.insert(0, str(本目录.parents[1]))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

sys.path.insert(0, str(本目录))

from 使用面回归_命令行 import 跑命令行回归  # noqa: E402

if __name__ == "__main__":
    退出码值 = 跑命令行回归()
    node路径 = shutil.which("node")
    if node路径 is None:
        print("网页回归：node 不在 PATH ⇒ 未判（如实报，不当作通过）")
        退出码值 = 1
    else:
        执行结果 = subprocess.run(
            [node路径, str(本目录 / "使用面回归_网页.mjs")],
            capture_output=True, text=True, timeout=5,
        )
        print(执行结果.stdout, end="")
        if 执行结果.returncode != 0:
            print(执行结果.stderr, end="")
            退出码值 = 1
    sys.exit(自门禁(起始时刻, 退出码值, 尾巴余量毫秒=200,
                   修法="两件夹具都是本地纯计算 + 一个 node 子进程；慢了先看是不是 node 起不来"))
