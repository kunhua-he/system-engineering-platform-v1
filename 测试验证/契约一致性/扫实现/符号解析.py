# -*- coding: utf-8 -*-
"""符号解析 —— 值 / 符号解析（解析不出来一律 None —— 不许猜）。"""
from __future__ import annotations

import re

from .常量 import 生成物相对, 契约源相对, 契约源目录
from .小工具 import 配对
from .掩码 import 掩码


def 解整数(文本) -> object:
    if 文本 is None:
        return None
    文本 = 文本.strip()
    if re.fullmatch(r"\d+", 文本):
        return int(文本)
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", 文本):
        return int(文本, 16)
    匹配 = re.fullmatch(r"(\d+)\s*(<<|>>|\+|\-|\*|/|\||&)\s*(\d+)", 文本)
    if 匹配:
        左值, 运, 右值 = int(匹配.group(1)), 匹配.group(2), int(匹配.group(3))
        try:
            return {
                "<<": 左值 << 右值, ">>": 左值 >> 右值, "+": 左值 + 右值, "-": 左值 - 右值,
                "*": 左值 * 右值, "/": 左值 // 右值, "|": 左值 | 右值, "&": 左值 & 右值,
            }[运]
        except (ValueError, ZeroDivisionError):
            return None
    匹配 = re.fullmatch(r"(\d+)\s+as\s+\w+", 文本)
    if 匹配:
        return int(匹配.group(1))
    return None


def 解表达式(文本, 项表: dict) -> object:
    """把 `项表` 里的符号代入后求整数（例：`码 / 1000` + {码: 1001} → 1）。解不出 None。"""
    if 文本 is None:
        return None
    裸值 = 解整数(文本)
    if 裸值 is not None:
        return 裸值
    换 = 文本
    for 名 in sorted(项表, key=len, reverse=True):
        值 = 项表[名]
        if 值 is None:
            continue
        换 = re.sub(r"(?<![\w:])" + re.escape(名) + r"(?![\w:])", str(值), 换)
    return 解整数(换)


def 末段(文本: str) -> str:
    return 文本.strip().split("::")[-1].strip()


def 解构造器(文本: str, 符号表: dict = None, 本表: dict = None) -> object:
    """newtype 构造器 → 内层整数。**内层只认「整数字面量」或「本单元常量」**。

    为什么要有它：`契约声明` 新增 `#[repr(transparent)]` newtype 后，底座侧字段写成
    `v1_contract::类型标签::新建(0)` / `v1_contract::能力号::新建(0)`；扩展侧可能写 `0.into()`。
    认不出这类写法 ⇒ ③d1 由「通过」变「未判」（判据「按显式编号」的能力也被削弱）。
    口径：**认不出 = None（fail-closed）**，绝不当成「通过」——那是假绿，比未判更坏。

    **内层是符号时也要认**（2026-09-27 补，实测撞到）：扩展侧把它们写成
    `v1_contract::能力号::新建(能力号::词法分析)` / `v1_contract::类型标签::新建(类型标签_0005)`
    —— 内层是**符号**不是字面量。原先一律不认，后果是扩展那 7 条命令的
    `编号` / `返回类型` 全取不到 ⇒ ③c/③d1/③d2 **一条都比不了**（已判 0 项 ⇒ 报未判），
    而底座侧（内层是字面量 / 生成物常量）照判 ⇒ 缺陷只在扩展侧静默。
    现在内层**逐级解符号**（`符号表` / `本表`，即生成物与实现侧常量）；仍解不出才 None。
    这**不是放宽**：解的仍是**已登记的数**（生成物常量或本单元 `能力号` 表），不是猜。
    只认「内层是单个符号/字面量」：内层是复合表达式（`某值.取号值()` · `a + b`）一律不认。
    """
    if 文本 is None:
        return None
    文本 = 文本.strip()
    # `路径::类型名::新(<内层>)`
    匹配 = re.fullmatch(r"[\w:]+::新建\s*\(\s*(.+?)\s*\)", 文本)
    if 匹配:
        内 = 匹配.group(1)
        数 = 解整数(内)
        if 数 is not None:
            return 数
        if 符号表 is not None and 本表 is not None:
            return 解符号(内, 符号表, 本表)
        return None
    # `<整数字面量>.into()`（可带类型后缀：`0u32.into()` / `0_usize.into()`）
    匹配 = re.fullmatch(r"(\d+)\s*(?:[a-zA-Z]\w*)?\s*\.\s*into\s*\(\s*\)", 文本)
    if 匹配:
        return int(匹配.group(1))
    return None


