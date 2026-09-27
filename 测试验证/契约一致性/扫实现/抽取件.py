# -*- coding: utf-8 -*-
"""抽取件 —— 逐文件抽实现面：常量 · 构造器 · 数组表 · 参数表 · 类型表 · 错误码表 · 导出。"""
from __future__ import annotations

import re

from .小工具 import 配对, 拆顶层项, 找顶层终止, 行号
from .符号解析 import 解整数, 解符号

def 抽模块常量(掩: str, 键: str, 模块名: str) -> list:
    """`pub mod <模块名> { pub const <名>: <t> = <值>; }` → [{名, 值, 位置}]。"""
    出 = []
    for m in re.finditer(r"pub\s+mod\s+" + re.escape(模块名) + r"\s*\{", 掩):
        止 = 配对(掩, m.end() - 1)
        if 止 < 0:
            continue
        块起 = m.end()
        for c in re.finditer(
            r"pub\s+const\s+([^\s:]+)\s*:\s*[^=;]*?=\s*([^;]+);", 掩[块起:止]
        ):
            v = 解整数(c.group(2))
            出.append(
                {
                    "名": c.group(1),
                    "值": v,
                    "原文": c.group(2).strip(),
                    "位置": f"{键}:{行号(掩, 块起 + c.start())}",
                }
            )
    return 出


def 抽构造器(掩: str, 返回型: str) -> dict:
    """`const fn <名>(<形参>) -> <返回型> { <返回型> { 字段: 值, … } }`

    返回 {构造名: {"形参": [名…], "字段": {字段: ("形参"|"表达式", 文本)}}}。
    """
    出 = {}
    for m in re.finditer(r"const\s+fn\s+([^\s(<]+)\s*\(", 掩):
        形参起 = m.end() - 1
        形参止 = 配对(掩, 形参起)
        if 形参止 < 0:
            continue
        形参名 = []
        for p in 拆顶层项(掩[形参起 + 1 : 形参止]):
            名 = p.split(":", 1)[0].strip()
            if 名:
                形参名.append(名)
        尾 = 掩[形参止 + 1 : 形参止 + 200]
        m2 = re.match(r"\s*->\s*" + re.escape(返回型) + r"\s*\{", 尾)
        if not m2:
            continue
        # `-> 返回型 {` 那个 `{` 是**函数体**的开括号；真正的结构体字面量在它里面。
        # 实测两种写法都有：`-> 命令信息 { 命令信息 { … } }` 与 `-> 命令信息 { …字段… }`，
        # 所以先看函数体里有没有 `<返回型> {`，没有才把函数体本身当字段表。
        体起0 = 形参止 + 1 + m2.end() - 1
        体止0 = 配对(掩, 体起0)
        if 体止0 < 0:
            continue
        体0 = 掩[体起0 + 1 : 体止0]
        m3 = re.search(r"(?:^|[^\w])" + re.escape(返回型) + r"\s*\{", 体0)
        if m3:
            体起 = 体起0 + 1 + m3.end() - 1
            体止 = 配对(掩, 体起)
            if 体止 < 0:
                continue
            体 = 掩[体起 + 1 : 体止]
        else:
            体 = 体0
        字段 = {}
        for f in 拆顶层项(体):
            if ":" in f:
                名, 值 = f.split(":", 1)
                字段[名.strip()] = ("表达式", 值.strip())
            else:
                字段[f.strip()] = ("形参", f.strip())
        出[m.group(1)] = {"形参": 形参名, "字段": 字段}
    return 出


def 抽本文件整数常量(掩: str) -> dict:
    """本文件里能定值的整数常量（含 `能力号段[0].止 as usize + 1` 这一种）。"""
    表 = {}
    for m in re.finditer(r"(?:^|\n)[ \t]*(?:pub\s+)?const\s+([^\s:]+)\s*:", 掩):
        名 = m.group(1)
        位 = m.end()
        _, 值文, _ = _切声明(掩, 位)
        v = 解整数(值文)
        if v is not None:
            表[名] = v
            continue
        # const 命令表项数: usize = 能力号段[0].止 as usize + 1;
        m2 = re.fullmatch(r"([^\s\[]+)\s*\[\s*(\d+)\s*\]\s*\.\s*止\s+as\s+usize\s*\+\s*(\d+)", 值文 or "")
        if m2:
            段名, 序, 加 = m2.group(1), int(m2.group(2)), int(m2.group(3))
            m3 = re.search(
                r"const\s+" + re.escape(段名) + r"\s*:\s*\[[^\]]*\]\s*=\s*\[([^\]]*)\]",
                掩,
            )
            if m3:
                项 = 拆顶层项(m3.group(1))
                if 序 < len(项):
                    内 = re.search(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)", 项[序])
                    if 内:
                        表[名] = int(内.group(2)) + 加
    return 表


