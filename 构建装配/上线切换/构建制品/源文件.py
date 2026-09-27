"""源文件 —— 遍历 · 相对路径 · 内容指纹。"""

import hashlib
import os
from pathlib import Path

from .常量 import 仓根, 跳过目录, 源后缀


def 走源文件(目录: Path):
    for 根, 目录表, 文件表 in os.walk(目录):
        目录表[:] = [目录名 for 目录名 in 目录表 if 目录名 not in 跳过目录]
        for 名 in 文件表:
            if 名.endswith(源后缀):
                yield Path(根) / 名


def 相对(路径: Path) -> str:
    return 路径.relative_to(仓根).as_posix()


def 文件指纹(路径: Path) -> str:
    return hashlib.sha256(路径.read_bytes()).hexdigest()
