# -*- coding: utf-8 -*-
"""判据 M4 —— 命令行层：认领冲突的输出与用法错的退出码。"""

from .夹具 import leases
from .子进程 import run_cli
from .核心 import P1


def m4_pos(账本路径):
    """正向样本（**命令行层**）：跑真命令行，输出必须含「被谁占」、退出码必须是 3。
    为什么要有这条：样本只用核心函数 ⇒ 判据覆盖不到渲染/参数层。**本件实测**：`emit` 曾把
    渲染函数本身当结果打印（`<function ...>`），核心样本 17 条全绿，是这条样本逼出来的。"""
    首次认领 = run_cli(账本路径, "认领", "leg-a", P1)
    冲突认领 = run_cli(账本路径, "认领", "leg-b", P1)
    ok = (首次认领.returncode == 0 and 冲突认领.returncode == 3 and "冲突" in 冲突认领.stdout
          and "被 leg-a 占" in 冲突认领.stdout and "<function" not in 冲突认领.stdout)
    return ok, "第一次退出码=%d · 第二次退出码=%d · 报出被谁占=%s" % (
        首次认领.returncode, 冲突认领.returncode, "被 leg-a 占" in 冲突认领.stdout)


def m4_rev(账本路径):
    """反向样本：用法错的命令行不许静默成功（退出码必须 2，且账本一个字没动）。"""
    首次认领 = run_cli(账本路径, "认领", "leg-a")            # 缺路径
    冲突认领 = run_cli(账本路径, "回收")                      # 缺目标
    仓外路径运行 = run_cli(账本路径, "认领", "leg-a", "../../../etc/hosts")   # 仓外路径
    ok = 首次认领.returncode == 2 and 冲突认领.returncode == 2 and 仓外路径运行.returncode == 2 and leases(账本路径) == []
    return ok, "缺路径=%d · 缺回收目标=%d · 仓外路径=%d · 账本=%s" % (
        首次认领.returncode, 冲突认领.returncode, 仓外路径运行.returncode, leases(账本路径))
