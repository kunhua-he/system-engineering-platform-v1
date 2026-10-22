# -*- coding: utf-8 -*-
"""记未完成 —— 往规则库的 `未完成` 表记 / 改写 / 删掉**一行**（一行一债）。

用法：
    python3 开发工具/信息核心/信息核心.py 记未完成 --号 363 --缺什么 … [--落点 …] [--验证命令 …]
    python3 开发工具/信息核心/信息核心.py 记未完成 --删 --号 363
    python3 开发工具/信息核心/信息核心.py 记未完成 --列 [--号 363]

**为何要它**（2026-10-13 裁）：`未完成` 表原先的源是 `开发工具/信息核心/未完成.json` ——
那份 JSON 是平台最后一个**文件式状态**：一个非法转义（反斜杠加竖线）就整份读不动、
`建库` 直接崩；而它是 pretty-print 多行块 ⇒ 删一行要按字面匹配六行。裁的口径与
`条款` / `命名登记` 一致：**库即存本**（`表定义.py` 的 `源表` 那一段的原话），改动只走本命令。

四栏与原先的 JSON 逐字对齐：`号` · `缺什么` · `落点` · `验证命令`（后两栏可空）。
**做完即删**：一条债务修好了就把那一行删掉（`--删 --号 N`）—— 台账只留未完成的。

**保真值**（2026-10-22 第三轮维修）：后两栏的「**显式空串**」与「**没给**」是两件事 ——
`--落点 ""` = 把这栏**清成空串**，不给 `--落点` = 更新时保留原值、新增时留 NULL。旧写法 `落点 or None` 把两者
混成一个 NULL ⇒ 腿侧的「清空」在合主干重放时被静默丢掉（`合主干源库重放` 逐栏比对随之假绿）。
写入走**单一事务**（`begin immediate` + upsert）：读「有没有这行」与写在同一事务里，
同一号的读改写串行执行，缺参字段不会覆盖另一事务已提交的值。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402
import 记规则  # noqa: E402  （复用它的参数解析 —— 不许写第二套）

用法文本 = ("用法：信息核心.py 记未完成 --号 <整数> --缺什么 <散文> [--落点 <件::符号>] "
        "[--验证命令 <命令>] ｜ --删 --号 <整数> ｜ --列 [--号 <整数>]")

记账提醒 = ("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
        "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")


def _栏值(字段表: dict, 栏名: str):
    """⇒ 该栏本次要落的值：**显式给了（含空串）** ⇒ 原值；**没给** ⇒ `None`（该栏留 NULL）。

    判据是「键在不在 `字段表`」，不是「值真不真」—— `--落点 ""` 进来就是空串，那是**清栏**。
    """
    if 栏名 not in 字段表:
        return None
    return (字段表.get(栏名) or "").strip()


def 记未完成(字段表: dict) -> int:
    """按 `号` 就地写一行 / 删一行 / 列出来 ⇒ 退出码。"""
    号原文 = (字段表.get("号") or "").strip()
    if "列" in 字段表:
        return 列台账(号原文)
    if not 号原文.isdigit():
        print(用法文本, file=sys.stderr)
        return 2
    台账号 = int(号原文)
    if "删" in 字段表:
        return 删一行(台账号)
    缺什么 = (字段表.get("缺什么") or "").strip()
    if not 缺什么:
        print(f"拒：`--号 {台账号}` 给了却没给 `--缺什么` —— 台账一行必须说清缺什么。",
              file=sys.stderr)
        return 2
    落点 = _栏值(字段表, "落点")
    验证命令 = _栏值(字段表, "验证命令")
    连接 = sqlite3.connect(表定义.库路径(仓根), timeout=10)
    try:
        连接.execute("begin immediate")     # 读改写同一事务：并发两写不互相覆盖
        已有 = 连接.execute("select 落点, 验证命令 from 未完成 where 号 = ?", (台账号,)).fetchone()
        if 已有 is not None:
            if "落点" not in 字段表:
                落点 = 已有[0]
            if "验证命令" not in 字段表:
                验证命令 = 已有[1]
        连接.execute("insert into 未完成(号, 缺什么, 落点, 验证命令) values(?,?,?,?) "
                   "on conflict(号) do update set 缺什么 = excluded.缺什么, "
                   "落点 = excluded.落点, 验证命令 = excluded.验证命令",
                   (台账号, 缺什么, 落点, 验证命令))
        连接.commit()
    except sqlite3.Error as 错误:
        连接.rollback()
        print(f"拒：`未完成` 第 {台账号} 行写入失败（已回滚，库未变）：{错误}", file=sys.stderr)
        return 1
    finally:
        连接.close()
    print(f"记未完成：{'改' if 已有 else '增'} 第 {台账号} 行 · {缺什么[:40]}")
    print(记账提醒)
    return 0


def 删一行(台账号: int) -> int:
    """把一行从 `未完成` 表删掉（修好了就删，台账只留未完成的）⇒ 退出码。"""
    连接 = sqlite3.connect(表定义.库路径(仓根), timeout=10)
    try:
        连接.execute("begin immediate")
        已有 = 连接.execute("select 1 from 未完成 where 号 = ?", (台账号,)).fetchone()
        if not 已有:
            连接.rollback()
            print(f"拒：`未完成` 表里没有第 {台账号} 行（先 `--列` 看现行号）。", file=sys.stderr)
            return 2
        连接.execute("delete from 未完成 where 号 = ?", (台账号,))
        连接.commit()
    except sqlite3.Error as 错误:
        连接.rollback()
        print(f"拒：`未完成` 第 {台账号} 行删除失败（已回滚，库未变）：{错误}", file=sys.stderr)
        return 1
    finally:
        连接.close()
    print(f"记未完成：删第 {台账号} 行")
    print(记账提醒)
    return 0


def 列台账(号原文: str) -> int:
    """列台账（给了 `--号` 只列那一行）—— **只读**，不写库。"""
    连接 = sqlite3.connect("file:%s?mode=ro" % 表定义.库路径(仓根), uri=True)
    try:
        if 号原文:
            if not 号原文.isdigit():
                print(用法文本, file=sys.stderr)
                return 2
            行表 = 连接.execute(
                "select 号, 缺什么, 落点, 验证命令 from 未完成 where 号 = ?",
                (int(号原文),)).fetchall()
        else:
            行表 = 连接.execute(
                "select 号, 缺什么, 落点, 验证命令 from 未完成 order by 号").fetchall()
    finally:
        连接.close()
    for 台账号, 缺什么, 落点, 验证命令 in 行表:
        print(f"[{台账号}] {缺什么[:90]}")
        if 落点:
            print(f"      落点：{落点}")
        if 验证命令:
            print(f"      验证：{验证命令}")
    print(f"── 共 {len(行表)} 行 ──")
    return 0
