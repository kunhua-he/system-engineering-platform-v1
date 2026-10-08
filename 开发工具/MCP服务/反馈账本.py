# -*- coding: utf-8 -*-
"""反馈账本 —— 代理反馈的**来源 · 条目 · 判词 · 证据 · 批次 · 关闭**（与开工账本**同一本库**）。

**一句话**：反馈的**发现**与**处置**分开存 —— 代理只填发现（现象 · 落点 · 触发 · 预期与实际 ·
证据或明确未测），主策划给判词（债务 / 非问题 / 待核）并关联**唯一现行台账条目**或**真实开工**；
关闭要**真实验证证据**与**承接提交**，**代理自报不算验收**。

**为什么与开工账本同库**：它本来就是本地私有的运行记录（不进版本库），开工号是天然外键；
另开一本库 = 第二本账 + 跨库事务不可用（而验收要求「整批事务」）。

六张表（**只此一处**建）：
  反馈来源   一份报告一条（开工号 · 来源标识 · 内容指纹 · 读取状态 · 提取条数 · 判词条数 · 审完时刻）
  反馈条目   一条发现一条（现象 · 落点 · 触发 · 预期 · 实际 · 证据 · 未测 · 耗时 · 次数 · 并入主条目）
  反馈判词   一条条目**至多一条现行**判词（判词 · 理由 · 关联种类 · 关联目标 · 关联状态）
  反馈证据   补证（只增不改）
  反馈批次   客户端幂等键（同键同文 ⇒ 重放；同键异文 ⇒ 拒且整批零写）
  反馈关闭   验证关闭（验证证据 · 验证命令 · 退出码 · 承接提交 · 输出指纹 · 日志指针）

**指纹一处算**（`算指纹`）：条目指纹与批次载荷指纹都走它，别处不许自拼。
**未蒸馏判据一处**：`反馈关联.py::未蒸馏反馈集`（要解析台账与开工，故不住本件）。
"""

import hashlib
import json
import re
import sqlite3

from . import 开工账本 as 账本

# ── 封闭档表（写死在这里，别处不许自拼字符串）──────────────────────────────────────────────
判词_债务 = "债务"
判词_非问题 = "非问题"
判词_待核 = "待核"
判词档表 = (判词_债务, 判词_非问题, 判词_待核)

关联_台账 = "未完成条目"
关联_开工 = "开工"
关联档表 = (关联_台账, 关联_开工)

关联状态_现行 = "现行"
关联状态_已撤 = "已撤"

# 读取状态四档（封闭）：`未读` = 有输出但**尚未逐字审读**（默认档）；`已读` = 已读完；
# `空报告待核` / `缺件待核` = 显式待核（缺件可无 sha，内容身份用 `缺件指纹标记` 占位）。
# `已读` / `已提取` **都不等于审完** —— 审完只能由 `登记报告审完` 人工声明。
读取_未读 = "未读"
读取_已读 = "已读"
读取_空报告 = "空报告待核"
读取_缺件 = "缺件待核"
读取状态档表 = (读取_未读, 读取_已读, 读取_空报告, 读取_缺件)
# 缺件来源无内容身份 ⇒ 用**标记串**占内容指纹那一栏；发现输出后新 sha 即**新来源**，不覆盖旧记录。
缺件指纹标记 = "missing"

# 开工号形状：`v1-` 加六位数字（与开工账本同一形状；本件是反馈侧的**唯一**一份）。
开工号形状 = re.compile(r"v1-[0-9]{6}")
# 报告指纹形状：十六进制串（sha256 一类）；太短的不当指纹（「来源含内容 sha」）。
指纹形状 = re.compile(r"[0-9a-fA-F]{8,128}")
# 短回执里现象截断的默认宽度（要全文就传 `展开` = 真）。
截断宽度 = 40

建表语句 = (
    """create table if not exists 反馈来源 (
        来源号    integer primary key autoincrement,
        开工号    text not null,
        来源标识  text not null,
        内容指纹  text not null,
        报告路径  text,
        读取状态  text not null,
        提取条数  integer not null default 0,
        判词条数  integer not null default 0,
        待核理由  text,
        审完时刻  text,
        审完说明  text,
        登记时刻  text not null,
        unique (开工号, 来源标识, 内容指纹)
    )""",
    """create table if not exists 反馈条目 (
        条目号      integer primary key autoincrement,
        来源号      integer not null,
        开工号      text not null,
        现象        text not null,
        落点        text,
        触发        text,
        预期        text,
        实际        text,
        证据        text,
        未测        text,
        耗时毫秒    integer,
        调用次数    integer,
        并入主条目  integer,
        条目指纹    text not null,
        登记时刻    text not null
    )""",
    """create table if not exists 反馈判词 (
        编号      integer primary key autoincrement,
        条目号    integer not null unique,
        判词      text not null,
        理由      text not null,
        关联种类  text,
        关联目标  text,
        关联状态  text not null,
        判定开工号 text,
        判定时刻  text not null
    )""",
    """create table if not exists 反馈证据 (
        编号      integer primary key autoincrement,
        条目号    integer not null,
        证据      text not null,
        来源      text,
        补证开工号 text,
        补证时刻  text not null
    )""",
    """create table if not exists 反馈批次 (
        幂等键    text primary key,
        开工号    text not null,
        载荷指纹  text not null,
        结果摘要  text not null,
        提交时刻  text not null
    )""",
    """create table if not exists 反馈关闭 (
        编号      integer primary key autoincrement,
        条目号    integer not null unique,
        验证证据  text not null,
        验证命令  text not null,
        退出码    integer not null,
        承接提交  text not null,
        输出指纹  text,
        日志指针  text,
        关闭开工号 text,
        关闭时刻  text not null
    )""",
)


