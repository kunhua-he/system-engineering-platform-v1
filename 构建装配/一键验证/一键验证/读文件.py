# -*- coding: utf-8 -*-
"""并行读全仓 + 建上下文（文件表 · 包到层映射 · 仓根）。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from pathlib import Path

from . import 常量

from .小工具 import 是临时路径, 相对
from .常量 import 临时目录前缀, 号段图路径, 契约目录名, 常量表路径, 并发度, 扫描后缀, 编号字段, 编号目录, 跳过目录, 顶层目录到层
from .测试件 import 建测试文件集


def 扫源文件(仓根: Path) -> list:
    """全仓源码文件（跳过生成物与参照物目录）。"""
    结果 = []
    for 根, 目录表, 文件表 in os.walk(仓根):
        目录表[:] = [
            d
            for d in 目录表
            if d not in 跳过目录 and not d.startswith(常量.临时目录前缀)
        ]
        for 名 in 文件表:
            if 名.endswith(扫描后缀):
                结果.append(Path(根) / 名)
    return 结果


# ════════════════════════════════════════════════════════════════════════════
# ① 并行读（IO 密集 · 按文件分片 · 32 路）
# ════════════════════════════════════════════════════════════════════════════


def 读一个文件(任务: tuple) -> tuple:
    """一个分片的全部重活：读字节 → 解 UTF-8 → 解 JSON。都在这里做，并行跑。"""
    仓根, 路径 = 任务
    键 = 相对(仓根, 路径)
    try:
        字节 = 路径.read_bytes()
    except OSError as 错:
        return 键, {"文本": None, "数据": None, "错误": f"读不动：{错}"}
    try:
        文本 = 字节.decode("utf-8")
    except UnicodeDecodeError as 错:
        return 键, {"文本": None, "数据": None, "错误": f"不是 UTF-8：{错}"}
    数据 = None
    错 = None
    if 路径.suffix == ".json":
        try:
            数据 = json.loads(文本)
        except json.JSONDecodeError as 解析错:
            return 键, {"文本": 文本, "数据": None, "错误": f"JSON 解析失败：{解析错}"}
        if not isinstance(数据, dict):
            return 键, {
                "文本": 文本,
                "数据": None,
                "错误": f"顶层不是对象（是 {type(数据).__name__}）",
            }
    return 键, {"文本": 文本, "数据": 数据, "错误": 错}


def 并行读(仓根: Path, 路径表: list) -> dict:
    任务 = [(仓根, p) for p in 路径表]
    with ThreadPoolExecutor(max_workers=并发度) as 池:
        return dict(池.map(读一个文件, 任务))


def 建上下文(仓根: Path) -> dict:
    契约根 = 仓根 / 契约目录名
    # 一次扫全，按文件分片并行读（读 + 解 UTF-8 + 解 JSON 都在分片里）；
    # 后面所有检查都在内存里做，不再回磁盘。
    契约件 = sorted(契约根.rglob("*.json")) if 契约根.is_dir() else []
    # `rglob` 不走 `跳过目录` / 临时件排除 ⇒ 这里按同一口径再筛一遍
    # （否则落进 `契约声明/` 的临时声明根仍会被读进来，未完成事项.md #204）。
    契约件 = [p for p in 契约件 if not 是临时路径(相对(仓根, p))]
    源件 = [p for p in 扫源文件(仓根) if p.suffix != ".json"]
    文件 = 并行读(仓根, 契约件 + 源件)

    平台 = 解析(文件, f"{契约目录名}/平台声明.json")
    号段图 = 解析(文件, 号段图路径)
    常量表 = 解析(文件, 常量表路径)
    作废 = 解析(文件, f"{契约目录名}/作废号表.json")
    冻结 = 解析(文件, f"{契约目录名}/冻结登记.json")

    编号表 = {}
    目录存在 = {}
    for 目录 in 编号目录:
        目录存在[目录] = (契约根 / 目录).is_dir()
        记录表 = []
        前缀 = f"{契约目录名}/{目录}/"
        for 键 in sorted(文件):
            if not 键.startswith(前缀) or not 键.endswith(".json"):
                continue
            记录表.append(
                {
                    "目录": 目录,
                    "文件名": 键.rsplit("/", 1)[1],
                    "键": 键,
                    "字段": 编号字段[目录],
                    "数据": 文件[键]["数据"],
                    "错误": 文件[键]["错误"],
                }
            )
        编号表[目录] = 记录表

    return {
        "仓根": 仓根,
        "文件": 文件,
        "平台": 平台,
        "号段图": 号段图,
        "常量表": 常量表,
        "作废": 作废,
        "冻结": 冻结,
        "编号表": 编号表,
        "编号目录存在": 目录存在,
        "包到层": 建包到层映射(文件),
        "测试文件集": 建测试文件集(文件),
    }


def 建包到层映射(文件: dict) -> dict:
    """Cargo 包名 → 层。包名里的 `-` 换成 `_`（Rust 的 `use` 用下划线）。"""
    表 = {}
    for 键, 项 in 文件.items():
        if not 键.endswith("Cargo.toml") or 项["文本"] is None:
            continue
        配 = re.search(r"^\s*name\s*=\s*\"([^\"]+)\"", 项["文本"], re.M)
        if not 配:
            continue
        层 = 路径到层(键)
        if 层:
            表[配.group(1).replace("-", "_")] = 层
    return 表


def 路径到层(键: str) -> str:
    头 = 键.split("/", 1)[0]
    return 顶层目录到层.get(头, "")


def 解析(文件: dict, 键: str):
    项 = 文件.get(键)
    return None if 项 is None else 项["数据"]
