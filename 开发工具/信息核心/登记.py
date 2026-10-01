# -*- coding: utf-8 -*-
"""登记 —— 往规则库的 `命名定义` 表登记新名 / 改自由文本两栏（**改命名规则的唯一写路径**）。

用法：
    python3 开发工具/信息核心/信息核心.py 登记 <名> [<名>…] [--语义 <一句话>]
    python3 开发工具/信息核心/信息核心.py 登记 --语义 <语义> [--唯一名 <文本>] [--现状 <文本>]

**为何要它**：名册住规则库（华哥 2026-09-29「全规则都在 db 里面。外部不留」）⇒ 登记不能再靠
改一份 json（库里是唯一存本，不再有源件）。写库走**生成物记账**那条路（`v1_task` 功能 = 5）
—— `v1_edit` 是文本替换，二进制件它改不了。

**语义**：默认「名即语义」（与旧名册的 txt 一行一名同口径）；一个名指多件事的，
用 `--语义` 写清楚，或改由「一个语义一行」的方式登记。

**第二种形态（`--唯一名` / `--现状`）—— 改自由文本两栏**：`命名定义` 的 `唯一名` /
`现状` 两栏是自由文本，原先只做 `(语义, 唯一名, 现状)` 的 `insert or replace`（三栏一起写死），
两栏改不动。现给 `登记` 加这两栏的**显式写口**：`--语义` 定位既有行（它是主键），
`--唯一名` / `--现状` 各只改一栏（不给的那栏保持原值）。**本口只改既有行，不新建** ——
新建走 `登记 <名>`。首个用例：枚举值名裁为 `真`/`假`（库 `规则` 表 `命名口径-8`）——
    python3 开发工具/信息核心/信息核心.py 登记 --语义 "null / true / false" \\
        --唯一名 "`空值` · `真` · `假`" --现状 "`空` · `逻辑真` · `逻辑假`"
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402
import 记规则  # noqa: E402  （复用它的参数解析 —— 不许写第二套）


def 解析(参数表: list) -> tuple:
    """⇒ `(名表, 语义, 唯一名, 现状)`。

    位置参数（首个 `--` 之前）= 名表；`--语义` / `--唯一名` / `--现状` 各吃一个值（值可带空格）。
    字段解析复用 `记规则.解析参数`（**不许写第二套**）；`--唯一名` / `--现状` 缺席时给 `None`
    （`None` = 不改那一栏，与「显式给空串」区分开）。
    """
    名表 = []
    for 一片 in 参数表:
        if 一片.startswith("--"):
            break
        名表.append(一片)
    字段表 = 记规则.解析参数(参数表)
    return 名表, 字段表.get("语义", ""), 字段表.get("唯一名"), 字段表.get("现状")


def 登记(名表: list, 语义: str = "", 唯一名=None, 现状=None) -> int:
    """登记新名；给 `--唯一名` / `--现状` 时改为**改自由文本两栏**（键 = `--语义`）⇒ 退出码。

    `--语义` 定位既有行（它是 `命名定义` 的主键），语义不在名册 ⇒ 拒（**只改既有行，不新建**）；
    只改给的栏，另一栏保持原值；两栏都没给 ⇒ 拒。
    """
    if 唯一名 is not None or 现状 is not None:
        语义 = (语义 or "").strip()
        if not 语义:
            print("改两栏要 `--语义 <语义>`（它是 `命名定义` 的主键）", file=sys.stderr)
            return 2
        连接 = sqlite3.connect(表定义.库路径(仓根))
        try:
            旧行 = 连接.execute(
                "select 唯一名, 现状 from 命名定义 where 语义 = ?", (语义,)).fetchone()
            if 旧行 is None:
                print("拒：`%s` 不在名册 —— 本口只改既有行；新建走 `登记 <名>`" % 语义,
                      file=sys.stderr)
                return 1
            唯一名 = 旧行[0] if 唯一名 is None else 唯一名
            现状 = 旧行[1] if 现状 is None else 现状
            连接.execute("update 命名定义 set 唯一名 = ?, 现状 = ? where 语义 = ?",
                       (唯一名, 现状, 语义))
            连接.commit()
        finally:
            连接.close()
        print("改两栏：%s ⇒ 唯一名 = %s · 现状 = %s" % (语义, 唯一名, 现状))
        return 0
    if not 名表:
        print("用法：信息核心.py 登记 <名> [<名>…] [--语义 <一句话>]", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        for 登记名 in 名表:
            连接.execute("insert or replace into 命名定义 values(?,?,?)",
                       (语义 or 登记名, 登记名, "（名即语义）"))
        连接.commit()
    finally:
        连接.close()
    print("登记 %d 个名：%s" % (len(名表), " · ".join(名表)))
    return 0
