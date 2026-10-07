# -*- coding: utf-8 -*-
"""语法闸 —— `v1_edit` 第 ⑦ 道闸：整批**最终态**内存模拟 + `ast.parse`（**只解析 · 不执行**）。

**为什么要有它**（实测 2026-10-08）：`v1_edit` 只检查原先只做局部风险提示（行数 / 入口 /
十干 / 禁译名），**不查语法** ⇒ 一个缩进坏件一路放行、真写落盘才 `SyntaxError`（同域 531 HTTP
修暴露的同一类）。本件按 `ast.parse` 判**整批最终态**：新建 / 修改 / 删除按项表顺序在内存里推到
最后，再对**仍存在**的 `.py` 逐件解析；删掉的件不解析。**只解析不执行**（不 import、不 eval）。

**为什么不逐条 parse**：一批里同件「先改一半、后条补另一段」的中间态暂时不完整是**正常**的，
逐条 parse 会把这种正常批误拒 ⇒ 只看**每件最终态**。

**一处实现，两处共用**：`修改.派发` 的第 ⑦ 道闸与 `批量预检.扫一遍` 都调本件 —— 不各写一套。
"""

import ast
from pathlib import Path


def 模拟最终态(工作树: Path, 项表: list) -> tuple:
    """按项表顺序在内存里推出**每件最终态** ⇒ `(最终态表, 未判)`。

    最终态表 = `{相对路径: 最终全文 或 None}`（None = 这件最终被删）。
    未判 = 这些件的模拟走不通（盘上不存在 / 找不到旧内容 / 旧内容不唯一 / 二进制）—— 它们由写口
    既有闸兜着，本闸**不替它们下判**（不猜 · 不假红）。
    """
    from .修改 import 功能_新建, 功能_修改, 功能_删除, _定位旧内容
    最终态表, 未判 = {}, set()
    for 路径, 功能号, 旧内容, 新内容 in 项表:
        if 路径 in 未判:
            continue
        if 路径 not in 最终态表:
            件路径 = 工作树 / 路径
            try:
                全文 = 件路径.read_text(encoding="utf-8", newline="\n") if 件路径.is_file() else None
            except (UnicodeDecodeError, OSError):
                未判.add(路径)
                continue
            最终态表[路径] = 全文
        全文 = 最终态表[路径]
        if 功能号 == 功能_新建:
            if 全文 is not None:
                未判.add(路径)
                continue
            最终态表[路径] = 新内容 if 新内容.endswith("\n") else 新内容 + "\n"
        elif 功能号 == 功能_删除:
            if 全文 is None:
                未判.add(路径)
                continue
            最终态表[路径] = None
        else:
            if 全文 is None:
                未判.add(路径)
                continue
            位表 = _定位旧内容(全文, 旧内容)
            if len(位表) != 1:
                未判.add(路径)
                continue
            字节位置 = 位表[0]
            最终态表[路径] = 全文[:字节位置] + 新内容 + 全文[字节位置 + len(旧内容):]
    return 最终态表, 未判


def 查最终态语法(最终态表: dict) -> list:
    """对仍存在的 `.py` 最终态逐件 `ast.parse`（**只解析，不执行**）⇒ 语法条目表。

    条目 = `(相对路径, 行号, 列号, 语法说明)`；删掉的件（终态 None）与非 `.py` 跳过。
    编码头 / 合法生成宏按 Python 标准处理（交 `ast.parse`）；缩进错与非 UTF-8 字节一律报。
    """
    语法条目表 = []
    for 路径, 全文 in sorted(最终态表.items()):
        if 全文 is None or not 路径.endswith(".py"):
            continue
        try:
            ast.parse(全文, filename=路径)
        except SyntaxError as 语法错:
            语法条目表.append((路径, 语法错.lineno or 0, 语法错.offset or 0, 语法错.msg))
        except ValueError as 值错:
            语法条目表.append((路径, 0, 0, str(值错)))
    return 语法条目表


def 排语法条目(语法条目表: list) -> str:
    """把语法条目排成按件分组的多行文本 ⇒ 每行「  件:行:列 · 原因」。"""
    return "\n".join("  %s:%d:%d · %s" % (路径, 行号, 列号, 语法说明)
                     for 路径, 行号, 列号, 语法说明 in sorted(set(语法条目表)))
