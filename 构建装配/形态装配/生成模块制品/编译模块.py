# -*- coding: utf-8 -*-
"""编译模块 —— 一个模块目录 ⇒ 一次 `cargo run --example 出模块制品`（退出码原样传）。

本件**不装包**、不改容器头、不改段格式：编译全在 `编译器支持库` 那个 example 里（真的 1106 链）。
"""

import os
import subprocess
from pathlib import Path

from .路径形状 import (编译器支持库目录, 制品后缀, 能力声明目录名, 暂存目录环境变量,
                  出制品示例名, 默认暂存目录)


def 编译环境(暂存目录: Path) -> dict:
    """子进程环境：暂存目录 + cargo 家 / 目标目录 + 离线（不联网、不猜路径）。"""
    环境 = dict(os.environ)
    环境[暂存目录环境变量] = str(暂存目录)
    环境.setdefault("CARGO_HOME", str(Path("构建环境/cargo").resolve()))
    环境.setdefault("CARGO_TARGET_DIR", str(Path("构建环境/构建缓存").resolve()))
    环境.setdefault("CARGO_NET_OFFLINE", "true")
    return 环境


def 跑模块(模块目录: Path) -> int:
    """编一个模块 ⇒ 退出码（0 = 产物已写出）。能力声明不是恰好一份 ⇒ 不编、直接 1。"""
    能力声明表 = sorted((模块目录 / 能力声明目录名).glob("*.json"))
    if len(能力声明表) != 1:
        print("✗ %s：能力声明必须恰好一份，实际 %d" % (模块目录, len(能力声明表)))
        return 1
    暂存目录 = Path(os.environ.get(暂存目录环境变量) or 默认暂存目录)
    暂存目录.mkdir(parents=True, exist_ok=True)
    命令表 = ["cargo", "run", "--locked", "--example", 出制品示例名, "--", str(模块目录.resolve())]
    完成 = subprocess.run(命令表, cwd=str(编译器支持库目录), env=编译环境(暂存目录))
    print(("✓ " if 完成.returncode == 0 else "✗ ")
          + "%s（退出码 %d · 产物 %s%s）" % (模块目录.name, 完成.returncode, 模块目录.name, 制品后缀))
    return 完成.returncode
