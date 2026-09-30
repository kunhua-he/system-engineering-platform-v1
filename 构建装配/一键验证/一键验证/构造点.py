# -*- coding: utf-8 -*-
"""Rust 构造点与常量抽取（手写 平台信息 的判据靠它）。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .剥字面量 import 条件编译测试区, 去字面量


构造模式 = re.compile(r"平台信息\s*\{")
具名项头 = re.compile(
    r"^([ \t]*)(?:pub(?:\([^)]*\))?[ \t]+)?(static|const|fn)[ \t]+([^\s:(<]+)"
)
# 这些出现在同一行且位于 平台信息 之前 ⇒ 它不是一个「构造」，而是类型声明/返回类型/impl 头
非构造标记 = ("->", "struct ", "enum ", "impl ", "trait ")
# 构造点前一个非空白字符只可能是这些（表达式位置）
构造前导 = ("=", "(", ",", "[", "{", ":")


def 找构造点(文本: str) -> list:
    """找出所有 `平台信息 { … }` **构造点**（不是类型声明、不是返回类型）。

    区分办法：同一行里 平台信息 之前出现 `->` / `struct` / `enum` / `impl` / `trait`
    的，是类型位置；前一个非空白字符不在 `= ( , [ { :` 里的，也不是构造。
    """
    净文本 = 去字面量(文本)
    区表 = 条件编译测试区(文本)
    行首表 = [0]
    for 游标, 字符 in enumerate(净文本):
        if 字符 == "\n":
            行首表.append(游标 + 1)

    def 行号(位置: int) -> int:
        下界, 上界 = 0, len(行首表) - 1
        while 下界 < 上界:
            中点 = (下界 + 上界 + 1) // 2
            if 行首表[中点] <= 位置:
                下界 = 中点
            else:
                上界 = 中点 - 1
        return 下界 + 1

    def 行文(位置: int) -> str:
        区间起点 = 行首表[行号(位置) - 1]
        区间终点 = 文本.find("\n", 区间起点)
        return 文本[区间起点 : 区间终点 if 区间终点 >= 0 else len(文本)].strip()

    点表 = []
    for 命中 in 构造模式.finditer(净文本):
        源码行 = 行号(命中.start())
        行起 = 行首表[源码行 - 1]
        行内前文 = 净文本[行起 : 命中.start()]
        if any(标记 in 行内前文 for 标记 in 非构造标记):
            continue
        前文紧 = 净文本[: 命中.start()].rstrip()
        if not 前文紧 or 前文紧[-1] not in 构造前导:
            continue
        区间起点 = 命中.end() - 1
        深度 = 0
        区间终点 = None
        for 游标 in range(区间起点, len(净文本)):
            if 净文本[游标] == "{":
                深度 += 1
            elif 净文本[游标] == "}":
                深度 -= 1
                if 深度 == 0:
                    区间终点 = 游标
                    break
        if 区间终点 is None:
            区间终点 = len(净文本) - 1
        字段 = {}
        for 行文段 in 文本[区间起点 + 1 : 区间终点].splitlines():
            号段 = 行文段.strip().rstrip(",")
            if not 号段 or ":" not in 号段:
                continue
            字段名, _, 字段值 = 号段.partition(":")
            字段[字段名.strip()] = 字段值.strip()
        # 所属具名项：先看**本行**是不是项头（`static 底座存储: … = …(平台信息 {`）；
        # 否则用「往回找块开括号」定到所在块，再取该块的项头（`fn 夹具…() {`）。
        # 不按缩进猜——同一块里的兄弟 `static` 缩进相同，猜法会取错（实测撞到过）。
        具名 = ""
        行起位 = 行首表[源码行 - 1]
        同行前文 = 净文本[行起位 : 命中.start()]
        名配 = 具名项头.match(同行前文)
        if 名配:
            具名 = 名配.group(3)
        else:
            位置 = 命中.start()
            for _ in range(3):  # 最多上溯三层（mod 套 fn 之类）
                块起 = -1
                深度 = 0
                for 游标 in range(位置 - 1, -1, -1):
                    if 净文本[游标] == "}":
                        深度 += 1
                    elif 净文本[游标] == "{":
                        if 深度 == 0:
                            块起 = 游标
                            break
                        深度 -= 1
                if 块起 < 0:
                    break
                块行 = 行号(块起)
                块行起 = 行首表[块行 - 1]
                块上行 = 文本[块行起 : 文本.find("\n", 块行起) if 文本.find("\n", 块行起) >= 0 else len(文本)]
                名配 = 具名项头.match(块上行)
                if 名配:
                    具名 = 名配.group(3)
                    break
                位置 = 块起
        点表.append(
            {
                "行号": 源码行,
                "头行": 行文(命中.start()),
                "字段": 字段,
                "测试区": any(区起 <= 命中.start() <= 区止 for 区起, 区止 in 区表),
                "具名项": 具名,
            }
        )
    return 点表


def _抽版本三元组(文本: str, 常量名: str):
    """抽 `const 名: v1_contract::(版本三元组|版本要求) = v1_contract::\1::新建(…);` → `'主.次[.构建]'`。

    **两型两种段数**（拉齐参照实现，见 `契约声明/基础形状.rs`）：
    `版本三元组` = 3 段（实现/提供）· `版本要求` = 2 段（要求，无修订）。
    故断言 **2–4** 段都收：段数与型对不对由另一边（渲染侧）保证，本件只负责把数抽出来对拍。
    """
    格式器 = re.compile(
        r"const\s+" + re.escape(常量名)
        + r"\s*:\s*v1_contract::(版本三元组|版本要求)\s*=\s*v1_contract::\1::新建\s*\("
        r"((?:\s*\d+\s*,)*\s*\d+)\s*,?\s*\)"
    )
    命中 = 格式器.search(文本)
    if not 命中:
        return None
    return ".".join(版本段.strip() for 版本段 in 命中.group(2).split(","))


def 跑生成器检查(仓根: Path, 生成器: Path) -> tuple:
    """调生成器自身的 --检查（§八：重新生成并与落盘件逐字节比对）。返回 (退出码, 输出摘要)。"""
    try:
        结果 = subprocess.run(
            [sys.executable, str(生成器), "--检查"],
            cwd=str(仓根),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as 错误:
        return 127, f"起不动生成器：{错误}"
    输出 = (结果.stdout or "").strip() or (结果.stderr or "").strip()
    return 结果.returncode, 输出.replace("\n", " ／ ")[:400]


def _抽字节串常量(文本: str, 常量名: str):
    格式器 = re.compile(
        r"const\s+" + re.escape(常量名) + r'\s*:\s*[^=]+=\s*(?:b)?"((?:[^"\\]|\\.)*)"',
        re.S,
    )
    命中 = 格式器.search(文本)
    if not 命中:
        return None
    return _解Rust转义(命中.group(1))


_转义表 = {"0": "\0", "n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}


def _解Rust转义(原文: str) -> str:
    """把 Rust 字面量里的转义还原（`\\0` → NUL），并去掉结尾 NUL（契约要的是 NUL 结尾串）。"""
    输出缓冲 = []
    序号 = 0
    while 序号 < len(原文):
        if 原文[序号] == "\\" and 序号 + 1 < len(原文):
            输出缓冲.append(_转义表.get(原文[序号 + 1], 原文[序号 + 1]))
            序号 += 2
        else:
            输出缓冲.append(原文[序号])
            序号 += 1
    return "".join(输出缓冲).rstrip("\0")


def _抽整数常量(文本: str, 常量名: str, 类型名: str):
    格式器 = re.compile(
        r"const\s+" + re.escape(常量名) + r"\s*:\s*" + 类型名 + r"\s*=\s*([0-9_]+)"
    )
    命中 = 格式器.search(文本)
    if not 命中:
        return None
    try:
        return int(命中.group(1).replace("_", ""))
    except ValueError:
        return None


def _抽平台信息字段(文本: str) -> set:
    """从 契约声明/src/lib.rs 的 `pub struct 平台信息 { … }` 里抽字段名。"""
    格式器 = re.compile(r"pub\s+struct\s+平台信息\s*\{(.*?)\n\}", re.S)
    命中 = 格式器.search(文本)
    if not 命中:
        return set()
    字段 = set()
    for 源码行 in 命中.group(1).splitlines():
        源码行 = 源码行.split("//", 1)[0].strip()
        if 源码行.startswith("pub "):
            声明 = 源码行[4:].split(":", 1)[0].strip()
            if 声明:
                字段.add(声明)
    return 字段


# 整份夹具的挂载声明：`#[cfg(test)]`（可含别的 cfg 条件，括号可嵌套）+ 若干属性
# （`#[path = "…"]` 就在这里，也可能写在 cfg **之前**）+ `mod 名;`。
# 只认以 `;` 结尾的 `mod`——`mod 名 { … }` 是**内联**测试块（在同一个文件里），不是外部文件。
_夹具挂载形 = re.compile(r"#\[\s*cfg\s*\(")


def _属性窗口起(掩码文本: str, 位置: int) -> int:
    """本项的起点：往回找最近的 `;` / `{` / `}` —— `#[path = "…"]` 写在 `#[cfg(test)]`
    **之前**也是合法的属性顺序，所以取 `#[path]` 时不能只看 cfg 之后那一段。"""
    区间起点 = 位置
    while 区间起点 > 0 and 掩码文本[区间起点 - 1] not in ";{}":
        区间起点 -= 1
    return 区间起点


def _条件编译属性(掩码文本: str, 区间起点: int):
    """从 `区间起点`（指向 `#`）解析一个 `#[cfg(…)]` 属性，返回 (属性文本, 结束位) 或 None。

    括号**配对**解析：`#[cfg(any(test, feature = "x"))]` 有两层括号，`[^)]*` 这类正则会漏
    ⇒ 「扫描面不覆盖它声称的范围」（判据的可信性.md §三.2）。
    """
    命中 = _夹具挂载形.match(掩码文本, 区间起点)
    if not 命中:
        return None
    位置 = 命中.end()
    长度 = len(掩码文本)
    深度 = 1
    while 位置 < 长度 and 深度:
        if 掩码文本[位置] == "(":
            深度 += 1
        elif 掩码文本[位置] == ")":
            深度 -= 1
        位置 += 1
    if 深度:
        return None
    收尾 = 位置
    while 收尾 < 长度 and 掩码文本[收尾] in " \t\r\n":
        收尾 += 1
    if 收尾 >= 长度 or 掩码文本[收尾] != "]":
        return None
    return 掩码文本[区间起点 : 收尾 + 1], 收尾 + 1
