# -*- coding: utf-8 -*-
"""建库 · 源件 —— 读源表的仓内源件（`.json` / 名册两种形态）；`未完成` 表由它抽。"""
from pathlib import Path

import 表定义

from .通用 import 读JSON件, 读文本
from .文档 import 装文档


def 读源件(根目录: Path, 表名: str) -> list:
    """读源表的仓内源件（`表定义.源件表`，可多个）。**读不动就炸，绝不返回空** —— 返回空会把那张表洗白。"""
    全部行 = []
    for 相对路径 in 表定义.源件表[表名]:
        全部行 += 读一件(根目录 / 相对路径)
    return 全部行


def 读一件(源件路径: Path) -> list:
    """一个源件 → 行表。两种形态：`.json`（`{"说明", "行": [[…], …]}`）· 其它（一行一名，`#` 开头是注释）。

    名册行的两形：`名` = 名即语义（登记在册）；`名 → 新名` = 登记在册**且待改名**
    （`现状` 列写「待改名 → …」，新名可以有几个，用 ` · ` 分隔 —— 一个名指多件事要按角色拆名）。
    """
    if 源件路径.suffix == ".json":
        数据 = 读JSON件(源件路径)
        if not isinstance(数据, dict) or not isinstance(数据.get("行"), list):
            raise ValueError(f"源件读不动（要 {{'说明': …, '行': […]}}）：{源件路径}")
        return [tuple(一行) for 一行 in 数据["行"]]
    文本 = 读文本(源件路径)
    if not 文本:
        raise ValueError(f"源件读不动（文件不在或为空）：{源件路径}")
    行表 = []
    for 一行 in 文本.splitlines():
        条目 = 一行.strip()
        if not 条目 or 条目.startswith("#"):
            continue
        名字, _, 新名 = 条目.partition("→")
        名字 = 名字.strip()
        行表.append((名字, 名字, f"待改名 → {新名.strip()}" if 新名.strip() else "（名即语义）"))
    return 行表


def 装未完成(根目录: Path) -> list:
    return 读源件(根目录, "未完成")


def 装分片源件(连接, 表名: str, 分片列: str, 现抽, 根目录: Path) -> int:
    """分片源件表：只重抽**源件在场**的那几片，其余行**保住**（见 `表定义.分片源件表`）。

    `条款` 走这条：每片的源件 = 该片 `文档路径` 指的那份 md。md 在场 ⇒ 重抽它那几节；
    md 已删（全树只剩 `README.md` / `AGENTS.md`）⇒ 旧节一字不动（库是它们的唯一存本）。
    返回**整表**行数（读数口径与 `装表` 一致）。
    """
    文档行 = 装文档(根目录)
    在场路径表 = [一行[0] for 一行 in 文档行]
    数据行 = 现抽(根目录, 文档行)
    if 在场路径表:
        占位符 = ",".join("?" * len(在场路径表))
        连接.execute(f"delete from {表名} where {分片列} in ({占位符})", 在场路径表)
        if 数据行:
            连接.executemany(
                f"insert or replace into {表名} values({','.join('?' * len(数据行[0]))})", 数据行)
            落库行数 = 连接.execute(
                f"select count(*) from {表名} where {分片列} in ({占位符})", 在场路径表).fetchone()[0]
            if 落库行数 != len(数据行):
                raise ValueError(
                    f"{表名}：分片源件抽出 {len(数据行)} 行、落库只剩 {落库行数} 行 ⇒ "
                    f"有行被**主键**合并掉了（先修源件再跑）。")
    return 连接.execute(f"select count(*) from {表名}").fetchone()[0]