def _切声明(掩: str, 位: int):
    """从 `位` 起切一个 const/static 声明：返回 (类型文, 值文, 止位)。"""
    深 = 0
    i = 位
    类型起 = 位
    while i < len(掩):
        c = 掩[i]
        if c in "([{":
            深 += 1
        elif c in ")]}":
            深 -= 1
        elif 深 == 0 and c == "=":
            值起 = i + 1
            值止 = 找顶层终止(掩, 值起, ";")
            if 值止 < 0:
                return 掩[类型起:i].strip(), 掩[值起:].strip(), len(掩)
            return 掩[类型起:i].strip(), 掩[值起:值止].strip(), 值止 + 1
        elif 深 == 0 and c == ";":
            return 掩[类型起:i].strip(), None, i + 1
        i += 1
    return None, None, len(掩)


def 抽数组表(掩: str, 元素型: str) -> list:
    """抽 `(const|static) <名>: [<元素型>; <N>] = [ … ];` 与
    `const fn <名>() -> [<元素型>; <N>] { … }` 的表体。

    **不再抽「声明项数 `<N>`」**：命令表 / 函数表的项数已由编译期断言落点承担（③g），
    留一个没人判的项数在这里就是第二个事实源（`项目文档/哲学.md` §一）。
    """
    出 = []
    for m in re.finditer(
        r"(?:const|static)\s+([^\s:]+)\s*:\s*\[\s*" + re.escape(元素型)
        + r"\s*;\s*([^\]]+)\]\s*=\s*",
        掩,
    ):
        表名 = m.group(1)
        rhs起 = m.end()
        分号 = 找顶层终止(掩, rhs起, ";")
        rhs = 掩[rhs起:分号].strip() if 分号 > 0 else 掩[rhs起:].strip()
        出.append(
            {
                "表名": 表名,
                "值原文": rhs,
                "位置": f"{行号(掩, m.start())}",
                "内文": (掩[rhs起 + 1 : 配对(掩, rhs起)] if rhs.startswith("[") else None),
                "内文起": rhs起 + 1,
            }
        )
    for m in re.finditer(
        r"const\s+fn\s+([^\s(<]+)\s*\(\s*\)\s*->\s*\[\s*" + re.escape(元素型)
        + r"\s*;\s*([^\]]+)\]\s*\{",
        掩,
    ):
        体起 = m.end() - 1
        体止 = 配对(掩, 体起)
        if 体止 < 0:
            continue
        出.append(
            {
                "表名": m.group(1),
                "值原文": m.group(1) + "()",
                "位置": f"{行号(掩, m.start())}",
                "内文": 掩[体起 + 1 : 体止],
                "内文起": 体起 + 1,
                "是函数": True,
            }
        )
    return 出


def 抽参数表(掩: str, 键: str, 符号表: dict) -> dict:
    """抽 `[参数信息; N]` 表 → {表名: {类型标签原文, 位置}}。

    **不再抽「项数」**：③h 已改成读编译期断言落点（表长只有编译器数得准），
    留一个没人判的项数在这里就是第二个事实源（`项目文档/哲学.md` §一）。
    """
    出 = {}
    for m in re.finditer(
        r"(?:const|static)\s+([^\s:]+)\s*:\s*\[\s*参数信息\s*;\s*([^\]]+)\]\s*=\s*\[",
        掩,
    ):
        起 = m.end() - 1
        止 = 配对(掩, 起)
        if 止 < 0:
            continue
        内 = 掩[起 + 1 : 止]
        项 = 拆顶层项(内)
        标签 = []
        for t in 项:
            t2 = t.split("{", 1)[1] if "{" in t else t
            mm = re.search(r"类型标签\s*:\s*([^,}]+)", t2)
            标签.append(mm.group(1).strip() if mm else None)
        出[m.group(1)] = {
            "类型标签原文": 标签,
            "位置": f"{键}:{行号(掩, m.start())}",
        }
    return 出