# ── 通用小工具 ────────────────────────────────────────────────────────────────────────────

def 时刻串() -> str:
    """当前时刻（本地时区 ISO8601）。**唯一格式化口**是开工账本那一处，本件只转发。"""
    return 账本.时刻串()


def 算指纹(原值) -> str:
    """值 ⇒ sha256（规范 JSON：键排序 + 无空格）。**唯一指纹口**。"""
    规范文本 = json.dumps(原值, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(规范文本.encode("utf-8")).hexdigest()


def 截断(原文本, 宽度: int = 截断宽度) -> str:
    """单行短文本（去换行 + 截断加省略号）—— 短回执不许回整篇正文。"""
    净文本 = " ".join(str(原文本 or "").split())
    return 净文本 if len(净文本) <= 宽度 else 净文本[:宽度] + "…"


def 拼回执(读数: dict) -> str:
    """短回执：结构化一行 JSON（网关把它放进信封的 `结果`）—— 分页/提交都回它，不回整篇正文。"""
    return json.dumps(读数, ensure_ascii=False)


def 是开工号(候选值) -> bool:
    return bool(开工号形状.fullmatch(str(候选值 or "").strip()))


def 是报告指纹(候选值) -> bool:
    return bool(指纹形状.fullmatch(str(候选值 or "").strip()))


def 连反馈库() -> sqlite3.Connection:
    """开**同一本**开工账本库并确保反馈六表在（第一次用就建表）。"""
    连接 = 账本.连账本()
    for 建表语句行 in 建表语句:
        连接.execute(建表语句行)
    _补列(连接)
    连接.commit()
    return 连接


def _补列(连接) -> None:
    """老库补列（`反馈关闭` 的 `输出指纹` / `日志指针`）—— `create table if not exists` 只对新库生效。"""
    列名集 = {文本行[1] for 文本行 in 连接.execute("pragma table_info(反馈关闭)")}
    for 栏名 in ("输出指纹", "日志指针"):
        if 栏名 not in 列名集:
            连接.execute("alter table 反馈关闭 add column %s text" % 栏名)


def 开工在吗(连接, 开工号: str) -> bool:
    return bool(账本.读开工(连接, 开工号))


# ── 读行 ──────────────────────────────────────────────────────────────────────────────────

def 读来源(连接, 来源号):
    数据行 = 连接.execute("select * from 反馈来源 where 来源号 = ?", (来源号,)).fetchone()
    return dict(数据行) if 数据行 else None


def 读条目(连接, 条目号):
    数据行 = 连接.execute("select * from 反馈条目 where 条目号 = ?", (条目号,)).fetchone()
    return dict(数据行) if 数据行 else None


def 读判词(连接, 条目号):
    数据行 = 连接.execute("select * from 反馈判词 where 条目号 = ?", (条目号,)).fetchone()
    return dict(数据行) if 数据行 else None


def 读关闭(连接, 条目号):
    数据行 = 连接.execute("select * from 反馈关闭 where 条目号 = ?", (条目号,)).fetchone()
    return dict(数据行) if 数据行 else None


def 列来源(连接, 开工号: str) -> list:
    return [dict(数据行) for 数据行 in 连接.execute(
        "select * from 反馈来源 where 开工号 = ? order by 来源号", (开工号,))]


def 计次(连接, 条目号: int) -> int:
    """本条目自身 + **显式并入**它的条目数（语义合并保留计次）。"""
    return 1 + 连接.execute("select count(*) from 反馈条目 where 并入主条目 = ?",
                       (条目号,)).fetchone()[0]


def 有效判词(连接, 条目号: int):
    """条目**现行有效**判词：本条目有判词就用它；已并入主条目就取主条目的。"""
    判词行 = 读判词(连接, 条目号)
    if 判词行:
        return 判词行
    条目行 = 读条目(连接, 条目号)
    if 条目行 and 条目行.get("并入主条目"):
        return 读判词(连接, 条目行["并入主条目"])
    return None


def 已判词集(连接, 开工号: str) -> set:
    """本开工**已判词**的条目号集（含「已并入主条目且主条目有判词」的从条目）—— 一条 SQL。"""
    return {数据行[0] for 数据行 in 连接.execute(
        "select 条目号 from 反馈条目 where 开工号 = ? and ("
        "  exists(select 1 from 反馈判词 where 反馈判词.条目号 = 反馈条目.条目号)"
        "  or exists(select 1 from 反馈判词 where 反馈判词.条目号 = 反馈条目.并入主条目))",
        (开工号,))}
