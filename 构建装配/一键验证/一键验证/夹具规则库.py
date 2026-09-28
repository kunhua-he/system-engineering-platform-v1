# -*- coding: utf-8 -*-
"""夹具规则库 —— 给**合成仓**造一份最小规则库（判据 ㉒ 读基线 · 判据 ㊷ 读名册都要它）。

**为何要它**：名册与基线都住规则库（华哥 2026-09-29「全规则都在 db 里面。外部不留」）⇒
夹具仓也得有一张库，否则判据读不到 ⇒ fail-closed 报红（那会让**正向样本**当场红，元判据 ⑭ 不过）。

**名册从夹具仓的干净代码派生**（不手写一份清单）：夹具件改了不用跟着改清单；
而**注入件是在建库之后才落盘的** ⇒ 它的名不在名册里 ⇒ 「新增即红」照旧成立。
★ 诚实登记：派生走**判据同一套扫描器** ⇒ 扫描器坏掉时名册会偏小（读数偏**红**，不会假绿）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

库相对路径 = "开发工具/信息核心/信息核心.db"

# 夹具只需要判据用到的那几张表（真仓的库有 8 张源表，夹具不必跟）。
建表 = (
    "create table if not exists 命名定义(语义 text primary key, 唯一名 text not null, 现状 text)",
    "create table if not exists 命名例外(名 text primary key)",
    "create table if not exists 命名基线(档 text not null, 路径 text not null, 名字 text not null, 处数 integer not null, primary key(档, 路径, 名字))",
    "create table if not exists 命名穷举基线(面 text not null, 名字 text not null, 处数 integer not null, primary key(面, 名字))",
)


def 取命名扫描():
    """惰性取**剥器**（本包的 `命名扫描.py`）—— 剥注释与字符串只此一份。"""
    from . import 命名扫描

    return 命名扫描


def 取命名后缀() -> tuple:
    """惰性取**命名后缀表**（`开发工具/代码地图/查名.py`）—— 口径只此一份。"""
    工具根 = Path(__file__).resolve().parents[3]
    根目录 = str(工具根 / "开发工具")
    if 根目录 not in sys.path:
        sys.path.insert(0, 根目录)
    import 代码地图.查名 as 查名

    return tuple(查名.命名后缀)


def 名册表(件表: dict) -> list:
    """夹具仓的干净代码里的**全部标识符** ⇒ 名册名表（排序去重）。

    用「全部标识符」而不是「三面绑定」：夹具的定义面靠**合成索引**（判据要读面那一刻才造，
    造仓时还没有）⇒ 只取绑定会漏掉模块级名，那会让正向样本当场红。
    """
    命名扫描 = 取命名扫描()
    后缀表 = 取命名后缀()
    名集 = set()
    for 路径, 文本 in 件表.items():
        if not 路径.endswith(后缀表):
            continue
        后缀 = "." + 路径.rsplit(".", 1)[-1]
        名集.update(命名扫描.抽标识符(命名扫描.剥后缀(后缀, 文本)))
    return sorted(名集)


def 建夹具规则库(临根: Path, 件表: dict) -> Path:
    """在夹具仓里造一份最小规则库（名册 = 夹具干净代码的标识符；两张基线留空）⇒ 库路径。"""
    库件 = 临根 / 库相对路径
    库件.parent.mkdir(parents=True, exist_ok=True)
    连接 = sqlite3.connect(库件)
    try:
        for 语句 in 建表:
            连接.execute(语句)
        for 出现名 in 名册表(件表):
            连接.execute("insert or replace into 命名定义 values(?,?,?)",
                       (出现名, 出现名, "（名即语义）"))
    finally:
        连接.commit()
        连接.close()
    return 库件
