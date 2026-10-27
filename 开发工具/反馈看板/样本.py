# -*- coding: utf-8 -*-
"""反馈看板 · 样本 —— 隔离夹具自测：**增改删**后资料组映射一致 · **读失败不报新鲜**。

**为什么隔离**：不动真库（真库 `mode=ro` 且不许写）；在临时目录造一本**同构**夹具库 + 一份
库 `未完成` 表，直接喂给 `取数.取数(库件=…, 台账件=…)`。**断言**：
  ① 一条债务关联现行台账号 ⇒ 落在「未完成条目|号」组，承接有效；
  ② 一条债务关联正式开工 ⇒ 落在「开工|号」组，承接有效；
  ③ 把关联改成台账里没有的号 ⇒ 掉进「缺关联」，承接有效 = 假（映射随库实时变）；
  ④ 增 / 删条目 ⇒ 组条数与总数实时跟变；
  ⑤ 库件不存在 / 坏件 / 台账不在 ⇒ `陈旧` = 真 · `错误` 非空（**读失败不报新鲜**）。
"""

import json
import sqlite3
import tempfile
from pathlib import Path

from . import 取数

夹具开工号 = "v1-900901"
台账号 = 901
缺件号 = 999999
夹具时刻 = "2026-10-08T00:00:00+0800"

建表语句 = (
    "create table 开工 (开工号 text primary key, 工作内容 text, 分支名 text, 工作树 text, "
    "状态 text, 开工时间 text, 释放时间 text, 父开工号 text, 开工种类 text)",
    "create table 反馈来源 (来源号 integer primary key autoincrement, 开工号 text, 来源标识 text, "
    "内容指纹 text, 报告路径 text, 读取状态 text, 提取条数 integer, 判词条数 integer, "
    "待核理由 text, 审完时刻 text, 审完说明 text, 登记时刻 text)",
    "create table 反馈条目 (条目号 integer primary key autoincrement, 来源号 integer, 开工号 text, "
    "现象 text, 落点 text, 触发 text, 预期 text, 实际 text, 证据 text, 未测 text, 耗时毫秒 integer, "
    "调用次数 integer, 并入主条目 integer, 条目指纹 text, 登记时刻 text)",
    "create table 反馈判词 (编号 integer primary key autoincrement, 条目号 integer unique, 判词 text, "
    "理由 text, 关联种类 text, 关联目标 text, 关联状态 text, 判定开工号 text, 判定时刻 text)",
    "create table 反馈证据 (编号 integer primary key autoincrement, 条目号 integer, 证据 text, "
    "来源 text, 补证开工号 text, 补证时刻 text)",
    "create table 反馈关闭 (编号 integer primary key autoincrement, 条目号 integer unique, "
    "验证证据 text, 验证命令 text, 退出码 integer, 承接提交 text, 输出指纹 text, 日志指针 text, "
    "关闭开工号 text, 关闭时刻 text)",
)


def 造夹具(根目录: Path) -> tuple:
    """临时目录里造一本同构夹具库（含 `未完成` 表）⇒ `(库件, 台账件)`。"""
    库件 = 根目录 / "夹具账本.db"
    台账件 = 库件
    连接 = sqlite3.connect(str(库件))
    try:
        for 建表行 in 建表语句:
            连接.execute(建表行)
        连接.execute("insert into 开工 (开工号, 工作内容, 状态) values (?, ?, ?)",
                 (夹具开工号, "夹具腿工作内容", "进行中"))
        连接.execute("create table if not exists 未完成(号 integer primary key, 缺什么 text not null, 落点 text, 验证命令 text)")
        连接.execute("insert or replace into 未完成(号, 缺什么, 落点, 验证命令) values(?,?,?,?)",
                 (台账号, "夹具缺什么", "夹具落点", "夹具验证"))
        连接.execute("insert into 反馈来源 (来源号, 开工号, 来源标识, 内容指纹, 报告路径, "
                 "读取状态, 提取条数, 判词条数, 审完时刻, 登记时刻) "
                 "values (1, ?, '样本/report.md', ?, '/tmp/report.md', '已读', 1, 1, ?, ?)",
                (夹具开工号, "a" * 64, 夹具时刻, 夹具时刻))
        连接.execute("insert into 反馈条目 (条目号, 来源号, 开工号, 现象, 证据, 条目指纹, 登记时刻) "
                 "values (1, 1, ?, '夹具现象一号', '夹具证据', ?, ?)", (夹具开工号, "f" * 64, 夹具时刻))
        连接.execute("insert into 反馈判词 (条目号, 判词, 理由, 关联种类, 关联目标, 关联状态, 判定时刻) "
                 "values (1, '债务', '夹具理由', '未完成条目', ?, '现行', ?)", (str(台账号), 夹具时刻))
        连接.commit()
    finally:
        连接.close()
    return 库件, 台账件


def 跑取数(库件, 台账件, 根目录: Path) -> dict:
    """跑一次取数（夹具库 / 夹具台账）。"""
    return 取数.取数(根目录, {"每页": 200}, 库件=库件, 台账件=台账件)


def 找组(载荷: dict, 组键: str):
    """按组键找资料组（没有 ⇒ None）。"""
    for 资料组 in 载荷.get("组") or []:
        if 资料组["组键"] == 组键:
            return 资料组
    return None


