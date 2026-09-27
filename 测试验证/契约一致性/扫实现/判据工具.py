# -*- coding: utf-8 -*-
"""判据工具 —— `记判据` 与比对用的小解析（本表 · 编号 · 可抛错误码 · 落点）。"""
from __future__ import annotations

import re

from .小工具 import 拆顶层项
from .符号解析 import 解符号, 末段


def 记判据(判据: str, 判定: str, 位置: str, 缺什么: str, 不能自愈: str, 红类: str = "") -> dict:
    return {
        "位置": 位置,
        "缺什么": 缺什么,
        "为什么不能自愈": 不能自愈,
        "判定": 判定,
        "红类": 红类,
    }


def _本表(单元: dict) -> dict:
    """本单元内可解析的整数符号（能力号 · 错误码 · 本文件 const）。"""
    表 = {}
    for 条目 in 单元["能力号"]:
        if 条目["值"] is not None:
            表[条目["名"]] = 条目["值"]
    for 条目 in 单元.get("错误码常量", []):
        if 条目["值"] is not None:
            表[条目["名"]] = 条目["值"]
    表.update(单元.get("本文件整数常量", {}))
    return 表


def _取编号(字段: dict, 兜底):
    """命令编号读法：**显式字段优先，下标只作兜底**（`契约声明/src/lib.rs` 命令信息 · 旁路区）。

    `命令信息.编号` 是显式 `u32`（旧形状没有这个字段）⇒ 有字段且解得出就用它；
    字段缺失或解不出才退回 `兜底()`（= 命令表下标 / 下标表达式）。
    为什么这么排：显式编号是唯一对照键（`字段名册与引用方式.md` §三 的旧约定已废止）。
    """
    编号字段 = 字段.get("编号")
    if 编号字段 and 编号字段.get("值") is not None:
        return 编号字段["值"], (编号字段.get("原文") or "").strip()
    return 兜底()


def _解可抛错误码(单元: dict, 原文, 符号表: dict, 本表: dict):
    """把 `命令信息.可抛错误码` 的实参解析成错误码列表；解不出返回 None（不许猜）。

    只认两种写法（`契约声明/src/lib.rs` 命令信息 · 旁路区 `可抛错误码: 表段<u32>`）：
    `表段::空实例()` = 空集（本命令不抛错，不是漏写）；`表段::新建(<本单元 [u32; N] 表>.as_ptr(), …)`
    = 取那张表的项逐项解符号。别的写法一律 None ⇒ 判据侧报未判并写明原文。
    """
    if 原文 is None:
        return None
    文 = 原文.strip()
    if re.fullmatch(r"表段\s*::\s*空实例\s*\(\s*\)", 文):
        return []
    匹配 = re.match(r"表段\s*::\s*新建\s*\(\s*([^\s.(]+)\s*\.\s*as_ptr\s*\(\s*\)", 文)
    if not 匹配:
        return None
    抛码表项 = 单元.get("抛码表", {}).get(末段(匹配.group(1)))
    if 抛码表项 is None:
        return None
    结果 = []
    for 项 in 拆顶层项(抛码表项.get("内文") or ""):
        值 = 解符号(项, 符号表, 本表)
        if 值 is None:
            return None
        结果.append(值)
    return 结果


def _按编号找命令(单元: dict, 编号) -> object:
    for 条目 in 单元["命令"]:
        if 条目["编号"] == 编号:
            return 条目
    return None


def _参数表名(一条: dict) -> object:
    原 = 一条["字段"].get("参数表", {}).get("原文")
    if 原 is None:
        return None
    匹配 = re.match(r"([^\s.]+)", 原.strip())
    if not 匹配:
        return None
    名 = 匹配.group(1)
    if "::" in 名 or 名 in ("core", "std", "null"):
        return None  # 路径表达式（`core::ptr::null()` 之类）不是本地参数表名
    return 名


def _落点(单元: dict, 名称: str) -> object:
    """本单元里名为 `名称` 的 const（③g / ③h 的编译期断言落点）；没有返回 None。

    为什么按**名**取 const 而不扫表声明：落点是**声明过的契约名**（只在一处定义，
    改口径只改那一处），而扫声明文本会因换个命名 / 挪个位置就漏（假绿）。
    """
    for 条目 in 单元["常量"]:
        if 条目["名"] == 名称:
            return 条目
    return None
