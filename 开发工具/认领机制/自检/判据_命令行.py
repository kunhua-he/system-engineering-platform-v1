# -*- coding: utf-8 -*-
"""判据 M4 —— 命令行层：认领冲突的输出与用法错的退出码。"""

from .夹具 import leases
from .子进程 import run_cli
from .核心 import P1


def m4_pos(p):
    """正向样本（**命令行层**）：跑真命令行，输出必须含「被谁占」、退出码必须是 3。
    为什么要有这条：样本只用核心函数 ⇒ 判据覆盖不到渲染/参数层。**本件实测**：`emit` 曾把
    渲染函数本身当结果打印（`<function ...>`），核心样本 17 条全绿，是这条样本逼出来的。"""
    a = run_cli(p, "认领", "leg-a", P1)
    b = run_cli(p, "认领", "leg-b", P1)
    ok = (a.returncode == 0 and b.returncode == 3 and "冲突" in b.stdout
          and "被 leg-a 占" in b.stdout and "<function" not in b.stdout)
    return ok, "第一次退出码=%d · 第二次退出码=%d · 报出被谁占=%s" % (
        a.returncode, b.returncode, "被 leg-a 占" in b.stdout)


def m4_rev(p):
    """反向样本：用法错的命令行不许静默成功（退出码必须 2，且账本一个字没动）。"""
    a = run_cli(p, "认领", "leg-a")            # 缺路径
    b = run_cli(p, "回收")                      # 缺目标
    c = run_cli(p, "认领", "leg-a", "../../../etc/hosts")   # 仓外路径
    ok = a.returncode == 2 and b.returncode == 2 and c.returncode == 2 and leases(p) == []
    return ok, "缺路径=%d · 缺回收目标=%d · 仓外路径=%d · 账本=%s" % (
        a.returncode, b.returncode, c.returncode, leases(p))
