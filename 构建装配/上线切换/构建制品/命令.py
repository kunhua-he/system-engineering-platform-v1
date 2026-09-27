"""命令 —— 跑子进程（不吞输出）· 工具链版本 · 提交哈希与工作区脏。"""

import subprocess

from .常量 import 仓根, 回执相对路径


def 跑命令(命令, **附加):
    """跑一条命令；失败即抛，**不吞输出**。"""
    运行结果 = subprocess.run(命令, capture_output=True, text=True, **附加)
    if 运行结果.returncode != 0:
        raise SystemExit(
            "命令失败（退出码 {}）：{}\n{}\n{}".format(
                运行结果.returncode, " ".join(命令), 运行结果.stdout[-2000:], 运行结果.stderr[-2000:]
            )
        )
    return 运行结果


def 工具链版本() -> str:
    return 跑命令(["rustc", "--version"], cwd=仓根).stdout.strip()


def 提交哈希() -> tuple:
    运行结果 = 跑命令(["git", "rev-parse", "--short=12", "HEAD"], cwd=仓根).stdout.strip()
    脏行 = [
        源码行
        for 源码行 in 跑命令(["git", "status", "--porcelain"], cwd=仓根).stdout.splitlines()
        if 源码行.strip() and 源码行[3:].strip().strip('"') != 回执相对路径
    ]
    是否脏 = bool(脏行)
    return 运行结果, 是否脏
