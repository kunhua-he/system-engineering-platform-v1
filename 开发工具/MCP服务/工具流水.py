# -*- coding: utf-8 -*-
"""工具流水 —— 开工的**后台自动事实**（sqlite，落**同一本** `<运行数据根>/数据库/开工账本.db`）。

**它是什么**：网关（`参数规范.py::网关派发`）在**每次带明确开工ID**的工具调用后，自动记一行
**白名单元数据**：工具名 · 操作 · 开工号 · 时刻 · 退出码 · 写前/写后指纹 · 作业任务ID。
它让「这条开工一路调了哪些工具 · 哪一次写盘 · 写到什么指纹 · 起了哪个后台作业」在**崩溃后**仍可查。

**它不是什么**：绝不记 `arguments` / 请求正文 / 环境变量 / 请求头 / 任何密钥。恢复摘要也**绝不**
从它臆测模型思维 —— 摘要只由「开工行字段 + agent 显式写的检查点行」合成（见 `开工记忆.py`）；
流水只当**旁证**（时间线）。

**有界封顶**：口径同 `<运行数据根>/日志` —— 只增有顶、到顶丢最旧，不滚雪球。到 `封顶行数` 就按
`裁掉条数` 裁一批最旧行（一次裁一批，不每条都裁）。**不另立第二记忆库**：表建在开工账本那本库上。

**失败即缺一条事实**：`记流水` 一律吞异常、绝不阻断工具调用。写操作（`v1_edit` / 状态翻）的恢复
关键证据仍走各自**真实事务**（`写盘账本` / `写盘意图`），**不由流水代保证**。

**并发**：写盘走 `begin immediate`（与账本其余写口同形，条件式、不无条件覆盖）。

**记账域（2026-10-08 加 · 自检隔离）**：`--自检` 的域内调用会往**生产**账本落遥测（实测每次
6 行，生产库 3148 行里约 76% 是自检遥测）—— 既污染生产时间线，又让多路自检抢同一把
`begin immediate` 写锁。`临时记账库()` 是**逐进程**的作用域（ContextVar）：域内 `记流水` 仍走
**同一份实现**，只把落点换成进程私有的临时库；**域外（生产默认）路径与行为逐字不变**。
"""

import contextlib
import contextvars as 上下文变量
import re
import sqlite3

from . import 开工账本 as 账本

流水建表语句 = (
    """create table if not exists 工具流水 (
        编号       integer primary key autoincrement,
        工具名     text not null,
        操作       text,
        开工号     text,
        时刻       text not null,
        退出码     integer,
        写前指纹   text,
        写后指纹   text,
        作业任务ID text
    )""",
)

封顶行数 = 4000            # 有界封顶（口径同 `<运行数据根>/日志`：到顶丢最旧，不滚雪球）
裁掉条数 = 500             # 到顶一次裁掉的旧行数（一批一批裁，避免每条都裁）
# 哪些工具**不记**：`v1_context` 自述「不写记忆」⇒ 它的调用一行都不落。
不记工具 = ("v1_context",)
# 只从回执里摘这一个**白名单标记**（32 位十六进制任务ID）；绝不存回执正文。
任务号形状 = re.compile(r"任务ID：([0-9a-f]{32})")

# ── 记账域（自检隔离）───────────────────────────────────────────────────────────
# 域内改落**进程私有**的临时库：`记流水` 仍是同一份实现，只换落点；域外一律走生产口。
# **作用域边界**：`ContextVar` 是**线程上下文**的 —— 子进程**不继承**（隔离样本的子进程各进各的域）；
# 线程池 worker 起手是**空上下文**（继承不到调用方的域）。当前 worker 只起子进程、由子进程各进各的域
# ⇒ 无生产写；**将来若有线程直接调工具，必须在那个线程里显式 `set`**（别当「逐进程」覆盖全线程）。
记账目的地 = 上下文变量.ContextVar("记账目的地", default=None)


@contextlib.contextmanager
def 临时记账库():
    """临时记账作用域：域内 `记流水` 真写进程私有的临时库，出域恢复默认（临时目录即清）。

    出域（含域内抛异常）一律 `reset` 回原目的地 ⇒ 不泄漏到并发生产请求。
    **边界**：子进程不继承本域、线程池 worker 起手是空上下文 ⇒ 子进程 / 线程要各自 `with` 一次
    （本件只在自检里用；线程直接调工具的场景当前不存在，出现了必须显式进域）。
    """
    import shutil
    import tempfile
    from pathlib import Path
    临时根 = Path(tempfile.mkdtemp(prefix="v1临时记账-"))
    旧目的地 = 记账目的地.set(临时根 / "开工账本.db")
    try:
        yield 临时根
    finally:
        记账目的地.reset(旧目的地)
        shutil.rmtree(临时根, ignore_errors=True)


def _开记账连接():
    """记账连接口：域内开临时库（建表同 `账本.建表语句` **一份**），域外走 `账本.连账本()`。"""
    路径 = 记账目的地.get()
    if 路径 is None:
        return 账本.连账本()
    连接 = sqlite3.connect(str(路径))
    连接.row_factory = sqlite3.Row
    for 建表语句行 in 账本.建表语句:
        连接.execute(建表语句行)
    连接.commit()
    return 连接


