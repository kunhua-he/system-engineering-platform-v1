# -*- coding: utf-8 -*-
"""批量登记 —— 一次把多个名写进库 `命名登记`（走仓内正式命令，绝不手写 SQL）。

用法（经唯一壳 `信息核心.py`）：
    python3 开发工具/信息核心/信息核心.py 登记 --批 <表文件> [--干跑] [--不落库]
    python3 开发工具/信息核心/信息核心.py 登记 --批 -            # 从标准输入读批表

**批表两种**（`--批` 给的那个文件）：
  · JSON —— 顶层数组；每条可以是对象 `{"名字":…,"语义":…,"模式":…,"来源":…}`、
    数组 `["名字","语义","模式","来源"]`、或一行字符串；也可用 `{"名单":[…]}` 包一层。
  · 行式 —— 每行 `名字<TAB>语义<TAB>模式<TAB>来源`（缺列按空补；`#` 开头与空行跳过）。

**为什么要有它**（多路代理实测）：新建一个件时**所有绑定名**（形参 · 局部 · 函数名 ·
JS 的 `const` / 解构名）都要在库 `命名登记`（状态=合格），否则 `v1_edit` 写入前整批拒。
逐名一次子进程：一条腿为 5 个新件登记 98 次、另一条为 39 个名登记 39 次还被 5 秒硬顶杀掉
—— 纯机械往返。本口一次做完。

**三条口径**：
  · **幂等** —— 同一个名重复登记不报错、不产生重复行、**不改已有合格行的语义**（已存在 ⇒ 跳过）。
  · **一次给全** —— 成功登记 N / 已存在跳过 M / 需改名（禁止形状）逐条列名字与理由，
    并给「可登记 / 需改名」两栏，调用方不必逐条试。
  · **部分成功** —— 逐行判，拒一个不影响其余（如实回执，不整批回滚）。

规则（禁止形状 · 模式 · 语义）**只此一份**：`代码地图.查名` 判形状与状态、
`命名字典登记` 给模式 / 来源枚举 —— 本件不抄第二套。库是二进制**源件**，
`v1_edit` 改不了它，写库 + 记账走 `v1_task` 功能 = 6。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(仓根 / "开发工具"))

import 表定义  # noqa: E402
import 命名字典登记  # noqa: E402  —— 合法模式 / 合法来源 / 合法状态 只此一份

用法文本 = ("用法：信息核心.py 登记 --批 <表文件> [--干跑] [--不落库]\n"
          "  `--批 -` 从标准输入读；表文件 = JSON 或每行 `名字<TAB>语义<TAB>模式<TAB>来源`。")

# 回执里每栏最多列几个名字（成百上千个时不全打，另行列总数）。
上限条数 = 100
# 批表字段的规范顺序（数组形 / 行式按位对齐）。
字段顺序 = ("名字", "语义", "模式", "来源", "状态")


class 批表错误(Exception):
    """批表读不动 / 形状不对 —— 参数面失败（退出码 2）。"""


def 取查名():
    """惰性取命名口径主人（`代码地图.查名`）—— 判形状与状态只此一份。"""
    from 代码地图 import 查名 as 查名模块

    return 查名模块


def 拆批表行(源码行: str) -> dict:
    """一行文本 ⇒ 字段表：先按 TAB 分，只有一段再按空白分；缺列按空补。"""
    段表 = 源码行.split("\t")
    if len(段表) == 1:
        段表 = 源码行.split()
    return {键名: (段表[序号].strip() if 序号 < len(段表) else "")
            for 序号, 键名 in enumerate(字段顺序)}


def 拆批表条目(条目值) -> dict:
    """一条批表条目 ⇒ 字段表：对象 / 数组 / 字符串三形都收（别的形状 ⇒ 空表 ⇒ 判空名拒）。"""
    if isinstance(条目值, dict):
        return {str(键名): 值 for 键名, 值 in 条目值.items()}
    if isinstance(条目值, (list, tuple)):
        return {键名: (条目值[序号] if 序号 < len(条目值) else "")
                for 序号, 键名 in enumerate(字段顺序)}
    if isinstance(条目值, str):
        return 拆批表行(条目值)
    return {}


def 解析批表(批表文本: str) -> list:
    """批表原文 ⇒ 字段表列表。先试 JSON；解不动 ⇒ 退到行式（TAB / 空白分隔）。"""
    批表文本 = (批表文本 or "").lstrip("\ufeff")
    if not 批表文本.strip():
        return []
    try:
        顶层值 = json.loads(批表文本)
    except ValueError:
        顶层值 = None
    if 顶层值 is not None:
        if isinstance(顶层值, dict):
            顶层值 = 顶层值.get("名单") or 顶层值.get("行") or []
        if not isinstance(顶层值, list):
            raise 批表错误("JSON 顶层要是数组，或含 `名单` / `行` 数组的对象")
        return [拆批表条目(条目值) for 条目值 in 顶层值]
    行表 = []
    for 源码行 in 批表文本.splitlines():
        源码行 = 源码行.strip()
        if not 源码行 or 源码行.startswith("#"):
            continue
        行表.append(拆批表行(源码行))
    return 行表


def 读批表文本(表文件: str) -> str:
    """读批表：`-` / 空 ⇒ 标准输入；否则仓内相对或绝对路径。读不动 ⇒ `批表错误`。"""
    表文件 = (表文件 or "").strip()
    if 表文件 in ("", "-"):
        return sys.stdin.read()
    件路径 = Path(表文件)
    if not 件路径.is_absolute():
        件路径 = 仓根 / 表文件
    if not 件路径.is_file():
        raise 批表错误("批表文件不在：%s" % 件路径)
    try:
        return 件路径.read_text(encoding="utf-8", errors="replace")
    except OSError as 读不动原因:
        raise 批表错误("批表文件读不动：%s" % 读不动原因) from 读不动原因


def 读判据名单(连接) -> tuple:
    """⇒ `(泛名表, 动作词表)` —— 两张判据名单的主人都是库（本件不写死字面量）。"""
    泛名表 = {数据行[0] for 数据行 in 连接.execute("select 名字 from 命名泛名")}
    动作词表 = {数据行[0] for 数据行 in 连接.execute(
        "select 名字 from 命名字典 where 分组='动作'")}
    return 泛名表, 动作词表


def 判批表行(字段表: dict, 泛名表: set, 动作词表: set, 例外集: set) -> tuple:
    """一行 ⇒ `(归类, 结果条)`；归类 ∈ 登记 / 跳过 / 拒绝。

    `命名例外`（外部强加）里的名 ⇒ **跳过**（豁免优先，不报成需改名）；
    落四类禁止形状（单汉字名 · 泛名 · 序数代称 · 西文单字母）⇒ 拒绝并给理由；
    模式 / 来源给了但不在枚举里 ⇒ 拒绝；其余 ⇒ 可登记（缺的语义 / 模式由 `判状态` 补）。
    """
    查名模块 = 取查名()
    名字 = str(字段表.get("名字") or "").strip()
    if not 名字:
        return "拒绝", {"名字": "", "理由": "名字为空"}
    if 名字 in 例外集:
        return "跳过", {"名字": 名字, "理由": "已在命名例外（外部强加）"}
    形状 = 查名模块.判禁止形状(名字, 泛名表)
    if 形状:
        return "拒绝", {"名字": 名字, "理由": "落禁止形状「%s」" % 形状}
    _, 判模式, 判语义 = 查名模块.判状态(名字, 泛名表, 动作词表)
    给定模式 = str(字段表.get("模式") or "").strip()
    给定来源 = str(字段表.get("来源") or "").strip()
    给定语义 = str(字段表.get("语义") or "").strip()
    if 给定模式 and 给定模式 not in 命名字典登记.合法模式:
        return "拒绝", {"名字": 名字,
                     "理由": "模式非法「%s」（只接受 %s）" % (给定模式, " / ".join(命名字典登记.合法模式))}
    if 给定来源 and 给定来源 not in 命名字典登记.合法来源:
        return "拒绝", {"名字": 名字,
                     "理由": "来源非法「%s」（只接受 %s）" % (给定来源, " / ".join(命名字典登记.合法来源))}
    return "登记", {"名字": 名字, "语义": 给定语义 or 判语义,
                 "模式": 给定模式 or 判模式, "来源": 给定来源 or "新定义", "状态": "合格"}


def _写新名(库件, 待写: list) -> None:
    """把新名一次写进 `命名登记`（`insert or ignore`：**绝不覆盖**已有行的语义）。"""
    连接 = sqlite3.connect(str(库件))
    try:
        连接.executemany(
            "insert or ignore into 命名登记(名字, 语义, 模式, 来源, 状态) values(?,?,?,?,?)",
            [(结果条["名字"], 结果条["语义"], 结果条["模式"], 结果条["来源"], 结果条["状态"])
             for 结果条 in 待写])
        连接.commit()
    finally:
        连接.close()


def _列名字栏(行表: list, 标题: str, 名字表: list) -> None:
    """拼一栏名字（有界：超 `上限条数` 只列前若干，另报总数）。"""
    if not 名字表:
        return
    行表.append("【%s】%d 个" % (标题, len(名字表)))
    for 展示条 in 名字表[:上限条数]:
        if isinstance(展示条, tuple):
            行表.append("  「%s」  —— %s" % 展示条)
        else:
            行表.append("  %s" % 展示条)
    if len(名字表) > 上限条数:
        行表.append("  …（还有 %d 个未列出）" % (len(名字表) - 上限条数))


def 批量登记(行表: list, 落库: bool = True, 干跑: bool = False) -> int:
    """跑一批登记 ⇒ 退出码（0 全成 · 4 部分成功 · 1 全拒 · 2 前置不满足）。

    写前先读一遍 `命名登记` / `命名例外` 定「已存在」，写用 `insert or ignore` ⇒ 幂等。
    落库（默认）走 `落库.落库`（判据 55 名册新鲜度要求：新名进 `命名登记` 且名册跟上现场）。
    """
    库件 = 表定义.库路径(仓根)
    if not 库件.is_file():
        print("批量登记跑不动：规则库不在：%s" % 库件, file=sys.stderr)
        return 2
    连接 = sqlite3.connect(str(库件))
    try:
        已登记 = {数据行[0] for 数据行 in 连接.execute("select 名字 from 命名登记")}
        例外 = {数据行[0] for 数据行 in 连接.execute("select 名字 from 命名例外")}
        泛名表, 动作词表 = 读判据名单(连接)
    finally:
        连接.close()
    待写, 已存在, 需改名, 批内重复 = [], [], [], []
    见过 = set()
    for 字段表 in 行表:
        归类, 结果条 = 判批表行(字段表, 泛名表, 动作词表, 例外)
        名字 = 结果条["名字"]
        if 归类 == "拒绝":
            需改名.append((名字 or "（空）", 结果条["理由"]))
            continue
        if 名字 in 见过:
            批内重复.append(名字)
            continue
        见过.add(名字)
        if 归类 == "跳过" or 名字 in 已登记:
            已存在.append((名字, 结果条.get("理由") or "已在命名登记"))
            continue
        待写.append(结果条)
    if 待写 and not 干跑:
        _写新名(库件, 待写)
    写入行数 = len(待写)
    落库读数 = ""
    if 落库 and not 干跑:
        try:
            import 落库 as 落库模块
            读数 = 落库模块.落库(仓根)
            落库读数 = ("落库：扫描出现 %d · 新增 %d · 其中待改名 %d"
                     % (读数["扫描出现"], 读数["新增"], 读数["其中待改名"]))
        except Exception as 落库原因:  # 落库失败不吞掉已登记的名，只如实报
            落库读数 = "落库没跑成：%s" % 落库原因
    行表输出 = ["批量登记%s：收到 %d 行 · 登记 %d · 已存在跳过 %d · 需改名 %d · 批内重复 %d"
             % ("（干跑，未写库）" if 干跑 else "", len(行表), 写入行数,
                len(已存在), len(需改名), len(批内重复))]
    _列名字栏(行表输出, "可登记", [结果条["名字"] for 结果条 in 待写])
    _列名字栏(行表输出, "需改名", 需改名)
    _列名字栏(行表输出, "已存在跳过", 已存在)
    _列名字栏(行表输出, "批内重复", 批内重复)
    if 落库读数:
        行表输出.append(落库读数)
    if not 干跑 and 写入行数:
        行表输出.append("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
                    "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    print("\n".join(行表输出))
    if 需改名 and 写入行数 == 0 and not 已存在 and not 批内重复:
        return 1
    if 需改名:
        return 4
    return 0


def 入口函数(字段表: dict) -> int:
    """命令行入口（由 `命名字典登记.入口函数` 路由调用，本件不自带 `__main__`）。"""
    try:
        行表 = 解析批表(读批表文本(字段表.get("批")))
    except 批表错误 as 批表原因:
        print("批量登记：%s" % 批表原因, file=sys.stderr)
        return 2
    if not 行表:
        print("批量登记：批表里没有可登记的行（空表 / 全注释）。", file=sys.stderr)
        return 2
    return 批量登记(行表, 落库=("不落库" not in 字段表), 干跑=("干跑" in 字段表))
