# -*- coding: utf-8 -*-
"""建库 · 代码图 —— `codegraph` 索引库 → `代码名` · `节点` · `连接` 三表。"""
import sqlite3
from pathlib import Path

from .路径 import 仓根  # noqa: F401,E402 —— 先挂 sys.path（须在下面那条 import 之前）
from 代码地图.落点 import 库目录名, 库文件名  # noqa: E402

import 表定义  # noqa: E402

# 「一次扫描 → 多张表」的中间结果缓存：`节点` 与 `连接` 共用一次读。
_拓扑缓存: dict = {}


def 装代码名(根目录: Path) -> list:
    索引 = 根目录 / 库目录名 / 库文件名
    if not 索引.is_file():
        return []
    索引库 = sqlite3.connect(索引)
    输出行 = 索引库.execute(
        "select id, name, kind, language, qualified_name, file_path, start_line from nodes"
    ).fetchall()
    索引库.close()
    return 输出行


def 节点名(键名: str) -> tuple:
    路径段 = 键名.split("/")
    顶层 = 路径段[0]
    层名 = 表定义.顶层目录到层.get(顶层, 顶层)
    if 顶层 in 表定义.底座树 and len(路径段) > 1:
        return 层名, f"{顶层}/{路径段[1]}"
    return 层名, 顶层


def 装节点(根目录: Path) -> list:
    return _拓扑表(根目录)[0]


def 装连接(根目录: Path) -> list:
    return _拓扑表(根目录)[1]


def _拓扑表(根目录: Path) -> tuple:
    """代码地图索引 → `(节点行, 连接行)`。缓存住，两张表共用一次读。"""
    if 根目录 in _拓扑缓存:
        return _拓扑缓存[根目录]
    索引 = 根目录 / 库目录名 / 库文件名
    if not 索引.is_file():
        _拓扑缓存[根目录] = ([], [])
        return _拓扑缓存[根目录]
    索引库 = sqlite3.connect(索引)
    文件到节点, 节点集 = {}, {}
    for (文件,) in 索引库.execute("select distinct file_path from nodes where file_path is not null"):
        所在层, 节点键 = 节点名(文件)
        文件到节点[文件] = 节点键
        节点集[节点键] = 所在层
    边表 = {}
    for (源件, 目标件) in 索引库.execute(
        "select n1.file_path, n2.file_path from edges e "
        "join nodes n1 on n1.id = e.source join nodes n2 on n2.id = e.target "
        "where e.kind = 'imports'"
    ):
        起点, 终点 = 文件到节点.get(源件), 文件到节点.get(目标件)
        if not 起点 or not 终点 or 起点 == 终点:
            continue
        边表[(起点, 终点)] = 边表.get((起点, 终点), 0) + 1
    索引库.close()
    _拓扑缓存[根目录] = (
        [(节点键, 所在层, "节点", 表定义.节点职责.get(节点键, ""))
         for 节点键, 所在层 in 节点集.items()],
        [(起点, 终点, "imports", 条数) for (起点, 终点), 条数 in 边表.items()],
    )
    return _拓扑缓存[根目录]
