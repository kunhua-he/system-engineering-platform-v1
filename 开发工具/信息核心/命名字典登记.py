# -*- coding: utf-8 -*-
"""命名字典登记 —— 往规则库的**命名两表**写登记（`命名登记` · `命名字典`）。

用法：
    python3 开发工具/信息核心/信息核心.py 命名字典登记 --名字 X --语义 Y --模式 Z --来源 W [--状态 V]
    python3 开发工具/信息核心/信息核心.py 命名字典登记 --名字 X --分组 G --说明 S

**为何要它**：`命名登记` 是「名字 → 语义 · 模式 · 来源 · 状态」的唯一登记面，`命名字典` 是
「核心词 → 分组 · 说明」的存本。两表都带 CHECK 约束（`模式` / `来源` / `状态`），手写 SQL
写错值要到运行时才炸 ⇒ 本模块把校验前置：非法值**报错并返回非 0**，不静默吞。

`解析` 复用 `记规则.解析参数`（值可带空格），**不许写第二套**。
写库 + 记账走 `v1_task` 功能 = 6（库是二进制**源件**，`v1_edit` 改不了它）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402
import 记规则  # noqa: E402  （复用它的参数解析 —— 不许写第二套）

合法模式 = ("动作+对象", "对象+说明")
合法来源 = ("核心字典", "新定义")
合法状态 = ("合格", "待改名")

用法文本 = ("用法：信息核心.py 命名字典登记 --名字 X --语义 Y --模式 Z --来源 W [--状态 V]"
          " ／ 命名字典登记 --名字 X --分组 G --说明 S")


def 解析(参数表: list) -> dict:
    """`--名字 X --语义 Y --模式 Z --来源 W [--状态 V]` ⇒ 字段表（值可带空格）。

    走 `记规则.解析参数`（照抄那条口径，不写第二套）。返回的字段表**键名即形参名**，
    可直接喂给 `登记名字` / `登记核心词`。
    """
    return 记规则.解析参数(参数表)


def 登记名字(名字: str, 语义: str, 模式: str, 来源: str, 状态: str = "合格") -> int:
    """往 `命名登记` 表 upsert 一行（主键 `名字`）⇒ 退出码（0 成功 · 2 参数非法）。

    `模式` / `来源` / `状态` 各自只接受枚举里的值（与库里的 CHECK 一致），非法即拒。
    upsert 用 `on conflict do update` ⇒ **保住**已有行的 `出现次数` 与 `创建时间`
    （`insert or replace` 会把整行删了重插，计数归零、时间刷新 —— 那是坏的）。
    """
    名字 = (名字 or "").strip()
    语义 = (语义 or "").strip()
    模式 = (模式 or "").strip()
    来源 = (来源 or "").strip()
    状态 = (状态 or "合格").strip()
    if not 名字 or not 语义:
        print("拒：`--名字` 与 `--语义` 都不能为空。", file=sys.stderr)
        return 2
    if 模式 not in 合法模式:
        print(f"拒：`--模式 {模式}` 非法 —— 只接受 {' / '.join(合法模式)}。", file=sys.stderr)
        return 2
    if 来源 not in 合法来源:
        print(f"拒：`--来源 {来源}` 非法 —— 只接受 {' / '.join(合法来源)}。", file=sys.stderr)
        return 2
    if 状态 not in 合法状态:
        print(f"拒：`--状态 {状态}` 非法 —— 只接受 {' / '.join(合法状态)}。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        连接.execute(
            "insert into 命名登记(名字, 语义, 模式, 来源, 状态) values(?,?,?,?,?) "
            "on conflict(名字) do update set 语义=excluded.语义, 模式=excluded.模式, "
            "来源=excluded.来源, 状态=excluded.状态",
            (名字, 语义, 模式, 来源, 状态))
        连接.commit()
    finally:
        连接.close()
    print(f"命名登记：{名字} · 语义={语义} · 模式={模式} · 来源={来源} · 状态={状态}")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0


def 登记核心词(名字: str, 分组: str, 说明: str) -> int:
    """往 `命名字典` 表 upsert 一行（唯一键 `名字`）⇒ 退出码（0 成功 · 2 参数非法）。

    三个字段都非空；upsert 保住 `编号` 与 `创建时间`（只更新 `分组` / `说明`）。
    """
    名字 = (名字 or "").strip()
    分组 = (分组 or "").strip()
    说明 = (说明 or "").strip()
    if not 名字 or not 分组 or not 说明:
        print("拒：`--名字` / `--分组` / `--说明` 三者都不能为空。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        连接.execute(
            "insert into 命名字典(名字, 分组, 说明) values(?,?,?) "
            "on conflict(名字) do update set 分组=excluded.分组, 说明=excluded.说明",
            (名字, 分组, 说明))
        连接.commit()
    finally:
        连接.close()
    print(f"命名字典：{名字} · 分组={分组} · 说明={说明}")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0


def 删名字(名字: str) -> int:
    """把一行从 `命名登记`（连带派生库 `命名出现`）删掉 ⇒ 退出码（0 成功 · 2 参数非法）。

    用途：一个名已从代码里改净、登记成了**陈旧行**（`落库` 只新增、不会删）⇒ 用本口清出。
    不删会一直计在 `待改名` 里。

    ★ 2026-10-07：`命名出现` 已搬进**派生库**（非版本，见 `表定义.派生表`）⇒ 两处分开删：
    规则库删 `命名登记`，派生库删 `命名出现`（派生库 / 表不在 ⇒ 出现行数记 0，不报错）。
    """
    名字 = (名字 or "").strip()
    if not 名字:
        print("拒：`--删` 要给 `--名字`。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        登记行数 = 连接.execute("delete from 命名登记 where 名字 = ?", (名字,)).rowcount
        连接.commit()
    finally:
        连接.close()
    出现行数 = 0
    派生库件 = 表定义.派生库路径(仓根)
    if 派生库件.is_file():
        派生连接 = sqlite3.connect(str(派生库件))
        try:
            有表 = 派生连接.execute(
                "select 1 from sqlite_master where type='table' and name='命名出现'").fetchone()
            if 有表:
                出现行数 = 派生连接.execute(
                    "delete from 命名出现 where 名字 = ?", (名字,)).rowcount
                派生连接.commit()
        finally:
            派生连接.close()
    print(f"命名登记：删 {名字}（登记 {登记行数} 行 · 命名出现 {出现行数} 行）")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0


def 记例外(名字: str, 说明: str) -> int:
    """把一个名登记进 `命名例外`（语言 / 协议 / 工具强加，或经裁定的豁免）⇒ 退出码。

    用途：一个名**不该改**（图标键逐字照抄参考图 · 外部协议键 · 局部变量改了反而难读）⇒
    进例外表；`落库` 会跳过例外名（不进 `待改名`）。**理由必填** —— 例外是裁定，不是垃圾桶。
    """
    名字, 说明 = (名字 or "").strip(), (说明 or "").strip()
    if not 名字 or not 说明:
        print("拒：`--例外` 要给 `--名字` 与 `--理由`。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        连接.execute("insert or replace into 命名例外(名字, 说明) values(?,?)", (名字, 说明))
        连接.execute("delete from 命名登记 where 名字 = ?", (名字,))
        连接.commit()
    finally:
        连接.close()
    print(f"命名例外：{名字} · 理由={说明}")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0


def 登记(字段表: dict) -> int:
    """按字段表分派：`--删` ⇒ `删名字`；`--例外` ⇒ `记例外`；有 `--分组`/`--说明` ⇒ `登记核心词`；否则 ⇒ `登记名字`。"""
    if "删" in 字段表:
        return 删名字(字段表.get("名字", ""))
    if "例外" in 字段表:
        return 记例外(字段表.get("名字", ""), 字段表.get("理由", ""))
    if 字段表.get("分组") or 字段表.get("说明"):
        return 登记核心词(字段表.get("名字", ""), 字段表.get("分组", ""),
                       字段表.get("说明", ""))
    return 登记名字(字段表.get("名字", ""), 字段表.get("语义", ""), 字段表.get("模式", ""),
                  字段表.get("来源", ""), 字段表.get("状态") or "合格")


def 入口函数(命令行参数: list) -> int:
    """命令行入口：解析 + 分派 ⇒ 退出码（由 `信息核心.py` 路由调用，本件不自带 `__main__`）。"""
    字段表 = 解析(命令行参数)
    if not 字段表.get("名字"):
        print(用法文本, file=sys.stderr)
        return 2
    return 登记(字段表)