def 改判词(库件: Path, 关联种类: str, 关联目标: str) -> None:
    连接 = sqlite3.connect(str(库件))
    try:
        连接.execute("update 反馈判词 set 关联种类 = ?, 关联目标 = ? where 条目号 = 1",
                 (关联种类, 关联目标))
        连接.commit()
    finally:
        连接.close()


def 加条目(库件: Path, 条目号: int, 关联种类: str, 关联目标: str) -> None:
    连接 = sqlite3.connect(str(库件))
    try:
        连接.execute("insert into 反馈条目 (条目号, 来源号, 开工号, 现象, 证据, 条目指纹, 登记时刻) "
                 "values (?, 1, ?, '夹具现象二号', '夹具证据', ?, ?)",
                (条目号, 夹具开工号, "b" * 64, 夹具时刻))
        连接.execute("insert into 反馈判词 (条目号, 判词, 理由, 关联种类, 关联目标, 关联状态, 判定时刻) "
                 "values (?, '债务', '夹具理由', ?, ?, '现行', ?)",
                (条目号, 关联种类, 关联目标, 夹具时刻))
        连接.commit()
    finally:
        连接.close()


def 删条目(库件: Path, 条目号: int) -> None:
    连接 = sqlite3.connect(str(库件))
    try:
        连接.execute("delete from 反馈判词 where 条目号 = ?", (条目号,))
        连接.execute("delete from 反馈条目 where 条目号 = ?", (条目号,))
        连接.commit()
    finally:
        连接.close()


def 入口函数(样本参数: list, 仓根目录) -> int:
    """跑完全部夹具样本 ⇒ 退出码（有失败即 1）。"""
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="反馈看板样本-") as 临时目录:
        夹具根 = Path(临时目录)
        库件, 台账件 = 造夹具(夹具根)
        载荷 = 跑取数(库件, 台账件, 夹具根)
        资料组 = 找组(载荷, "未完成条目|%d" % 台账号)
        样本表.append(("台账关联 ⇒ 落「未完成条目|号」组且承接有效",
                 载荷["陈旧"] is False and 载荷["错误"] is None and 资料组 is not None
                 and 资料组["承接有效"] is True and 资料组["条数"] == 1
                 and len(载荷["条目"]) == 1 and 载荷["条目"][0]["判词"] == "债务"
                 and 载荷["条目"][0]["关闭提交"] == "未关闭"))
        样本表.append(("报告指纹与路径随条目返回",
                 载荷["条目"][0]["报告指纹"] == "a" * 16
                 and 载荷["条目"][0]["报告路径"] == "/tmp/report.md"))
        改判词(库件, "开工", 夹具开工号)
        载荷 = 跑取数(库件, 台账件, 夹具根)
        资料组 = 找组(载荷, "开工|%s" % 夹具开工号)
        样本表.append(("开工关联 ⇒ 落「开工|号」组且承接有效",
                 资料组 is not None and 资料组["承接有效"] is True
                 and 载荷["条目"][0]["承接任务"].startswith(夹具开工号)))
        改判词(库件, "未完成条目", str(缺件号))
        载荷 = 跑取数(库件, 台账件, 夹具根)
        资料组 = 找组(载荷, 取数.组_缺关联)
        样本表.append(("改关联到台账外号 ⇒ 掉「缺关联」且承接有效=假（映射随库实时变）",
                 资料组 is not None and 资料组["承接有效"] is False
                 and 载荷["条目"][0]["承接有效"] is False
                 and "未知" in 载荷["条目"][0]["核验"]))
        改判词(库件, "未完成条目", str(台账号))
        加条目(库件, 2, "未完成条目", str(台账号))
        载荷 = 跑取数(库件, 台账件, 夹具根)
        样本表.append(("增条目 ⇒ 组条数与总数实时增",
                 载荷["分页"]["总数"] == 2
                 and 找组(载荷, "未完成条目|%d" % 台账号)["条数"] == 2))
        删条目(库件, 2)
        载荷 = 跑取数(库件, 台账件, 夹具根)
        样本表.append(("删条目 ⇒ 组条数与总数实时回落",
                 载荷["分页"]["总数"] == 1
                 and 找组(载荷, "未完成条目|%d" % 台账号)["条数"] == 1))
        载荷 = 跑取数(夹具根 / "不存在.db", 台账件, 夹具根)
        样本表.append(("库件不存在 ⇒ 陈旧=真 · 错误非空 · 组空（读失败不报新鲜）",
                 载荷["陈旧"] is True and bool(载荷["错误"]) and not 载荷["组"]
                 and 载荷["分页"]["总数"] == 0))
        坏件 = 夹具根 / "坏件.db"
        坏件.write_bytes(b"not a sqlite database")
        载荷 = 跑取数(坏件, 台账件, 夹具根)
        样本表.append(("库件坏 ⇒ 陈旧=真 · 错误非空（读失败不报新鲜）",
                 载荷["陈旧"] is True and bool(载荷["错误"]) and not 载荷["组"]))
        载荷 = 跑取数(库件, 夹具根 / "无台账.json", 夹具根)
        样本表.append(("台账不在 ⇒ 陈旧=真（现量取不到不假新鲜）",
                 载荷["陈旧"] is True and bool(载荷["错误"])))
    失败 = [说明 for 说明, 通过 in 样本表 if not 通过]
    for 说明, 通过 in 样本表:
        print(("  ✓ " if 通过 else "  ✗ ") + 说明)
    print("样本 %d 条 · 通过 %d · 失败 %d" % (len(样本表), len(样本表) - len(失败), len(失败)))
    return 0 if not 失败 else 1
