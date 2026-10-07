#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""制品读数 —— 当前 HEAD + 三件制品 sha256（启动网关 / 工作进程 / 编译器支持库制品）。

发布验收三张卡都印这一行：结论要能钉到「跑的是哪一份件」—— 否则同一句读数
换个制品也能复现，事后无法复算。

口径：三件制品取自**构建缓存**与**扩展目录**（生产装配实际加载的那几份）；
缺件给「缺失」而不是报错（缺件本身就是一条读数）。

    python3 -c "import sys; sys.path.insert(0, '测试验证/准入判据/故障取证样本'); import 制品读数; 制品读数.印制品读数()"
"""

import hashlib
import subprocess
from pathlib import Path

仓根 = Path(__file__).resolve().parents[3]

# 三件制品（生产装配实际加载的那几份）：网关 · 工作进程 · 支持库制品。
制品路径表 = {
    "启动网关": 仓根 / "构建环境/构建缓存/debug/examples/启动网关",
    "工作进程": 仓根 / "构建环境/构建缓存/debug/examples/工作进程",
    "编译器支持库.支持库制品": 仓根 / "扩展根目录/原子支持库/编译器支持库/编译器支持库.支持库制品",
}


def 取制品指纹表():
    """三件制品的 sha256（缺件给「缺失」）。"""
    指纹表 = {}
    for 制品名, 制品路径 in 制品路径表.items():
        指纹表[制品名] = (
            hashlib.sha256(制品路径.read_bytes()).hexdigest() if 制品路径.is_file() else "缺失"
        )
    return 指纹表


def 取提交指纹():
    """当前 HEAD 提交指纹（git rev-parse HEAD；取不到给「未知」）。"""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(仓根), capture_output=True, text=True, timeout=3,
        ).stdout.strip() or "未知"
    except (OSError, subprocess.SubprocessError):
        return "未知"


def 印制品读数():
    """印一行「HEAD + 三制品 sha256」并返回该行文本。"""
    指纹表 = 取制品指纹表()
    读数行 = "制品读数：HEAD=%s · %s" % (
        取提交指纹(), " · ".join("%s=%s" % (制品名, 值) for 制品名, 值 in 指纹表.items())
    )
    print("  " + 读数行)
    return 读数行
