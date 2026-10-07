# -*- coding: utf-8 -*-
"""作业账本 —— 后台作业的**唯一**落盘状态（sqlite），落 `<运行数据根>/数据库/作业账本.db`。

**为什么必须落盘**：MCP 服务是长驻进程，且改了 `MCP服务/**` 后**自愈 exec**（下一帧即新码）
—— 进程内存态会被冲掉。作业状态只住内存 ⇒ 重载后「还在跑」与「早完了」分不出，把失败静默
当成功。故状态一律落盘；日志另落 `<运行数据根>/日志/<任务ID>.log`（标准错误走
`<任务ID>.错误.log`，工作进程自身的诊断走 `<任务ID>.工作.log`）。

**并发**：取消者与工作进程会并发写同一行 ⇒ 一切写盘走 `改行` 的**条件更新**（按当前状态加
白名单），绝不无条件覆盖（无条件会把「已取消」抹成「已完成」）。

**路径只经** `开发工具/运行数据根/口径.py`（判据 ㉕：不许自身拼路径）。
"""

import datetime
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/
from 运行数据根 import 解析当前环境, 确保子目录  # noqa: E402

子目录类别 = "数据库"
日志子目录类别 = "日志"
库文件名 = "作业账本.db"
日志后缀 = ".log"
错误日志后缀 = ".错误.log"
工作日志后缀 = ".工作.log"
时刻格式 = "%Y-%m-%dT%H:%M:%S%z"

状态_启动中 = "启动中"
状态_运行中 = "运行中"
状态_取消中 = "取消中"
状态_已完成 = "已完成"
状态_失败 = "失败"
状态_已取消 = "已取消"
状态_崩溃失联 = "崩溃失联"

# 非终态（可被收敛 / 可被取消抢占）；终态一旦落定就不许被覆盖。
非终态集 = (状态_启动中, 状态_运行中, 状态_取消中)
可抢态集 = (状态_启动中, 状态_运行中)
终态集 = (状态_已完成, 状态_失败, 状态_已取消, 状态_崩溃失联)
# 允许 `改行` 写的栏（栏名要进 SQL ⇒ 白名单，不拿调用方的键直接拼）。
可改栏 = ("开工ID", "状态", "完成时间", "退出码", "组号", "组代次", "命令组号", "命令代次", "截断", "说明")

建表语句 = (
    """create table if not exists 作业 (
        任务ID   text primary key,
        状态     text not null,
        命令     text not null,
        工作树   text not null,
        开工ID   text,
        开始时间 text not null,
        完成时间 text,
        退出码   integer,
        组号     integer,
        组代次   text,
        命令组号 integer,
        命令代次 text,
        截断     integer not null default 0,
        说明     text,
        具名     text
    )""",
)


def 时刻串() -> str:
    """当前时刻（本地时区 ISO8601）。**一处格式化**（与 `开工账本.py` 同形）。"""
    return datetime.datetime.now().astimezone().strftime(时刻格式)


def 作业账本路径() -> Path:
    """`<运行数据根>/数据库/作业账本.db` —— 落点走 `运行数据根` 包，本件不自拼路径。"""
    return 确保子目录(解析当前环境(), 子目录类别) / 库文件名


def 日志路径(任务ID: str, 档名后缀: str = 日志后缀) -> Path:
    """`<运行数据根>/日志/<任务ID><档名后缀>`。"""
    return 确保子目录(解析当前环境(), 日志子目录类别) / (任务ID + 档名后缀)


def 连账本() -> sqlite3.Connection:
    """开账本（第一次用就建表）。`timeout=5` = 与工作进程并发写时的等锁上限（秒）。"""
    连接 = sqlite3.connect(str(作业账本路径()), timeout=5)
    连接.row_factory = sqlite3.Row
    for 建表语句行 in 建表语句:
        连接.execute(建表语句行)
    _补列(连接)
    连接.commit()
    return 连接


