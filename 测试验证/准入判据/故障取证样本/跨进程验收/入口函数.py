"""跨进程执行路卡 —— 发布验收卡模块的公开面（`发布验收/卡调度.py` 按名调它）。

与 `发布验收_缓存恢复.py` 同族：它们都是**库件**（不带 `__main__`），由
`发布验收.py` 一个入口拉起。本件只做转调 —— 实现住 `验收项/`。
"""

import sys
from pathlib import Path

本目录 = Path(__file__).resolve().parent
if str(本目录) not in sys.path:
    sys.path.insert(0, str(本目录))

from 验收项 import 主流程  # noqa: E402


def 入口函数(命令行参数):
    """卡入口：忽略参数，跑八条必证并返回退出码（与其它卡同形）。"""
    _ = 命令行参数
    return 主流程()