def 解符号(文本, 符号表: dict, 本表: dict) -> object:
    """把 `类型标签_0005` / `v1_contract::声明数据::类型标签_0005` /
    `命令状态::错误` / `能力号::生成容器 as usize` / `v1_contract::类型标签::新建(0)` 解析成数。

    读法（顺序即优先级）：newtype 构造器 → 去 `as` → 全路径（含去掉 `v1_contract::` /
    `crate::` 前缀后的模块限定名）→ 末段 → 表达式代入。解不出返回 None（不许猜）。
    """
    if 文本 is None:
        return None
    文本 = 文本.strip()
    裸值 = 解构造器(文本, 符号表, 本表)
    if 裸值 is not None:
        return 裸值
    裸值 = 解整数(文本)
    if 裸值 is not None:
        return 裸值
    匹配 = re.fullmatch(r"(.+?)\s+as\s+\w+", 文本)
    if 匹配:
        文本 = 匹配.group(1).strip()
    # 先按**全路径**（含模块限定名）找，再退回**末段** —— 同名的常量分属不同 `pub mod` 时，
    # 只有全路径能消歧（`槽标志::空槽标志` 与 `常量排布::无值` 是两个数）。
    候选 = [文本]
    for 前 in ("v1_contract::", "crate::"):
        if 文本.startswith(前):
            候选.append(文本[len(前):])
    for 候 in 候选:
        if 候 in 本表:
            return 本表[候]
        if 候 in 符号表:
            return 符号表[候]
    名 = 末段(文本)
    if 名 in 本表:
        return 本表[名]
    if 名 in 符号表:
        return 符号表[名]
    return 解表达式(文本, {**符号表, **本表})


def 解常量值(值文: str) -> object:
    """`pub const` 右值 → 数。**整数字面量与号空间 newtype 两种都认**，其余 None。

    为什么要有它（2026-09-27 补，实测撞到）：号空间 newtype 落地后，生成器改出
    `pub const 类型标签_0005: v1_contract::类型标签 = v1_contract::类型标签::新建(5);`
    —— 右值不再是裸整数。本函数原先只走 `解整数` ⇒ 生成物里那一批 `类型标签_N` /
    `错误码_N` **整批丢出符号表**（89 条里一条都不含它们），实现侧引用 `类型标签_0005`
    当场解不出 ⇒ ③e / ③c / ③d1 由「通过」变「未判」。
    走 `解符号`（同一套口径，不另写第二份）：newtype 构造器 → 整数字面量；解不出仍 None。
    """
    return 解符号(值文, {}, {})


def 建符号表(件表: dict, 掩表: dict = None) -> dict:
    """从生成物 + `契约声明/src/` 下**全部** `.rs` 建「符号 → 数」引用表（只读，不计入实现面）。

    **扫描面是符号不是文件**：早先只读 `生成物相对` 与 `契约源相对` 两个写死的路径，
    `契约声明/src/lib.rs` 一拆成路由（`mod` + `pub use`），搬进子件的 `槽标志` / `命令状态` /
    `通知返回` / `常量排布` 就静默丢出表。改成扫 `契约源目录` 下全部 `.rs`（含子目录）⇒
    下次再搬也不丢（同一类病：坏了没人知道）。
    """
    表 = {}
    掩表 = 掩表 or {}
    for 键 in sorted(件表):
        if not (键.startswith(契约源目录) and 键.endswith(".rs")):
            continue
        文 = 件表.get(键)
        if 文 is None:
            continue
        掩 = 掩表.get(键) or 掩码(文)
        # `pub const <名>: <t> = <整数字面量>;`（顶层或缩进都认；`pub const fn` 不匹配）
        for 匹配 in re.finditer(
            r"(?m)^\s*pub\s+const\s+([^\s:]+)\s*:\s*[^=;]*?=\s*([^;]+);", 掩
        ):
            裸值 = 解常量值(匹配.group(2))
            if 裸值 is not None:
                表[匹配.group(1)] = 裸值
        # `pub mod <M> { … pub const <名>: <t> = <整数字面量>; … }`
        # 同时收**模块限定名**（`M::名`）与**末段名**（`名`）两种键。
        for mm in re.finditer(r"pub\s+mod\s+([^\s{]+)\s*\{", 掩):
            止 = 配对(掩, mm.end() - 1)
            if 止 < 0:
                continue
            模 = mm.group(1)
            for 常量配 in re.finditer(
                r"pub\s+const\s+([^\s:]+)\s*:\s*[^=;]*?=\s*([^;]+);", 掩[mm.end() : 止]
            ):
                裸值 = 解常量值(常量配.group(2))
                if 裸值 is not None:
                    表[常量配.group(1)] = 裸值
                    表[f"{模}::{常量配.group(1)}"] = 裸值
        # `pub use <路径>::<原名> as <别名>;`
        for 匹配 in re.finditer(r"pub\s+use\s+([^\s;]+?)\s+as\s+([^\s;]+)\s*;", 掩):
            原名 = 匹配.group(1).split("::")[-1]
            if 原名 in 表:
                表[匹配.group(2)] = 表[原名]
    return 表
