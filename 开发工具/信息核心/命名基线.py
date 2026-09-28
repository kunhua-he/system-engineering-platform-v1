# -*- coding: utf-8 -*-
"""命名基线 —— 判据 ㉒ 与 ㊷ 的**存量清单**读写（住规则库的两张表，**不落外部 json**）。

两张表都是「存量入基线、新增即红 · 基线只许减」那一套（判据 ⑲ 先立的形状）：
  · `命名基线` —— 判据 ㉒ 的六档：`(档, 路径, 名字, 处数)`；
  · `命名穷举基线` —— 判据 ㊷ 的三面：`(面, 名字, 处数)`。

**为何住库**（华哥 2026-09-29「全规则都在 db 里面。外部不留」）：基线是判据的**对象**，与名册
同一类东西。住库 ⇒ 夹具仓只要有一张最小库就照跑，不再多一份 json 要跟着维护。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

库相对路径 = "开发工具/信息核心/信息核心.db"
表_命名基线 = "命名基线"
表_穷举基线 = "命名穷举基线"


def 读命名基线(树根) -> tuple:
    """判据 ㉒ 的基线 ⇒ `({(档, 路径, 名字): 处数}, 错误或 None)`。"""
    return _读一张(树根, 表_命名基线, lambda 一行: ((一行[0], 一行[1], 一行[2]), 一行[3]))


def 读穷举基线(树根) -> tuple:
    """判据 ㊷ 的基线 ⇒ `({(面, 名字): 处数}, 错误或 None)`。"""
    return _读一张(树根, 表_穷举基线, lambda 一行: ((一行[0], 一行[1]), 一行[2]))


def _读一张(树根, 表名: str, 组键) -> tuple:
    """⇒ `(项表, 错误或 None)` —— 读不动就交错误回去（由判据报红 / 未判），不抛。"""
    库件 = Path(树根) / 库相对路径
    if not 库件.is_file():
        return {}, f"规则库不在（{库件}）"
    try:
        连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
        try:
            行表 = list(连接.execute(f"select * from {表名}"))
        finally:
            连接.close()
    except sqlite3.Error as 错误:
        return {}, f"`{表名}` 读不动：{错误}"
    项表 = {}
    for 一行 in 行表:
        键名, 处数 = 组键(一行)
        项表[键名] = int(处数 or 0)
    return 项表, None


def 写命名基线(树根, 项表: dict) -> int:
    """把判据 ㉒ 的基线**整表重写**（登记 / 删陈旧登记都走它）⇒ 写入行数。"""
    return _写一张(树根, 表_命名基线,
               [(*键名, 处数) for 键名, 处数 in sorted(项表.items())])


def 写穷举基线(树根, 项表: dict) -> int:
    """把判据 ㊷ 的基线**整表重写** ⇒ 写入行数。"""
    return _写一张(树根, 表_穷举基线,
               [(*键名, 处数) for 键名, 处数 in sorted(项表.items())])


def _写一张(树根, 表名: str, 行表: list) -> int:
    """整表重写（先 delete 再 insert）—— **只有登记命令走它**，判据永远只读。"""
    连接 = sqlite3.connect(Path(树根) / 库相对路径)
    try:
        连接.execute(f"delete from {表名}")
        if 行表:
            连接.executemany(
                f"insert or replace into {表名} values({','.join('?' * len(行表[0]))})", 行表)
        连接.commit()
    finally:
        连接.close()
    return len(行表)
