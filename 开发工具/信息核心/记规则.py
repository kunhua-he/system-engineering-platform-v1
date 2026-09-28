# -*- coding: utf-8 -*-
"""记规则 —— 往规则库的 `规则` 表记一条**规则 / 裁决**（一次裁决一条的仓内写路径）。

用法：
    python3 开发工具/信息核心/信息核心.py 记规则 --类 <类名> --名 <一句话> --内容 <散文> [--依据 <落点>]

**为何要它**：`规则` 表是「全项目规则的唯一落点」（宪法 · 层序 · 开发规范 · 判据口径 …），
但 md 删净之后它**没有写入路径** —— 手写 SQL 会绕过 `v1_edit` 的账本，那是已关掉的坏路。
本命令就是那条正路：写库 + 记账走 `v1_task` 功能 = 5（库是二进制，`v1_edit` 改不了它）。

`编号` 由本命令按类自动给：`<类>-<序号>`，序号 = 该类现有的最大序号 + 1（同类的旧编号不复用）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402


def 解析参数(参数表: list) -> dict:
    """`--类 X --名 Y --内容 Z` ⇒ `{"类": "X", "名": "Y", "内容": "Z"}`（值可以带空格）。"""
    字段表 = {}
    字段键 = ""
    for 一片 in 参数表:
        if 一片.startswith("--"):
            字段键 = 一片[2:]
            字段表[字段键] = ""
        elif 字段键:
            字段表[字段键] = (字段表[字段键] + " " + 一片).strip()
    return 字段表


def 取新编号(连接, 类名: str) -> str:
    """`<类>-<序号>` —— 序号 = 该类现有的最大 + 1（按编号尾段取整数）。"""
    编号表 = 连接.execute(
        "select 编号 from 规则 where 类 = ?", (类名,)).fetchall()
    最大序号 = 0
    for (编号,) in 编号表:
        尾巴 = 编号.rsplit("-", 1)[-1]
        if 尾巴.isdigit():
            最大序号 = max(最大序号, int(尾巴))
    return f"{类名}-{最大序号 + 1}"


def 记规则(字段表: dict) -> int:
    """写一条规则进 `规则` 表 ⇒ 退出码。"""
    类名 = (字段表.get("类") or "").strip()
    规则名 = (字段表.get("名") or "").strip()
    内容 = (字段表.get("内容") or "").strip()
    依据 = (字段表.get("依据") or "").strip()
    if not 类名 or not 规则名 or not 内容:
        print("用法：信息核心.py 记规则 --类 <类名> --名 <一句话> --内容 <散文> [--依据 <落点>]",
              file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        编号 = 取新编号(连接, 类名)
        连接.execute("insert or replace into 规则 values(?,?,?,?,?)", (编号, 类名, 规则名, 内容, 依据))
        连接.commit()
    finally:
        连接.close()
    print(f"记规则：{编号} · {类名} · {规则名}")
    return 0
