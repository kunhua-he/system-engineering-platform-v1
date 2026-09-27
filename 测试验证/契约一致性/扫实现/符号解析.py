# -*- coding: utf-8 -*-
"""符号解析 —— 值 / 符号解析（解析不出来一律 None —— 不许猜）。"""
from __future__ import annotations

import re

from .常量 import 生成物相对, 契约源相对
from .小工具 import 配对
from .掩码 import 掩码


def 解整数(文) -> object:
    if 文 is None:
        return None
    文 = 文.strip()
    if re.fullmatch(r"\d+", 文):
        return int(文)
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", 文):
        return int(文, 16)
    m = re.fullmatch(r"(\d+)\s*(<<|>>|\+|\-|\*|/|\||&)\s*(\d+)", 文)
    if m:
        a, 运, b = int(m.group(1)), m.group(2), int(m.group(3))
        try:
            return {
                "<<": a << b, ">>": a >> b, "+": a + b, "-": a - b,
                "*": a * b, "/": a // b, "|": a | b, "&": a & b,
            }[运]
        except (ValueError, ZeroDivisionError):
            return None
    m = re.fullmatch(r"(\d+)\s+as\s+\w+", 文)
    if m:
        return int(m.group(1))
    return None


def 解表达式(文, 表: dict) -> object:
    """把 `表` 里的符号代入后求整数（例：`码 / 1000` + {码: 1001} → 1）。解不出 None。"""
    if 文 is None:
        return None
    v = 解整数(文)
    if v is not None:
        return v
    换 = 文
    for 名 in sorted(表, key=len, reverse=True):
        值 = 表[名]
        if 值 is None:
            continue
        换 = re.sub(r"(?<![\w:])" + re.escape(名) + r"(?![\w:])", str(值), 换)
    return 解整数(换)


def 末段(文: str) -> str:
    return 文.strip().split("::")[-1].strip()


def 解符号(文, 符号表: dict, 本表: dict) -> object:
    """把 `类型标签_0005` / `v1_contract::声明数据::类型标签_0005` /
    `命令状态::错误` / `能力号::生成容器 as usize` 解析成数。解不出返回 None。"""
    if 文 is None:
        return None
    文 = 文.strip()
    v = 解整数(文)
    if v is not None:
        return v
    m = re.fullmatch(r"(.+?)\s+as\s+\w+", 文)
    if m:
        文 = m.group(1).strip()
    名 = 末段(文)
    if 名 in 本表:
        return 本表[名]
    if 名 in 符号表:
        return 符号表[名]
    return 解表达式(文, {**符号表, **本表})


def 建符号表(件表: dict, 掩表: dict = None) -> dict:
    """从生成物 + 契约源建「符号 → 数」引用表（只读，不计入实现面）。"""
    表 = {}
    掩表 = 掩表 or {}
    生成 = 件表.get(生成物相对)
    if 生成:
        掩 = 掩表.get(生成物相对) or 掩码(生成)
        for m in re.finditer(
            r"(?m)^\s*pub\s+const\s+([^\s:]+)\s*:\s*[^=;]*?=\s*([^;]+);", 掩
        ):
            v = 解整数(m.group(2))
            if v is not None:
                表[m.group(1)] = v
    源 = 件表.get(契约源相对)
    if 源:
        掩 = 掩表.get(契约源相对) or 掩码(源)
        # pub mod <M> { … pub const <名>: <t> = <expr>; … }
        for mm in re.finditer(r"pub\s+mod\s+([^\s{]+)\s*\{", 掩):
            止 = 配对(掩, mm.end() - 1)
            if 止 < 0:
                continue
            块 = 掩[mm.end() : 止]
            for c in re.finditer(
                r"pub\s+const\s+([^\s:]+)\s*:\s*[^=;]*?=\s*([^;]+);", 块
            ):
                v = 解整数(c.group(2))
                if v is not None:
                    表[c.group(1)] = v
        # pub use <路径>::<原名> as <别名>;
        for m in re.finditer(
            r"pub\s+use\s+([^\s;]+?)\s+as\s+([^\s;]+)\s*;", 掩
        ):
            原名 = m.group(1).split("::")[-1]
            if 原名 in 表:
                表[m.group(2)] = 表[原名]
    return 表
