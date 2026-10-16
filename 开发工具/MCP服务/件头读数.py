# -*- coding: utf-8 -*-
"""件头读数 —— `v1_tree` 的 `件头` 操作：一次吐一个目录树的 `路径::符号::行数`。

**为什么要有它**（多腿实测）：摸一个目录里各件「多少行、有哪些顶层符号」现在要逐件 Read +
`wc -l` + `grep '^def'`，多腿实测 ≈10 次 Read 加 ≈10 次 ls/wc/grep。本件把它收成**一屏只读回执**，
替掉那串逐文件往返。只读零写：读工作树走盘上件、读引用走 git 对象（复用 `跨树` 的定位与读件）。
"""
import ast
import re

from .仓状态 import 参数错, 取开工号, 收尾, 跑git
from .跨树 import _定位, _定位当前树, _件文, _头行, 取记录条数

符号上限 = 12
列件上限 = 80
# 类型脚本件（`.rs`）的顶层符号形；只收这几类带名字的定义（宁漏不假红）。
类型符号形 = re.compile(
    r"^[ \t]*(?:pub(?:\([^)\n]*\))?[ \t]+)?(?:async[ \t]+)?(?:unsafe[ \t]+)?"
    r"(?:extern[ \t]+\"[^\"]*\"[ \t]+)?(fn|struct|enum|trait|impl|mod|const|static|type)"
    r"[ \t]+([A-Za-z_][A-Za-z0-9_]*)", re.M)


def 取件符号(路径: str, 全文: str) -> str:
    """按后缀取件内顶层符号 ⇒ `名 · 名`（超 `符号上限` 截断）；不认识的件 ⇒ `—`。"""
    if 路径.endswith(".py"):
        try:
            语法树 = ast.parse(全文)
        except (SyntaxError, ValueError):
            return "（语法读不出）"
        名表 = []
        for 语句 in 语法树.body:
            if isinstance(语句, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                名表.append(语句.name)
            elif isinstance(语句, ast.Assign):
                for 赋值项 in 语句.targets:
                    if isinstance(赋值项, ast.Name):
                        名表.append(赋值项.id)
        return 排符号(名表)
    if 路径.endswith(".rs"):
        return 排符号([符号名 for 符号类名, 符号名 in 类型符号形.findall(全文)])
    return "—"


def 排符号(名表: list) -> str:
    """去重保序、按 `符号上限` 截断 ⇒ `名 · 名`（空 ⇒ `（无顶层符号）`）。"""
    收表 = list(dict.fromkeys(名表))
    if not 收表:
        return "（无顶层符号）"
    if len(收表) > 符号上限:
        return " · ".join(收表[:符号上限]) + " …（共 %d）" % len(收表)
    return " · ".join(收表)


def 列件头(仓根, 参数表) -> tuple:
    """一个目录树的 `路径::符号::行数` 一屏（只读零写；`路径前缀` 定范围，`条数` 有界）。

    **默认读「当前树」**（`仓根` 的工作树，含未跟踪）—— 本操作是「一屏摸我正在改的这棵树」；
    与 `跨树` 其余操作「不给就主干」不同（主干树里看不到本腿新件）。给了 `开工ID` 或 `引用`
    则照 `跨树` 口径定位。
    """
    记录条数 = 取记录条数(参数表, 默认=列件上限, 硬顶=列件上限)
    路径前缀 = str(参数表.get("路径前缀") or "").strip()
    开工号 = 取开工号(参数表)
    引用 = str(参数表.get("引用") or "").strip()
    if 开工号 or 引用:
        定位, 错误 = _定位(仓根, 开工号, 引用)
    else:
        定位, 错误 = _定位当前树(仓根)
    if 错误:
        return 1, 错误
    命令 = (["ls-tree", "-r", "--name-only", 定位["引用"]] if 定位["引用"]
          else ["ls-files", "--cached", "--others", "--exclude-standard"])
    退出码, 输出文本 = 跑git(仓根, 命令, 树根=定位["树根"])
    if 退出码 != 0:
        return 1, "\n".join(_头行(定位) + ["列件失败：%s" % 输出文本.strip()[-200:]])
    # `路径前缀` = **前缀**（不是 git pathspec 的精确路径）：`ls-files`/`ls-tree` 对无通配路径按**精确**匹配
    # （`.../件头读数` 命中 0 件），且 `ls-tree` 不吃 `:(glob)` magic ⇒ 列全名后在 Python 侧按前缀筛
    # （两种树同一口径）
    名表 = [源码行 for 源码行 in 输出文本.splitlines()
          if 源码行.strip().endswith((".py", ".rs")) and 源码行.strip().startswith(路径前缀)]
    行表 = _头行(定位)
    行表.append("源码件 %d 个（.py/.rs；%s）· 符号上限 %d"
             % (len(名表), "引用树" if 定位["引用"] else "工作树（含未跟踪）", 符号上限))
    for 路径 in 名表[:记录条数]:
        全文, 读错说明 = _件文(仓根, 定位, 路径)
        if 读错说明:
            行表.append("  %s::（读不出：%s）" % (路径, 读错说明))
            continue
        行表.append("  %s::%s::%d 行" % (路径, 取件符号(路径, 全文), len(全文.split("\n"))))
    if len(名表) > 记录条数:
        行表.append("  …（还有 %d 个件，收窄 `路径前缀` 或调 `条数`）" % (len(名表) - 记录条数))
    return 0, 收尾(行表)
