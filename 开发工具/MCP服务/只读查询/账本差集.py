# -*- coding: utf-8 -*-
r"""账本差集 —— `v1_db` 的只读操作：比**盘上账本** schema 与**主干代码建表语句**的差集，
并尽量给出「这一列 / 这一表来自哪条未合腿」。

**为什么要有它**（只读审计暴露：核对者会把漂移当主干事实）：盘上 `开工账本.db` 会漂出主干代码
建表语句里没有的列 / 表（来自未合腿的 `create table` / `alter table … add column`）。此前只能逐表
`pragma` 手看、再靠人脑猜是哪条腿加的。本件一次给：多 / 少表 · 多 / 少列 · 逐项**来源开工号**
（用 `git log -S` 找引入该字符串的未合腿；给不出就如实说「未归因」，**不许猜**）。

**只读**：盘上库一律 `mode=ro` 连；主干一侧只 `git show` 读源码文本 + `ast` 取**字符串字面量**
（**只解析不执行**）。不建库、不迁移、不写源库。
"""
import ast
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # 开发工具/

from 运行数据根 import 无位置, 子目录路径, 解析当前环境            # noqa: E402
from .仓状态 import 参数错, 取记录条数, 拒未知, 收尾, 主干引用, 跑git, 声明键集  # noqa: E402

# 盘上账本库名 → 声明它的模块件（相对仓根）。加新账本在这里添一行即可。
账本件表 = (
    ("开工账本.db", "开发工具/MCP服务/开工账本.py"),
    ("作业账本.db", "开发工具/MCP服务/作业账本.py"),
)
# `create table if not exists <名> ( <字段体> )` —— 表名与字段体（贪婪到最后一个右括号）。
建表模式 = re.compile(
    r"create\s+table\s+if\s+not\s+exists\s+([A-Za-z0-9_\u4e00-\u9fff]+)\s*\((.*)\)", re.S | re.I)
# `alter table <名> add column <列>` —— 老库补列迁移。
补列模式 = re.compile(
    r"alter\s+table\s+([A-Za-z0-9_\u4e00-\u9fff]+)\s+add\s+column\s+([A-Za-z0-9_\u4e00-\u9fff]+)", re.I)
开工号模式 = re.compile(r"v1-[0-9]{6}")
# 表级子句首词：不算列（主键 / 唯一 / 外键 / 约束 / 检查）。
子句首词 = ("primary", "unique", "foreign", "constraint", "check")
# 一次差集最多跑几次归因搜索（每条一次 git 子进程 ⇒ 防同步口被拖长）。
归因上限 = 12


def _拆列(字段体: str) -> list:
    """`create table (…)` 的字段体 ⇒ 列名表：**按顶层逗号**拆（尊重括号嵌套），再跳过表级子句
    （`primary key (开工号, 路径)` 那类 —— 它的逗号在括号里，不会被拆开）。"""
    段表, 深度, 起点 = [], 0, 0
    for 当前下标, 遍历字符 in enumerate(字段体):
        if 遍历字符 == "(":
            深度 += 1
        elif 遍历字符 == ")":
            深度 -= 1
        elif 遍历字符 == "," and 深度 == 0:
            段表.append(字段体[起点:当前下标])
            起点 = 当前下标 + 1
    段表.append(字段体[起点:])
    列名表 = []
    for 当前段 in 段表:
        当前段 = 当前段.strip()
        if not 当前段:
            continue
        首词 = re.split(r"\s+", 当前段, 1)[0].strip().strip('"`[]')
        if 首词.lower() in 子句首词:
            continue
        列名表.append(首词)
    return 列名表


def _声明结构(源码文本: str) -> dict:
    """从模块源码取**声明结构** `{表名: [列名…]}`：吃字符串字面量里的 `create table` 段与
    `alter table … add column`（`_补列` 迁移）。**只解析不执行**（`ast` 只取常量）。"""
    结构: dict = {}
    try:
        语法树 = ast.parse(源码文本)
    except SyntaxError:
        return 结构
    for 节点 in ast.walk(语法树):
        if not (isinstance(节点, ast.Constant) and isinstance(节点.value, str)):
            continue
        字面文本 = 节点.value
        建表命中 = (建表模式.match(字面文本.strip())
                if re.match(r"\s*create\s+table", 字面文本, re.I) else None)
        if 建表命中:
            结构[建表命中.group(1)] = _拆列(建表命中.group(2))
        for 表名, 列名 in 补列模式.findall(字面文本):
            结构.setdefault(表名, [])
            if 列名 not in 结构[表名]:
                结构[表名].append(列名)
    return 结构


def _盘上结构(库件: Path) -> tuple:
    """只读打开盘上账本 ⇒ `({表名: [列名…]}, 错误)`；库不在 / 读不动如实说，不假装空。"""
    try:
        连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    except sqlite3.Error as 错误:
        return {}, "盘上账本打不开：%s" % 错误
    try:
        结构: dict = {}
        for (表名,) in 连接.execute(
                "select name from sqlite_master where type='table' and name not like 'sqlite_%' "
                "order by name"):
            结构[表名] = [字段[1] for 字段 in 连接.execute(
                'pragma table_info("%s")' % 表名.replace('"', '""'))]
        return 结构, ""
    except sqlite3.Error as 错误:
        return {}, "盘上账本读不动：%s" % 错误
    finally:
        连接.close()