def _补列(连接) -> None:
    """老库补列：`作业.开工ID`（2026-10-08 加 —— 「作业 → 开工」一眼可查）。

    `create table if not exists` 只对新库生效 ⇒ 老库要显式补。判定走 `pragma table_info`，
    补过就不动（**幂等**）；只 `add column`、不重建表 ⇒ 既有行一个字节都不丢。
    """
    列名集 = {文本行[1] for 文本行 in 连接.execute("pragma table_info(作业)")}
    for 列名 in ("具名", "开工ID"):
        if 列名 not in 列名集:
            连接.execute("alter table 作业 add column " + 列名 + " text")


def 落新行(任务ID: str, 命令: str, 工作树: str, 开始时间: str, 开工ID: str = "", 具名: str = "") -> None:
    """登记一条新作业（状态 = `启动中`，组号留空 —— 由调用方随后补）。

    `开工ID` = 这条作业服务的那条开工（`v1_job` 顶层开工号；`合主线` 用目标开工ID）——
    落列后「作业 → 开工」一眼可查，不必再靠命令文本 / 工作树路径猜。
    """
    连接 = 连账本()
    try:
        连接.execute(
            "insert into 作业 (任务ID, 状态, 命令, 工作树, 开工ID, 开始时间, 具名) values (?, ?, ?, ?, ?, ?, ?)",
            (任务ID, 状态_启动中, 命令, 工作树, 开工ID, 开始时间, 具名))
        连接.commit()
    finally:
        连接.close()


def 读行(任务ID: str):
    """读一条作业行 ⇒ `sqlite3.Row` 或 `None`（未知 ID 不编造）。"""
    连接 = 连账本()
    try:
        return 连接.execute("select * from 作业 where 任务ID=?", (任务ID,)).fetchone()
    finally:
        连接.close()


def 列作业(连接: sqlite3.Connection, 结果上限: int = 20) -> list:
    """最近作业 ⇒ `list[dict]`。**非终态在前**（好一眼看到在途的），再按开始时间倒序；有界。"""
    终态占位 = ",".join(["?"] * len(终态集))
    return [dict(数据行) for 数据行 in 连接.execute(
        "select * from 作业 order by (状态 in (%s)) asc, 开始时间 desc limit ?" % 终态占位,
        tuple(终态集) + (结果上限,))]


def 改行(任务ID: str, 允许状态集, 字段表: dict) -> int:
    """**条件更新**：只在该行**当前状态**落在 `允许状态集` 时改 ⇒ 返回改到的行数（0 = 没抢到）。"""
    未知栏 = sorted(set(字段表) - set(可改栏))
    if 未知栏:
        raise ValueError("不可改的栏：%s（只许 %s）" % ("、".join(未知栏), "、".join(可改栏)))
    赋值 = ", ".join("%s=?" % 栏名 for 栏名 in 字段表)
    状态占位 = ", ".join(["?"] * len(允许状态集))
    语句 = "update 作业 set %s where 任务ID=? and 状态 in (%s)" % (赋值, 状态占位)
    连接 = 连账本()
    try:
        游标 = 连接.execute(语句, tuple(字段表.values()) + (任务ID,) + tuple(允许状态集))
        连接.commit()
        return 游标.rowcount
    finally:
        连接.close()


def 落终态(任务ID: str, 退出码: int, 截断: int, 说明: str) -> None:
    """把终态落盘。**已被取消**（取消中 / 已取消）⇒ 记 `已取消`，不覆盖取消者的判定。
    两段**条件**更新 ⇒ 与取消者并发时不丢「已取消」。"""
    终态值 = 状态_已完成 if 退出码 == 0 else 状态_失败
    if 改行(任务ID, 可抢态集, {"状态": 终态值, "退出码": 退出码, "完成时间": 时刻串(),
                          "截断": 截断, "说明": 说明}):
        return
    改行(任务ID, (状态_取消中, 状态_已取消),
        {"状态": 状态_已取消, "退出码": 退出码, "完成时间": 时刻串(), "截断": 截断})
