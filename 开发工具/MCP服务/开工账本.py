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
from 运行数据根 import 无位置, 子目录路径, 解析当前环境, 确保子目录  # noqa: E402

子目录类 = "数据库"
库文件名 = "开工账本.db"
时刻格式 = "%Y-%m-%dT%H:%M:%S%z"
前置文件名 = "派腿前置.md"        # 收口方维护的《派腿前置》，落 `<运行数据根>/临时件/`

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
    return 确保子目录(解析当前环境(), 子目录类) / 库文件名


def 连账本() -> sqlite3.Connection:
    """开账本（第一次用就建表）。"""
    连接 = sqlite3.connect(str(账本路径()))
    连接.row_factory = sqlite3.Row
    for 一条 in 建表语句:
        连接.execute(一条)
    连接.commit()
    return 连接


# ── 开工 ────────────────────────────────────────────────────────────────────────────────

def 新开工号(连接: sqlite3.Connection) -> str:
    """下一个开工号：`v1-` + 6 位递增号（**只增不复用**）。

    复用号会让旧记录与支线撞名 ⇒ 那是最难查的一类错，所以取「已出现过的最大号 + 1」，
    不取「当前行数 + 1」。
    """
    源码行 = 连接.execute("select 开工号 from 开工 order by 开工号 desc limit 1").fetchone()
    号值 = int(源码行["开工号"][3:]) + 1 if 源码行 else 100001
    return "v1-%06d" % 号值


def 登记开工(连接, 开工号: str, 工作内容: str, 分支名: str, 工作树: str) -> None:
    连接.execute("insert into 开工 (开工号, 工作内容, 分支名, 工作树, 状态, 开工时间) "
              "values (?, ?, ?, ?, ?, ?)",
              (开工号, 工作内容, 分支名, 工作树, 状态_进行中, 时刻串()))
    连接.commit()


def 读开工(连接, 开工号: str):
    """一条开工 ⇒ dict（没有就是 `None`）。"""
    源码行 = 连接.execute("select * from 开工 where 开工号 = ?", (开工号,)).fetchone()
    return dict(源码行) if 源码行 else None


def 列开工(连接, 上限: int = 20) -> list:
    return [dict(数据行) for 数据行 in 连接.execute(
        "select * from 开工 order by 开工号 desc limit ?", (上限,))]


def 搜开工(连接, 关键词: str, 上限: int = 20) -> list:
    """按关键词搜历史：面 = 工作内容 + 认领路径 + 改动路径（**不含 diff**，见文件头）。"""
    匹配模式 = "%" + 关键词 + "%"
    return [dict(数据行) for 数据行 in 连接.execute(
        "select distinct 开工.* from 开工 "
        "left join 认领 on 认领.开工号 = 开工.开工号 "
        "left join 改动 on 改动.开工号 = 开工.开工号 "
        "where 开工.工作内容 like ? or 认领.路径 like ? or 改动.路径 like ? "
        "order by 开工.开工号 desc limit ?", (匹配模式, 匹配模式, 匹配模式, 上限))]


def 置状态(连接, 开工号: str, 状态: str) -> None:
    连接.execute("update 开工 set 状态 = ?, 释放时间 = ? where 开工号 = ?",
              (状态, 时刻串() if 状态 != 状态_进行中 else None, 开工号))
    连接.commit()


# ── 认领 ────────────────────────────────────────────────────────────────────────────────

def 认领文件(连接, 开工号: str, 路径指纹表: dict) -> None:
    """登记/补充认领。**指纹由调用方读盘算好**（agent 从不传指纹）。"""
    for 路径, 指纹 in 路径指纹表.items():
        连接.execute("insert into 认领 (开工号, 路径, 指纹) values (?, ?, ?) "
                  "on conflict(开工号, 路径) do update set 指纹 = excluded.指纹",
                  (开工号, 路径, 指纹))
    连接.commit()


def 读认领(连接, 开工号: str) -> dict:
    return {数据行["路径"]: 数据行["指纹"] for 数据行 in 连接.execute(
        "select 路径, 指纹 from 认领 where 开工号 = ?", (开工号,))}


def 查跨开工冲突(连接, 开工号: str, 路径表) -> dict:
    """`{路径: [也认领了它的别的开工号…]}` —— 别的**未释放**开工占着同一个件。

    **只报不拦**：有时确实要两条开工改同一个件的不同节。但工具不许一句不说 ——
    两条开工各写各的工作树（**运行期不撞**），撞的是**合并期**；等合并时才发现最贵。
    """
    占表 = {}
    for 路径 in 路径表:
        行表 = 连接.execute(
            "select 认领.开工号 from 认领 join 开工 on 认领.开工号 = 开工.开工号 "
            "where 认领.路径 = ? and 认领.开工号 <> ? and 开工.状态 <> ?",
            (路径, 开工号, 状态_已释放)).fetchall()
        if 行表:
            占表[路径] = sorted(数据行[0] for 数据行 in 行表)
    return 占表


