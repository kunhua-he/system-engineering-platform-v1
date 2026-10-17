# -*- coding: utf-8 -*-
"""跑声明记录区取证 · 跑取证 —— 转调解析器（唯一实现）· 承重读数断言。"""
import subprocess
import sys

from .常量 import 仓根, 取证器路径


def 跑取证(命令行参数):
    """跑取证器，返回 (退出码, stdout)。"""
    进程 = subprocess.run(
        [sys.executable, 取证器路径] + 命令行参数,
        cwd=仓根,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return 进程.returncode, 进程.stdout


def 断言(条件, 描述, 失败集):
    if 条件:
        print("  ✓ %s" % 描述)
    else:
        print("  ✗ %s" % 描述)
        失败集.append(描述)
