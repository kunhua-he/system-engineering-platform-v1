# -*- coding: utf-8 -*-
"""编译模块 —— 一个模块目录 ⇒ 一次 `cargo run --example 出模块制品`（退出码原样传）。

本件**不装包**、不改容器头、不改段格式：编译全在 `编译器支持库` 那个 example 里（真的 1106 链）。
"""

import os
import subprocess
from pathlib import Path

from .路径形状 import (编译器支持库目录, 制品后缀, 能力声明目录名, 暂存目录环境变量,
                  出制品示例名, 默认暂存目录, 组合模块库根)


def 编译环境(暂存目录: Path) -> dict:
    """子进程环境：暂存目录 + cargo 家 / 目标目录 + 离线（不联网、不猜路径）。"""
    环境 = dict(os.environ)
    环境[暂存目录环境变量] = str(暂存目录)
    # 正式入口是唯一配置源；不继承别的树的依赖家，也不另拼默认目录。
    环境回执 = subprocess.run(["sh", "-c", '. ./构建环境/进入.sh >/dev/null && printf "%s\\000" "$CARGO_HOME" "$CARGO_TARGET_DIR" "$CARGO_NET_OFFLINE"'], capture_output=True, timeout=5)
    if 环境回执.returncode:
        raise RuntimeError("读取正式构建环境失败：" + 环境回执.stderr.decode(errors="replace"))
    环境片段 = 环境回执.stdout.split(bytes([0]))
    if len(环境片段) != 4 or 环境片段[-1] or not all(环境片段[:3]):
        raise RuntimeError("正式构建环境未返回完整的依赖家、编译目录与离线模式")
    环境["CARGO_HOME"] = os.fsdecode(环境片段[0])
    环境.setdefault("CARGO_TARGET_DIR", os.fsdecode(环境片段[1]))
    环境["CARGO_NET_OFFLINE"] = os.fsdecode(环境片段[2])
    return 环境


def 跑模块(模块目录: Path) -> int:
    """编一个模块 ⇒ 退出码（0 = 产物已写出）。能力声明为空 ⇒ 不编、直接 1。"""
    能力声明表 = sorted((模块目录 / 能力声明目录名).glob("*.json"))
    if not 能力声明表:
        print("✗ %s：能力声明不能为空，实际 %d" % (模块目录, len(能力声明表)))
        return 1
    暂存目录 = Path(os.environ.get(暂存目录环境变量) or 默认暂存目录)
    暂存目录.mkdir(parents=True, exist_ok=True)
    命令表 = ["cargo", "run", "--locked", "--example", 出制品示例名, "--", str(模块目录.resolve())]
    完成 = subprocess.run(命令表, cwd=str(编译器支持库目录), env=编译环境(暂存目录))
    print(("✓ " if 完成.returncode == 0 else "✗ ")
          + "%s（退出码 %d · 产物 %s%s）" % (模块目录.name, 完成.returncode, 模块目录.name, 制品后缀))
    return 完成.returncode


def 回收退役模块():
    """整包源码与声明已撤且只剩自有生成物，才回收本生成器的制品。"""
    for 模块目录 in sorted(组合模块库根.iterdir()):
        if not 模块目录.is_dir() or (模块目录/'包声明.json').exists():
            continue
        剩余文件表 = [文件路径 for 文件路径 in 模块目录.rglob('*') if 文件路径.is_file() or 文件路径.is_symlink()]
        if not 剩余文件表 or any(文件路径.is_symlink() or 文件路径.parent != 模块目录 or 文件路径.name not in (模块目录.name+制品后缀, '指纹.json') for 文件路径 in 剩余文件表):
            continue
        退役制品 = 模块目录/(模块目录.name+制品后缀)
        if 退役制品.is_file():
            退役制品.unlink()