def 抽类型表(掩: str, 键: str) -> list:
    出 = []
    for m in re.finditer(
        r"(?:const|static)\s+([^\s:]+)\s*:\s*\[\s*数据类型信息\s*;\s*([^\]]+)\]\s*=\s*\[",
        掩,
    ):
        起 = m.end() - 1
        止 = 配对(掩, 起)
        if 止 < 0:
            continue
        for t in 拆顶层项(掩[起 + 1 : 止]):
            if "{" not in t:
                continue
            内 = t.split("{", 1)[1]
            mm = re.search(r"类型标签\s*:\s*([^,}]+)", 内)
            出.append(
                {
                    "表名": m.group(1),
                    "类型标签原文": mm.group(1).strip() if mm else None,
                    "位置": f"{键}:{行号(掩, m.start())}",
                }
            )
    return 出


def 抽错误码表(掩: str, 键: str, 符号表: dict, 本表: dict) -> dict:
    出 = {"表": [], "来源": None, "位置": None}
    for m in re.finditer(
        r"(?:const|static)\s+([^\s:]+)\s*:\s*\[\s*错误码信息\s*;\s*([^\]]+)\]\s*=\s*\[",
        掩,
    ):
        起 = m.end() - 1
        止 = 配对(掩, 起)
        if 止 < 0:
            continue
        构造 = 抽构造器(掩, "错误码信息")
        段位表达式 = None
        for 名, c in 构造.items():
            f = c["字段"].get("段位")
            if f and f[0] == "表达式":
                段位表达式 = f[1]
        for t in 拆顶层项(掩[起 + 1 : 止]):
            t = t.strip()
            if "{" in t:
                内 = t.split("{", 1)[1]
                码文 = re.search(r"(?:^|,)\s*码\s*:\s*([^,}]+)", 内)
                段文 = re.search(r"(?:^|,)\s*段位\s*:\s*([^,}]+)", 内)
                码 = 解符号(码文.group(1), 符号表, 本表) if 码文 else None
                段 = 解符号(段文.group(1), 符号表, 本表) if 段文 else None
            else:
                mm = re.match(r"([^\s(]+)\s*\((.*)\)\s*$", t, re.S)
                if not mm:
                    continue
                实参 = 拆顶层项(mm.group(2))
                码 = 解符号(实参[0], 符号表, 本表) if 实参 else None
                段 = None
                if 段位表达式 and 码 is not None:
                    v = 解符号(段位表达式, {**符号表, "码": 码}, 本表)
                    段 = v
            出["表"].append(
                {"码": 码, "段位": 段, "原文": " ".join(t.split())[:70], "位置": f"{键}:{行号(掩, m.start())}"}
            )
        出["来源"] = "字面量表"
        出["位置"] = f"{键}:{行号(掩, m.start())}"
        return 出
    # 非字面量：`错误码表: 表段::新(v1_contract::声明数据::错误码信息表段()…)`
    m = re.search(r"错误码表\s*:\s*([^,\n}]+)", 掩)
    if m:
        出["来源"] = "生成物"
        出["位置"] = f"{键}:{行号(掩, m.start())}"
        出["原文"] = m.group(1).strip()
    return 出


导出模式 = re.compile(r"#\[\s*(?:unsafe\s*\(\s*)?export_name\s*=")
无修饰模式 = re.compile(r"#\[\s*no_mangle\s*\]")


def 抽导出(掩: str, 原文本: str, 键: str) -> list:
    出 = []
    for m in 导出模式.finditer(掩):
        引 = 原文本.find('"', m.end(), min(len(原文本), m.end() + 200))
        if 引 < 0:
            continue
        终引 = 原文本.find('"', 引 + 1)
        if 终引 < 0:
            continue
        出.append({"符号": 原文本[引 + 1 : 终引], "位置": f"{键}:{行号(掩, m.start())}"})
    for m in 无修饰模式.finditer(掩):
        尾 = 掩[m.end() : m.end() + 300]
        f = re.search(r"fn\s+([^\s(<]+)", 尾)
        出.append(
            {"符号": (f.group(1) if f else "?"), "位置": f"{键}:{行号(掩, m.start())}"}
        )
    return 出


def 抽常量(掩: str, 键: str) -> list:
    出 = []
    for m in re.finditer(r"(?:^|\n)[ \t]*(?:pub\s+)?const\s+([^\s:]+)\s*:", 掩):
        名 = m.group(1)
        _, 值文, _ = _切声明(掩, m.end())
        出.append(
            {
                "名": 名,
                "值文": 值文,
                "值": 解整数(值文),
                "位置": f"{键}:{行号(掩, m.start() + 1)}",
            }
        )
    return 出
