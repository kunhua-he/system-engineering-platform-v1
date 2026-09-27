# -*- coding: utf-8 -*-
"""Rust 构造点与常量抽取（手写 平台信息 的判据靠它）。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .剥字面量 import cfg测试区, 去字面量


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
    净 = 去字面量(文本)
    区表 = cfg测试区(文本)
    行首表 = [0]
    for i, c in enumerate(净):
        if c == "\n":
            行首表.append(i + 1)

    def 行号(位: int) -> int:
        低, 高 = 0, len(行首表) - 1
        while 低 < 高:
            中 = (低 + 高 + 1) // 2
            if 行首表[中] <= 位:
                低 = 中
            else:
                高 = 中 - 1
        return 低 + 1

    def 行文(位: int) -> str:
        起 = 行首表[行号(位) - 1]
        止 = 文本.find("\n", 起)
        return 文本[起 : 止 if 止 >= 0 else len(文本)].strip()

    点表 = []
    for 命 in 构造模式.finditer(净):
        行 = 行号(命.start())
        行起 = 行首表[行 - 1]
        行内前文 = 净[行起 : 命.start()]
        if any(标 in 行内前文 for 标 in 非构造标记):
            continue
        前文紧 = 净[: 命.start()].rstrip()
        if not 前文紧 or 前文紧[-1] not in 构造前导:
            continue
        起 = 命.end() - 1
        深 = 0
        止 = None
        for i in range(起, len(净)):
            if 净[i] == "{":
                深 += 1
            elif 净[i] == "}":
                深 -= 1
                if 深 == 0:
                    止 = i
                    break
        if 止 is None:
            止 = len(净) - 1
        字段 = {}
        for 行文段 in 文本[起 + 1 : 止].splitlines():
            段 = 行文段.strip().rstrip(",")
            if not 段 or ":" not in 段:
                continue
            名, _, 值 = 段.partition(":")
            字段[名.strip()] = 值.strip()
        # 所属具名项：先看**本行**是不是项头（`static 底座存储: … = …(平台信息 {`）；
        # 否则用「往回找块开括号」定到所在块，再取该块的项头（`fn 夹具…() {`）。
        # 不按缩进猜——同一块里的兄弟 `static` 缩进相同，猜法会取错（实测撞到过）。
        具名 = ""
        行起位 = 行首表[行 - 1]
        同行前文 = 净[行起位 : 命.start()]
        配 = 具名项头.match(同行前文)
        if 配:
            具名 = 配.group(3)
        else:
            位 = 命.start()
            for _ in range(3):  # 最多上溯三层（mod 套 fn 之类）
                块起 = -1
                深 = 0
                for i in range(位 - 1, -1, -1):
                    if 净[i] == "}":
                        深 += 1
                    elif 净[i] == "{":
                        if 深 == 0:
                            块起 = i
                            break
                        深 -= 1
                if 块起 < 0:
                    break
                块行 = 行号(块起)
                块行起 = 行首表[块行 - 1]
                块上行 = 文本[块行起 : 文本.find("\n", 块行起) if 文本.find("\n", 块行起) >= 0 else len(文本)]
                配 = 具名项头.match(块上行)
                if 配:
                    具名 = 配.group(3)
                    break
                位 = 块起
        点表.append(
            {
                "行号": 行,
                "头行": 行文(命.start()),
                "字段": 字段,
                "测试区": any(a <= 命.start() <= b for a, b in 区表),
                "具名项": 具名,
            }
        )
    return 点表


def _抽版本三元组(文本: str, 常量名: str):
    """抽 `const 名: 版本三元组 = 版本三元组::新(主, 次, 修订, 构建);` → '主.次.修订.构建'。"""
    形 = re.compile(
        r"const\s+" + re.escape(常量名) + r"\s*:\s*版本三元组\s*=\s*版本三元组::新\s*\("
        r"\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,?\s*\)"
    )
    命中 = 形.search(文本)
    if not 命中:
        return None
    return ".".join(命中.group(i) for i in (1, 2, 3, 4))


def 跑生成器检查(仓根: Path, 生成器: Path) -> tuple:
    """调生成器自己的 --检查（§八：重新生成并与落盘件逐字节比对）。返回 (退出码, 输出摘要)。"""
    try:
        果 = subprocess.run(
            [sys.executable, str(生成器), "--检查"],
            cwd=str(仓根),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as 错:
        return 127, f"起不动生成器：{错}"
    输出 = (果.stdout or "").strip() or (果.stderr or "").strip()
    return 果.returncode, 输出.replace("\n", " ／ ")[:400]


def _抽字节串常量(文本: str, 常量名: str):
    形 = re.compile(
        r"const\s+" + re.escape(常量名) + r'\s*:\s*[^=]+=\s*(?:b)?"((?:[^"\\]|\\.)*)"',
        re.S,
    )
    命中 = 形.search(文本)
    if not 命中:
        return None
    return _解Rust转义(命中.group(1))


_转义表 = {"0": "\0", "n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}


def _解Rust转义(原: str) -> str:
    """把 Rust 字面量里的转义还原（`\\0` → NUL），并去掉结尾 NUL（契约要的是 NUL 结尾串）。"""
    出 = []
    序 = 0
    while 序 < len(原):
        if 原[序] == "\\" and 序 + 1 < len(原):
            出.append(_转义表.get(原[序 + 1], 原[序 + 1]))
            序 += 2
        else:
            出.append(原[序])
            序 += 1
    return "".join(出).rstrip("\0")


def _抽整数常量(文本: str, 常量名: str, 类型名: str):
    形 = re.compile(
        r"const\s+" + re.escape(常量名) + r"\s*:\s*" + 类型名 + r"\s*=\s*([0-9_]+)"
    )
    命中 = 形.search(文本)
    if not 命中:
        return None
    try:
        return int(命中.group(1).replace("_", ""))
    except ValueError:
        return None


def _抽平台信息字段(文本: str) -> set:
    """从 契约声明/src/lib.rs 的 `pub struct 平台信息 { … }` 里抽字段名。"""
    形 = re.compile(r"pub\s+struct\s+平台信息\s*\{(.*?)\n\}", re.S)
    命中 = 形.search(文本)
    if not 命中:
        return set()
    字段 = set()
    for 行 in 命中.group(1).splitlines():
        行 = 行.split("//", 1)[0].strip()
        if 行.startswith("pub "):
            声明 = 行[4:].split(":", 1)[0].strip()
            if 声明:
                字段.add(声明)
    return 字段


# 整份夹具的挂载声明：`#[cfg(test)]`（可含别的 cfg 条件，括号可嵌套）+ 若干属性
# （`#[path = "…"]` 就在这里，也可能写在 cfg **之前**）+ `mod 名;`。
# 只认以 `;` 结尾的 `mod`——`mod 名 { … }` 是**内联**测试块（在同一个文件里），不是外部文件。
_夹具挂载形 = re.compile(r"#\[\s*cfg\s*\(")


def _属性窗口起(掩: str, 位: int) -> int:
    """本项的起点：往回找最近的 `;` / `{` / `}` —— `#[path = "…"]` 写在 `#[cfg(test)]`
    **之前**也是合法的属性顺序，所以取 `#[path]` 时不能只看 cfg 之后那一段。"""
    起 = 位
    while 起 > 0 and 掩[起 - 1] not in ";{}":
        起 -= 1
    return 起


def _cfg属性(掩: str, 起: int):
    """从 `起`（指向 `#`）解析一个 `#[cfg(…)]` 属性，返回 (属性文本, 结束位) 或 None。

    括号**配对**解析：`#[cfg(any(test, feature = "x"))]` 有两层括号，`[^)]*` 这类正则会漏
    ⇒ 「扫描面不覆盖它声称的范围」（判据的可信性.md §三.2）。
    """
    配 = re.match(r"#\[\s*cfg\s*\(", 掩[起:])
    if not 配:
        return None
    k = 起 + 配.end()
    n = len(掩)
    深 = 1
    while k < n and 深:
        if 掩[k] == "(":
            深 += 1
        elif 掩[k] == ")":
            深 -= 1
        k += 1
    if 深:
        return None
    j = k
    while j < n and 掩[j] in " \t\r\n":
        j += 1
    if j >= n or 掩[j] != "]":
        return None
    return 掩[起 : j + 1], j + 1