def 查同内容未释放(连接, 工作内容: str, 排除开工号: str) -> list:
    """**未释放**的开工里，工作内容与本次逐字相同（去首尾空白后）的那些 ⇒ `[(开工号, 工作内容)]`。

    **只报不拦**（口径与 `查跨开工冲突` 同一条）：有时确实要重开一条。但工具不许一句不说 ——
    实测 2026-09-27：同一条活登了两次（`v1-100002` 与 `v1-100007`，工作内容一模一样），
    留下一棵没人认领的孤儿工作树。
    """
    内容 = 工作内容.strip()
    if not 内容:
        return []
    return [(数据行["开工号"], 数据行["工作内容"]) for 数据行 in 连接.execute(
        "select 开工号, 工作内容 from 开工 "
        "where 工作内容 = ? and 开工号 <> ? and 状态 <> ? order by 开工号",
        (内容, 排除开工号, 状态_已释放))]


def 查重复登记(连接, 开工号: str, 工作内容: str, 路径表) -> list:
    """疑似重复登记的别的**未释放**开工 ⇒ `[(别的开工号, 原因)]`。**只报不拦**。

    两个面：① 工作内容逐字相同；② 认领路径**高度重叠**（重合 ≥ 2 件且占本次认领的一半以上）。
    路径那一面**复用** `查跨开工冲突`（同一份实现）—— 不写平行的第二套判断。
    """
    输出缓冲 = [(别的号, "工作内容逐字相同（它还没释放）")
         for 别的号, _ in 查同内容未释放(连接, 工作内容, 开工号)]
    重合表: dict = {}
    for 路径, 号表 in 查跨开工冲突(连接, 开工号, 路径表).items():
        for 别的号 in 号表:
            重合表.setdefault(别的号, []).append(路径)
    for 别的号, 件表 in sorted(重合表.items()):
        if len(件表) >= 2 and len(件表) * 2 >= len(路径表):
            输出缓冲.append((别的号, "认领路径高度重叠（重合 %d / 本次 %d 件）" % (len(件表), len(路径表))))
    return 输出缓冲


def 前置提示行() -> str:
    """收口方那份《派腿前置》存在 ⇒ 指路那一行；不存在 / 解析不出 ⇒ 空串（不编话）。

    落点走 `运行数据根` 包取（`子目录路径`）—— **不许自身拼路径**（判据 ㉕）。
    """
    try:
        路径 = 子目录路径(解析当前环境(), "临时件") / 前置文件名
    except 无位置:
        return ""
    if not 路径.is_file():
        return ""
    return ("开工前先读收口方的《派腿前置》：%s\n"
            "  （工具优先级 MCP 优先 · 硬纪律 · 提速红线 · 权威源地图 —— 腿不知道它存在 = 等于没写）" % 路径)


def 写回指纹(连接, 开工号: str, 路径: str, 指纹: str) -> None:
    """写盘之后把**新指纹**内置回认领那一栏（agent 全程不碰指纹）。

    **是 upsert 不是 update**：新建出来的件在认领那一刻盘上还不存在 ⇒ 认领表里没有它那一行
    （`读盘指纹` 只收读得到的件）⇒ 写完必须能**补进去**，否则这个件下一次改动会被第 ③ 道闸
    判成「变过」而永远改不动（实测这条：不改 upsert，新建完就再也改不了它）。
    """
    连接.execute("insert into 认领 (开工号, 路径, 指纹) values (?, ?, ?) "
              "on conflict(开工号, 路径) do update set 指纹 = excluded.指纹",
              (开工号, 路径, 指纹))
    连接.commit()


# ── 改动 ────────────────────────────────────────────────────────────────────────────────

def 记改动(连接, 开工号: str, 路径: str, 功能: str, 写前指纹: str, 写后指纹: str) -> None:
    连接.execute("insert into 改动 (开工号, 路径, 功能, 写前指纹, 写后指纹, 时间) "
              "values (?, ?, ?, ?, ?, ?)",
              (开工号, 路径, 功能, 写前指纹, 写后指纹, 时刻串()))
    连接.commit()


def 读改动(连接, 开工号: str) -> list:
    return [dict(数据行) for 数据行 in 连接.execute(
        "select * from 改动 where 开工号 = ? order by 编号", (开工号,))]


def 全部开工(连接) -> list:
    return [dict(数据行) for 数据行 in 连接.execute("select * from 开工 order by 开工号")]
