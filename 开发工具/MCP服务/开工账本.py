# -*- coding: utf-8 -*-
"""开工账本 —— 谁在干什么、干过什么（**唯一一本**，sqlite）。

三张表（`开工` · `认领` · `改动`），一把落 `<运行数据根>/数据库/开工账本.db`。
**只此一处**记开工状态 —— 原来那本 `开发工具/认领机制/账本.json` 已并进来（`决策记录/2026-09-27_开工账本与四道闸.md`）。

**为什么用 DB 不用 JSON**：JSON 的好处是能 `git diff` 看变化；但开工记录会随**每次写盘**长，
JSON 会越来越难看。DB 顺手解掉「明细疯长」这件事。代价是二进制 —— 它本来就落运行数据根
（不进版本库），是本地私有的记录。

**不存 diff**：diff 本来就在 git 里（支线名就是开工号），存第二份是第二套实现。
代价：搜历史搜不到「上次把超时从 30 改成 5 是哪条开工」—— 搜的面只有工作内容 + 认领路径 + 改动路径。

**时间**：一律本地时区的 ISO8601（`2026-09-27T21:05:03+0800`），一处格式化。
"""

import datetime
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/：取 运行数据根
from 运行数据根 import 解析当前, 确保子目录  # noqa: E402

子目录类 = "数据库"
库文件名 = "开工账本.db"
时刻格式 = "%Y-%m-%dT%H:%M:%S%z"

状态_进行中 = "进行中"
状态_待合并 = "已提交待合并"
状态_已释放 = "已释放"

建表语句 = (
    """create table if not exists 开工 (
        开工号    text primary key,
        工作内容  text not null,
        分支名    text not null,
        工作树    text not null,
        状态      text not null,
        开工时间  text not null,
        释放时间  text
    )""",
    """create table if not exists 认领 (
        开工号   text not null,
        路径     text not null,
        指纹     text not null,
        primary key (开工号, 路径)
    )""",
    """create table if not exists 改动 (
        编号     integer primary key autoincrement,
        开工号   text not null,
        路径     text not null,
        功能     text not null,
        写前指纹 text,
        写后指纹 text,
        时间     text not null
    )""",
)


def 时刻串() -> str:
    """当前时刻（本地时区 ISO8601）。**一处格式化**，别处不许自拼。"""
    return datetime.datetime.now().astimezone().strftime(时刻格式)


def 账本路径() -> Path:
    """`<运行数据根>/数据库/开工账本.db`。落点走 `运行数据根` 包 —— 本件不自拼路径（判据 ㉕）。"""
    return 确保子目录(解析当前(), 子目录类) / 库文件名


def 连账本() -> sqlite3.Connection:
    """开账本（第一次用就建表）。"""
    连 = sqlite3.connect(str(账本路径()))
    连.row_factory = sqlite3.Row
    for 一条 in 建表语句:
        连.execute(一条)
    连.commit()
    return 连


# ── 开工 ────────────────────────────────────────────────────────────────────────────────

def 新开工号(连: sqlite3.Connection) -> str:
    """下一个开工号：`v1-` + 6 位递增号（**只增不复用**）。

    复用号会让旧记录与支线撞名 ⇒ 那是最难查的一类错，所以取「已出现过的最大号 + 1」，
    不取「当前行数 + 1」。
    """
    行 = 连.execute("select 开工号 from 开工 order by 开工号 desc limit 1").fetchone()
    号 = int(行["开工号"][3:]) + 1 if 行 else 100001
    return "v1-%06d" % 号


def 登记开工(连, 开工号: str, 工作内容: str, 分支名: str, 工作树: str) -> None:
    连.execute("insert into 开工 (开工号, 工作内容, 分支名, 工作树, 状态, 开工时间) "
              "values (?, ?, ?, ?, ?, ?)",
              (开工号, 工作内容, 分支名, 工作树, 状态_进行中, 时刻串()))
    连.commit()


def 读开工(连, 开工号: str):
    """一条开工 ⇒ dict（没有就是 `None`）。"""
    行 = 连.execute("select * from 开工 where 开工号 = ?", (开工号,)).fetchone()
    return dict(行) if 行 else None


def 列开工(连, 上限: int = 20) -> list:
    return [dict(行) for 行 in 连.execute(
        "select * from 开工 order by 开工号 desc limit ?", (上限,))]


def 搜开工(连, 关键词: str, 上限: int = 20) -> list:
    """按关键词搜历史：面 = 工作内容 + 认领路径 + 改动路径（**不含 diff**，见文件头）。"""
    模 = "%" + 关键词 + "%"
    return [dict(行) for 行 in 连.execute(
        "select distinct 开工.* from 开工 "
        "left join 认领 on 认领.开工号 = 开工.开工号 "
        "left join 改动 on 改动.开工号 = 开工.开工号 "
        "where 开工.工作内容 like ? or 认领.路径 like ? or 改动.路径 like ? "
        "order by 开工.开工号 desc limit ?", (模, 模, 模, 上限))]


def 置状态(连, 开工号: str, 状态: str) -> None:
    连.execute("update 开工 set 状态 = ?, 释放时间 = ? where 开工号 = ?",
              (状态, 时刻串() if 状态 != 状态_进行中 else None, 开工号))
    连.commit()


# ── 认领 ────────────────────────────────────────────────────────────────────────────────

def 认领文件(连, 开工号: str, 路径指纹表: dict) -> None:
    """登记/补充认领。**指纹由调用方读盘算好**（agent 从不传指纹）。"""
    for 路径, 指纹 in 路径指纹表.items():
        连.execute("insert into 认领 (开工号, 路径, 指纹) values (?, ?, ?) "
                  "on conflict(开工号, 路径) do update set 指纹 = excluded.指纹",
                  (开工号, 路径, 指纹))
    连.commit()


def 读认领(连, 开工号: str) -> dict:
    return {行["路径"]: 行["指纹"] for 行 in 连.execute(
        "select 路径, 指纹 from 认领 where 开工号 = ?", (开工号,))}


def 写回指纹(连, 开工号: str, 路径: str, 指纹: str) -> None:
    """写盘之后把**新指纹**内置回认领那一栏（agent 全程不碰指纹）。"""
    连.execute("update 认领 set 指纹 = ? where 开工号 = ? and 路径 = ?", (指纹, 开工号, 路径))
    连.commit()


# ── 改动 ────────────────────────────────────────────────────────────────────────────────

def 记改动(连, 开工号: str, 路径: str, 功能: str, 写前指纹: str, 写后指纹: str) -> None:
    连.execute("insert into 改动 (开工号, 路径, 功能, 写前指纹, 写后指纹, 时间) "
              "values (?, ?, ?, ?, ?, ?)",
              (开工号, 路径, 功能, 写前指纹, 写后指纹, 时刻串()))
    连.commit()


def 读改动(连, 开工号: str) -> list:
    return [dict(行) for 行 in 连.execute(
        "select * from 改动 where 开工号 = ? order by 编号", (开工号,))]


def 全部开工(连) -> list:
    return [dict(行) for 行 in 连.execute("select * from 开工 order by 开工号")]