def 表差集(盘上: dict, 声明: dict) -> dict:
    """**纯函数**：盘上相对声明的 schema 差集 ⇒ `{多表, 缺表, 多列, 缺列}`（都排好序）。

    `多` = 盘上有、声明没有（未合腿的漂移）；`缺` = 声明有、盘上没有（老库缺迁移）。
    """
    多表 = sorted(set(盘上) - set(声明))
    缺表 = sorted(set(声明) - set(盘上))
    多列, 缺列 = {}, {}
    for 表名 in sorted(set(盘上) & set(声明)):
        多出来的 = sorted(set(盘上[表名]) - set(声明[表名]))
        短少的 = sorted(set(声明[表名]) - set(盘上[表名]))
        if 多出来的:
            多列[表名] = 多出来的
        if 短少的:
            缺列[表名] = 短少的
    return {"多表": 多表, "缺表": 缺表, "多列": 多列, "缺列": 缺列}


def _归因(仓根, 标签: str, 漂移类别: str) -> list:
    """在 `开发工具/MCP服务/` 面里找**引入** `标签` 的未合腿 ⇒ 去重开工号表（给不出 ⇒ 空表）。

    `漂移类别` = 表 / 列：表用 `create table if not exists <标签>` 当搜索串，列用 `add column <标签>`。
    只收 `腿/*` 与 `origin/腿/*` 的 ref（**未合腿**）；别的 ref 不算来源。找不到就空表 —— 调用方
    如实报「未归因」，**不许猜**。
    """
    令牌 = "create table if not exists %s" % 标签 if 漂移类别 == "表" else "add column %s" % 标签
    退出码, 输出文本 = 跑git(仓根, ["log", "--all", "--source", "--format=%S",
                              "-S" + 令牌, "--", "开发工具/MCP服务/"])
    if 退出码 != 0:
        return []
    号表 = []
    for 源码行 in 输出文本.splitlines():
        源码行 = 源码行.strip()
        if not (源码行.startswith("refs/heads/腿/") or 源码行.startswith("refs/remotes/origin/腿/")):
            continue
        建表命中 = 开工号模式.search(源码行)
        if 建表命中 and 建表命中.group(0) not in 号表:
            号表.append(建表命中.group(0))
    return sorted(号表)


def 账本差集(仓根, 参数表) -> tuple:
    """`v1_db` 的 `账本差集` ⇒ `(退出码, 文本)`。**只读**（盘上库只读连、源码只解析）。"""
    from ..工具声明.操作_账本差集 import 操作表
    拒未知(参数表, 声明键集(操作表, "账本差集", 并入开工=True))
    记录条数 = 取记录条数(参数表)
    基准 = 主干引用(仓根)
    try:
        账本目录 = 子目录路径(解析当前环境(), "数据库")
    except 无位置 as 错误:
        return 1, "盘上账本落点解析不出：%s" % 错误
    行表 = ["基准 %s · 盘上 %s（只读）" % (基准 or "读不出", 账本目录)]
    漂移总数 = 0
    归因次数 = 0
    for 库名, 件路径 in 账本件表:
        行表.append("【%s】声明件 %s" % (库名, 件路径))
        if not 基准:
            行表.append("  未判：主干引用读不出 ⇒ 声明侧无从取")
            continue
        盘上, 错误 = _盘上结构(账本目录 / 库名)
        if 错误:
            行表.append("  " + 错误)
            continue
        退出码, 源码文本 = 跑git(仓根, ["show", "%s:%s" % (基准, 件路径)])
        if 退出码 != 0:
            行表.append("  声明侧取不到（%s 下没有该件）：%s" % (基准, 源码文本.strip()[-160:]))
            continue
        声明 = _声明结构(源码文本)
        差集 = 表差集(盘上, 声明)
        if not (差集["多表"] or 差集["缺表"] or 差集["多列"] or 差集["缺列"]):
            行表.append("  无漂移（盘上 %d 表与主干建表语句一致）" % len(盘上))
            continue
        行表.append("  表：盘上 %d · 声明 %d · 多 %d · 少 %d"
                % (len(盘上), len(声明), len(差集["多表"]), len(差集["缺表"])))
        漂移总数 += (len(差集["多表"]) + len(差集["缺表"])
                 + sum(len(值表) for 值表 in 差集["多列"].values())
                 + sum(len(值表) for 值表 in 差集["缺列"].values()))
        for 表名 in 差集["多表"][:记录条数]:
            号表 = []
            if 归因次数 < 归因上限:
                归因次数 += 1
                号表 = _归因(仓根, 表名, "表")
            行表.append("    多表 %s  ← %s" % (表名, "、".join(号表) or "未归因"))
        for 表名 in 差集["缺表"][:记录条数]:
            行表.append("    缺表 %s（主干有、盘上没有 ⇒ 老库缺迁移）" % 表名)
        for 表名, 列名表 in sorted(差集["多列"].items()):
            for 列名 in 列名表[:记录条数]:
                号表 = []
                if 归因次数 < 归因上限:
                    归因次数 += 1
                    号表 = _归因(仓根, 列名, "列")
                行表.append("    多列 %s.%s  ← %s" % (表名, 列名, "、".join(号表) or "未归因"))
        for 表名, 列名表 in sorted(差集["缺列"].items()):
            for 列名 in 列名表[:记录条数]:
                行表.append("    缺列 %s.%s（主干有、盘上没有）" % (表名, 列名))
    行表.append("漂移项 %d（多表 / 多列 / 缺表 / 缺列；判据：盘上 schema 相对主干代码建表语句）" % 漂移总数)
    return 0, 收尾(行表)
