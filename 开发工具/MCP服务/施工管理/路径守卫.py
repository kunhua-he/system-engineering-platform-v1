# -*- coding: utf-8 -*-
"""认领、推演、写盘与恢复共用的树内无链接路径守卫。"""
from pathlib import Path


def 核树内路径(工作树: Path, 相对路径: str) -> Path:
    """拒绝非规范路径及任一级链接；允许合法尚未创建的目标。"""
    if not isinstance(相对路径, str) or not 相对路径 or Path(相对路径).is_absolute():
        raise ValueError("路径须为规范仓内相对路径")
    if str(Path(相对路径)) != 相对路径 or ".." in Path(相对路径).parts or 相对路径 == ".":
        raise ValueError("路径须为规范仓内相对路径")
    if 工作树.is_symlink() or not 工作树.is_dir():
        raise ValueError("工作树不存在或为链接")
    当前路径 = 工作树
    for 路径段 in Path(相对路径).parts:
        当前路径 = 当前路径 / 路径段
        if 当前路径.is_symlink():
            raise ValueError("路径含链接")
    if not 当前路径.resolve().is_relative_to(工作树.resolve()):
        raise ValueError("目标不在工作树内")
    return 当前路径
