# -*- coding: utf-8 -*-
"""判据 62：顶层模块名必有导入 —— 用了 `模块.` 就必须 import 过它。

★ 2026-10-10（华哥口径）：**同类错误出现 2 次以上，就该单拉一个节点管它**，不在原地再修一次；
而且抽了节点还要**全项目扫同类落点并全部同步到该节点**，不能只看眼前一处。
本条收的正是那类重复错误：改了 `.py` 用了 `os.` / `sys.` 却没补 import ⇒ 只有跑到那一行才
`NameError`（实测两次：`shell.py` 缺 `sys`、三个命令行入口缺 `os`）—— 编译自检抓不到
（语法合法），闸 0 其它判据也不看，一路漏到长样本里才炸。

**用 AST 而不是正则**：正则版本实测在 571 件里报出 35 处，**全是假的**（字符串/注释里出现模块名）；
AST 天然只看真代码。

**只判「标准库模块名」**（名单见下）：项目内模块走点号路径（`开发工具.MCP服务.作业`），
不以单名出现 ⇒ 天然不误报；把项目模块名混进来会随仓长大而漂。

**口径**：`ast.Attribute` 的 `value` 是 `ast.Name`、名字在标准模块名单里、且该名**不在**本件的
任何 `import` 绑定里（含函数内 import 与 `as` 别名）⇒ 报。
**不命中**：`import os` 过 · `from os import path` 过 · 字符串/注释里的模块名 · 语法错的件
（另有判据管语法）。同名局部变量（`os = 某对象`）会误报 —— 本仓 0 处，不设豁免表（免得变成第二个事实源）。

依据：华哥 2026-10-10「你同样的错误，如果出现 2 次，预计你要看看是不是单拉一个节点来处理了」·
「而且可能会扩展，例如说，整个项目，还有没有其他的地方，会出现这个问题的。同步全部引用或者使用这个节点」。
"""
from __future__ import annotations

import ast

from .验证小工具 import 判不了, 违规
from .常量 import 检查名

# 标准库模块名单（**唯一主人**）：只有这些名字被 `.` 访问时才判。
_标准模块名 = frozenset({
    "os", "sys", "re", "subprocess", "json", "shutil", "tempfile", "threading", "pathlib",
    "ast", "time", "math", "hashlib", "unicodedata", "collections", "functools", "itertools",
    "typing", "copy", "struct", "glob", "socket", "urllib", "base64", "sqlite3", "datetime",
    "random", "string", "io", "contextlib", "dataclasses", "enum", "inspect", "traceback",
    "platform", "signal", "stat", "textwrap", "uuid", "zipfile", "tarfile", "csv", "difflib",
    "pprint", "warnings", "abc", "concurrent", "multiprocessing", "queue", "select",
    "selectors", "ssl", "http", "email", "html", "xml", "logging", "getpass", "argparse",
    "configparser", "pickle", "zlib", "gzip", "bz2", "lzma", "hmac", "secrets", "statistics",
    "decimal", "fractions", "numbers", "array", "bisect", "heapq", "weakref", "types",
    "operator", "keyword", "token", "tokenize", "dis", "compileall", "py_compile", "pkgutil",
    "importlib", "runpy", "sysconfig", "builtins", "shlex", "unittest",
})


def 扫顶层模块名(件表: dict) -> list:
    """扫一遍（原文 AST 解析）⇒ 命中清单：`(路径, 行号, 模块名)`。

    ★ 这里必须用**原文**而不是去串后的生产区文本：去串会破坏语法，`ast.parse` 直接抛。
    """
    输出缓冲 = []
    for 键名 in sorted(件表):
        源文本 = 件表[键名]
        if not 源文本 or not 键名.endswith(".py"):
            continue
        try:
            语法树 = ast.parse(源文本)
        except (SyntaxError, ValueError):
            continue
        已绑定名 = set()
        for 节点 in ast.walk(语法树):
            if isinstance(节点, ast.Import):
                for 导入别名 in 节点.names:
                    已绑定名.add((导入别名.asname or 导入别名.name).split(".")[0])
            elif isinstance(节点, ast.ImportFrom):
                for 导入别名 in 节点.names:
                    if 导入别名.name != "*":
                        已绑定名.add(导入别名.asname or 导入别名.name)
        for 节点 in ast.walk(语法树):
            if isinstance(节点, ast.Attribute) and isinstance(节点.value, ast.Name):
                模块名 = 节点.value.id
                if 模块名 in _标准模块名 and 模块名 not in 已绑定名:
                    输出缓冲.append((键名, 节点.lineno, 模块名))
    return 输出缓冲


_顶层模块名面缓存: dict = {}


def 顶层模块名面(上层读数: dict) -> dict:
    """扫描面：全仓 `.py` 的**原文**（AST 要完整源码）。"""
    键名 = str(上层读数["仓根"])
    if 键名 in _顶层模块名面缓存:
        return _顶层模块名面缓存[键名]
    扫描面表 = {
        键_件: 文件项["文本"]
        for 键_件, 文件项 in 上层读数["文件"].items()
        if 文件项.get("文本") is not None and 键_件.endswith(".py")
    }
    _顶层模块名面缓存[键名] = 扫描面表
    return 扫描面表


def 样本_顶层模块名(上层读数: dict) -> int:
    """对象数：扫描面下的 `.py` 件数（0 ⇒ 未判）。"""
    return len(顶层模块名面(上层读数))


def 检查62_顶层模块名必有导入(上层读数: dict) -> list:
    """全仓 `.py` 里 0 处「用了标准库模块名却没导入它」。"""
    if 样本_顶层模块名(上层读数) == 0:
        判不了(检查名[56], "（全仓）",
              "扫描面 0 件 `.py` ⇒ 空集不算通过（空集不是「没问题」，是「这条判据这次没量到东西」）",
              "确认传进来的仓根是不是真的仓根（`上层读数[\"仓根\"]` 指到空目录时就会这样）")
        return []
    return [
        违规(检查名[56], "%s:%d" % (路径, 号值),
             "用了 `%s.` 但本件没有导入 `%s`：编译自检抓不到（语法合法），只有跑到那一行才 `NameError` "
             "—— 实测两次都是这样漏到长样本里才炸" % (模块名, 模块名),
             "在文件顶部补 `import %s`（只在某个函数里用就在该函数内补），别靠别的模块传递导入" % 模块名)
        for 路径, 号值, 模块名 in 扫顶层模块名(顶层模块名面(上层读数))
    ]
