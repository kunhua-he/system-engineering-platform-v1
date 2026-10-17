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
    落点 = (字段表.get("落点") or "").strip()
    验证命令 = (字段表.get("验证命令") or "").strip()
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        已有 = 连接.execute("select 1 from 未完成 where 号 = ?", (台账号,)).fetchone()
        连接.execute("insert or replace into 未完成 values(?,?,?,?)",
                   (台账号, 缺什么, 落点 or None, 验证命令 or None))
        连接.commit()
    finally:
        连接.close()
    print(f"记未完成：{'改' if 已有 else '增'} 第 {台账号} 行 · {缺什么[:40]}")
    print(记账提醒)
    return 0


def 删一行(台账号: int) -> int:
    """把一行从 `未完成` 表删掉（修好了就删，台账只留未完成的）⇒ 退出码。"""
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        已有 = 连接.execute("select 1 from 未完成 where 号 = ?", (台账号,)).fetchone()
        if not 已有:
            print(f"拒：`未完成` 表里没有第 {台账号} 行（先 `--列` 看现行号）。", file=sys.stderr)
            return 2
        连接.execute("delete from 未完成 where 号 = ?", (台账号,))
        连接.commit()
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