def 补流水表(连接) -> None:
    """建 `工具流水` 表（幂等）。表落**同一本**开工账本库上 —— 不另立第二记忆库。"""
    for 建表语句行 in 流水建表语句:
        连接.execute(建表语句行)
    连接.commit()


def _摘作业任务ID(输出文本) -> str:
    """只从回执里摘 32 位十六进制任务ID（白名单标记）；摘不到给空串。**绝不存正文**。"""
    if not isinstance(输出文本, str):
        return ""
    命中 = 任务号形状.search(输出文本)
    return 命中.group(1) if 命中 else ""


def _最近写盘(连接, 开工号: str) -> tuple:
    """本开工 `改动` 表**最新一条**的 `(写前指纹, 写后指纹)`；没有 ⇒ `("", "")`。

    指纹不是从 arguments 来的（那会漏正文），而是取**已提交的真实改动行** —— 写操作的权威证据
    在 `改动` 表，流水只引它。
    """
    数据行 = 连接.execute(
        "select 写前指纹, 写后指纹 from 改动 where 开工号 = ? order by 编号 desc limit 1",
        (开工号,)).fetchone()
    if 数据行 is None:
        return "", ""
    return (数据行["写前指纹"] or ""), (数据行["写后指纹"] or "")


def _封顶(连接) -> int:
    """到顶就裁掉最旧的 `裁掉条数` 行 ⇒ 裁掉的行数（0 = 没到顶，一个字节不动）。"""
    总数 = 连接.execute("select count(*) from 工具流水").fetchone()[0]
    if 总数 <= 封顶行数:
        return 0
    return 连接.execute(
        "delete from 工具流水 where 编号 in "
        "(select 编号 from 工具流水 order by 编号 asc limit ?)", (裁掉条数,)).rowcount


def _关联作业开工(任务ID: str, 开工号: str) -> None:
    """`作业` 表**有** `开工ID` 列时，把该后台作业的开工归属补上。

    该列**由另一条腿负责加**（本件不重复加列，只在该列存在时关联）；列不在就什么都不做。
    """
    if not 任务ID or not 开工号:
        return
    from .作业账本 import 作业账本路径
    连接 = sqlite3.connect(str(作业账本路径()), timeout=2)
    try:
        连接.row_factory = sqlite3.Row
        列名集 = {文本行[1] for 文本行 in 连接.execute("pragma table_info(作业)")}
        if "开工ID" not in 列名集:
            return
        连接.execute("update 作业 set 开工ID = ? where 任务ID = ? and (开工ID is null or 开工ID = '')",
                  (开工号, 任务ID))
        连接.commit()
    except sqlite3.Error:
        return
    finally:
        连接.close()


def 记流水(工具名: str, 操作名: str, 开工号: str, 退出码, 输出文本="") -> None:
    """记一行白名单元数据。**一律吞异常** —— 记不上 = 缺一条事实，绝不阻断工具调用。

    只收**白名单元数据**；不落 `arguments` / 请求正文 / 环境变量 / 请求头 / 密钥。
    给了明确开工号、且给了操作、且不是「不写记忆」的工具 ⇒ 才记。
    """
    try:
        if not 开工号 or not 操作名:
            return
        # `v1_context` 自述「不写记忆」；`安全清收口` 自身不落（否则刚清完又立刻留一行，违背「真删」）。
        if 工具名 in 不记工具 or 操作名 == "安全清收口":
            return
        # `v1_edit` 的 `只检查` / **被拒**路径必须**零写入**（硬判据 ㊽ 的样本断言全树指纹不变）⇒ 不落；
        # 写操作的关键证据走 `写盘意图` / `写盘账本`，流水只记**成功的写**。
        if 工具名 == "v1_edit" and (操作名 == "只检查" or 退出码 != 0):
            return
        作业任务ID = ""
        if 工具名 == "v1_job" and 操作名 == "start":
            作业任务ID = _摘作业任务ID(输出文本)
        连接 = _开记账连接()
        try:
            补流水表(连接)
            写前指纹 = 写后指纹 = ""
            if 工具名 == "v1_edit":
                写前指纹, 写后指纹 = _最近写盘(连接, 开工号)
            连接.execute("begin immediate")
            连接.execute(
                "insert into 工具流水 (工具名, 操作, 开工号, 时刻, 退出码, 写前指纹, 写后指纹, 作业任务ID) "
                "values (?, ?, ?, ?, ?, ?, ?, ?)",
                (工具名, 操作名, 开工号, 账本.时刻串(), 退出码, 写前指纹, 写后指纹, 作业任务ID))
            _封顶(连接)
            连接.commit()
        finally:
            连接.close()
        if 作业任务ID:
            _关联作业开工(作业任务ID, 开工号)
    except Exception:            # 记流水是旁证：记不上就当缺一条，绝不把工具调用带崩
        return


def 读流水(连接, 开工号: str, 记录条数: int = 40) -> list:
    """本开工的流水，**最新在前**（倒序）。"""
    return [dict(数据行) for 数据行 in 连接.execute(
        "select * from 工具流水 where 开工号 = ? order by 编号 desc limit ?", (开工号, 记录条数))]


def 清流水(连接, 开工号: str) -> int:
    """**真删**本开工的全部流水 ⇒ 删掉的行数。只由安全收口在条件逐条成立后调用；不另建历史库。"""
    行数 = 连接.execute("delete from 工具流水 where 开工号 = ?", (开工号,)).rowcount
    连接.commit()
    return 行数
