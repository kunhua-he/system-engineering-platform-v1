# -*- coding: utf-8 -*-
"""落盘 · 改 · 回滚 · 留痕。

- **文件名 = 编号**（§一）：用 `O_CREAT|O_EXCL` 独占创建，撞号靠文件系统报错，不靠面判断。
- **改**（目标号已存在）：只增不改 + 显式确认 + 改动前后留痕（§五）。
- **回滚**：只撤面自己这一次落盘（新建的删、改过的恢复原文），不对外暴露成删除能力。
"""

import hashlib
import json
import os
from pathlib import Path

留痕目录名 = "改动留痕"
留痕文件名 = "改动留痕.jsonl"


def 序列化(数据) -> bytes:
    """落盘字节：与既有声明同形（UTF-8 · 2 空格缩进 · 结尾换行）。"""
    return (json.dumps(数据, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def 指纹(字节: bytes) -> str:
    """与 生成声明.py 的 源指纹() 同一口径：sha256 前 16 位十六进制。"""
    return hashlib.sha256(字节).hexdigest()[:16]


def 读现有(路径):
    """→ 字节 或 None（不存在）。读不动（权限等）会抛 OSError，交给上层照实报。"""
    try:
        return 路径.read_bytes()
    except FileNotFoundError:
        return None


def 新建(路径, 字节) -> None:
    """独占创建：已存在 ⇒ FileExistsError（这就是「一个号一个文件」的撞车点）。"""
    fd = os.open(str(路径), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, 字节)
    finally:
        os.close(fd)


def 覆盖(路径, 字节) -> None:
    fd = os.open(str(路径), os.O_WRONLY | os.O_TRUNC)
    try:
        os.write(fd, 字节)
    finally:
        os.close(fd)


def 回滚(路径, 旧字节) -> None:
    """旧字节为 None ⇒ 删除本次新建件；否则把原文写回。"""
    if 旧字节 is None:
        路径.unlink()
    else:
        覆盖(路径, 旧字节)


def 只增判定(旧数据, 新数据):
    """→ (是否只增, 差异列表)。只增 = 旧键全在且值全等（新键可以多出来）。"""
    差异 = []
    for 键, 旧值 in 旧数据.items():
        if 键 not in 新数据:
            差异.append("删掉旧键 %s" % 键)
        elif 新数据[键] != 旧值:
            差异.append("改旧键 %s：%r → %r" % (键, 旧值, 新数据[键]))
    return (not 差异), 差异


def 留痕(面根, 记录) -> str:
    """只追加一行 JSON Lines。返回留痕文件相对面的路径。"""
    目录 = Path(面根) / 留痕目录名
    目录.mkdir(parents=True, exist_ok=True)
    路径 = 目录 / 留痕文件名
    with 路径.open("a", encoding="utf-8") as 流:
        流.write(json.dumps(记录, ensure_ascii=False) + "\n")
    return "%s/%s" % (留痕目录名, 留痕文件名)
