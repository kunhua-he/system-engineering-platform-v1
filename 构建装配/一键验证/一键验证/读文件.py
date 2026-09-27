# -*- coding: utf-8 -*-
"""并行读全仓 + 建上下文（文件表 · 包到层映射 · 仓根）。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from pathlib import Path

from . import 常量

from .小工具 import 是临时路径, 相对
from .常量 import 临时目录前缀, 号段图路径, 契约目录名, 常量表路径, 并发度, 扫描后缀, 编号字段, 编号目录, 跳过目录, 顶层目录到层
from .测试件 import 建测试文件集


def 扫源文件(仓根: Path) -> list:
    """全仓源码文件（跳过生成物与参照物目录）。"""
    结果 = []
    for 根, 目录表, 文件表 in os.walk(仓根):
        目录表[:] = [
            目录名
            for 目录名 in 目录表
            if 目录名 not in 跳过目录 and not 目录名.startswith(常量.临时目录前缀)
        ]
        for 名 in 文件表:
            if 名.endswith(扫描后缀):
                结果.append(Path(根) / 名)
    return 结果


# ════════════════════════════════════════════════════════════════════════════
# ① 并行读（IO 密集 · 按文件分片 · 32 路）
# ════════════════════════════════════════════════════════════════════════════


def 读一个文件(任务: tuple) -> tuple:
    """一个分片的全部重活：读字节 → 解 UTF-8 → 解 JSON。都在这里做，并行跑。"""
    仓根, 路径 = 任务
    键 = 相对(仓根, 路径)
    try:
        字节 = 路径.read_bytes()
    except OSError as 错:
        return 键, {"文本": None, "数据": None, "错误": f"读不动：{错}"}
    try:
        文本 = 字节.decode("utf-8")
    except UnicodeDecodeError as 错:
        return 键, {"文本": None, "数据": None, "错误": f"不是 UTF-8：{错}"}
    数据 = None
    错 = None
    if 路径.suffix == ".json":
        try:
            数据 = json.loads(文本)
        except json.JSONDecodeError as 解析错:
            return 键, {"文本": 文本, "数据": None, "错误": f"JSON 解析失败：{解析错}"}
        if not isinstance(数据, dict):
            return 键, {
                "文本": 文本,
                "数据": None,
                "错误": f"顶层不是对象（是 {type(数据).__name__}）",
            }
    return 键, {"文本": 文本, "数据": 数据, "错误": 错}


def 并行读(仓根: Path, 路径表: list) -> dict:
    任务 = [(仓根, 路径) for 路径 in 路径表]
    with ThreadPoolExecutor(max_workers=并发度) as 池:
        return dict(池.map(读一个文件, 任务))


def 建上下文(仓根: Path) -> dict:
    契约根 = 仓根 / 契约目录名
    # 一次扫全，按文件分片并行读（读 + 解 UTF-8 + 解 JSON 都在分片里）；
    # 后面所有检查都在内存里做，不再回磁盘。
    契约件 = sorted(契约根.rglob("*.json")) if 契约根.is_dir() else []
    # `rglob` 不走 `跳过目录` / 临时件排除 ⇒ 这里按同一口径再筛一遍
    # （否则落进 `契约声明/` 的临时声明根仍会被读进来）。
    契约件 = [声明件 for 声明件 in 契约件 if not 是临时路径(相对(仓根, 声明件))]
    源件 = [源路径 for 源路径 in 扫源文件(仓根) if 源路径.suffix != ".json"]
    文件 = 并行读(仓根, 契约件 + 源件)

    平台 = 解析(文件, f"{契约目录名}/平台声明.json")
    号段图 = 解析(文件, 号段图路径)
    常量表 = 解析(文件, 常量表路径)
    作废 = 解析(文件, f"{契约目录名}/作废号表.json")
    冻结 = 解析(文件, f"{契约目录名}/冻结登记.json")

    编号表 = {}
    目录存在 = {}
    for 目录 in 编号目录:
        目录存在[目录] = (契约根 / 目录).is_dir()
        记录表 = []
        前缀 = f"{契约目录名}/{目录}/"
        for 键 in sorted(文件):
            if not 键.startswith(前缀) or not 键.endswith(".json"):
                continue
            记录表.append(
                {
                    "目录": 目录,
                    "文件名": 键.rsplit("/", 1)[1],
                    "键": 键,
                    "字段": 编号字段[目录],
                    "数据": 文件[键]["数据"],
                    "错误": 文件[键]["错误"],
                }
            )
        编号表[目录] = 记录表

    return {
        "仓根": 仓根,
        "文件": 文件,
        "平台": 平台,
        "号段图": 号段图,
        "常量表": 常量表,
        "作废": 作废,
        "冻结": 冻结,
        "编号表": 编号表,
        "编号目录存在": 目录存在,
        "包到层": 建包到层映射(文件),
        "测试文件集": 建测试文件集(文件),
    }


def 建包到层映射(文件: dict) -> dict:
    """Cargo 包名 → 层。包名里的 `-` 换成 `_`（Rust 的 `use` 用下划线）。"""
    表 = {}
    for 键, 项 in 文件.items():
        if not 键.endswith("Cargo.toml") or 项["文本"] is None:
            continue
        配 = re.search(r"^\s*name\s*=\s*\"([^\"]+)\"", 项["文本"], re.M)
        if not 配:
            continue
        层 = 路径到层(键)
        if 层:
            表[配.group(1).replace("-", "_")] = 层
    return 表


def 路径到层(键: str) -> str:
    头 = 键.split("/", 1)[0]
    return 顶层目录到层.get(头, "")


def 解析(文件: dict, 键: str):
    项 = 文件.get(键)
    return None if 项 is None else 项["数据"]


# ════════════════════════════════════════════════════════════════════════════
# 合成索引：给 `--自测` 的合成仓挂一份索引库（#225 的硬约束）
# ════════════════════════════════════════════════════════════════════════════
#
# **为什么必须要有它**：判据 ㉒ 的面已换成**代码地图索引**（读法见
# `开发工具/代码地图/索引库.全部定义`）。而索引是**整仓产出**的（`codegraph init <仓根>`）
# ⇒ `--自测` 的临时夹具仓没有索引 ⇒ 判据在夹具上会永远「未判」，而正向样本要求
# 「干净夹具上所有判据通过」—— 两者直接矛盾。解得开的那一步就是把「面」与「索引从哪来」
# **拆开**：真仓读真索引（tree-sitter 出的，最准），夹具仓读本件造的合成索引。
#
# ★ **合成索引的节点从哪来**（诚实登记）：夹具仓没有 tree-sitter 那份解析，所以合成索引由
#   本仓既有的**命名扫描**剥器从夹具源文件里抽标识符得出。⇒ 它只对**夹具**成立
#   （夹具是本仓自己造的，不是用户输入）；真仓一律读真索引。这不是「两条腿」：
#   **判据的面始终是索引**、读法只有一处（`索引库.全部定义`），本件只负责把索引放到
#   那个位置，不参与任何判定。

# 库文件名与 `开发工具/代码地图/落点.py::库文件名` 同；目录名另取一个，
# **刻意不叫** `.codegraph` —— 免得将来有人把合成库当成真库读。
合成索引目录名 = "_合成索引_"
合成索引文件名 = "codegraph.db"

# codegraph 的 `nodes` 表的列（本件只写上层读得到的那几列，其余留默认）。
_合成索引建表 = (
    "create table nodes (id text, kind text, name text, qualified_name text, "
    "file_path text, language text, start_line integer, end_line integer, "
    "start_column integer, end_column integer, signature text)",
    "create table edges (source text, target text, kind text, line integer, col integer)",
)

# 后缀 → 索引器认的语言名（只为如实填 `language` 列，不参与判定）。
_合成索引语言名 = {".rs": "rust", ".py": "python", ".js": "javascript",
              ".ts": "typescript", ".tsx": "typescript", ".vue": "vue"}


def _合成索引节点(件表: dict) -> list:
    """夹具的文件表 ⇒ codegraph 形状的节点行（每个标识符一行，与真索引同粒度）。

    抽法走 `命名扫描`（与判据 ㉒ 旧面的剥器**同一套**）：真索引的 `variable` 节点就覆盖到
    「声明过的名字」，而这里的剥器抽的也正是这些 —— 两边在夹具上读数一致。
    行号从**剥后的净文本**上数（长度不变 ⇒ 行号与原文对齐）。
    """
    from .命名扫描 import _标识符, _是自身成员访问, 剥

    行表 = []
    for 键 in sorted(件表):
        文本 = 件表[键]
        if not 文本:
            continue
        后缀 = "." + 键.rsplit(".", 1)[-1]
        净 = 剥(后缀, 文本)
        for 序, 命 in enumerate(
            命 for 命 in _标识符.finditer(净)
            if not (命.start() > 0 and 净[命.start() - 1] == "."
                    and not _是自身成员访问(净, 命.start()))
        ):
            名 = 命.group(0)
            行号 = 净[: 命.start()].count("\n") + 1
            列号 = 命.start() - (净.rfind("\n", 0, 命.start()) + 1)
            行表.append((
                "variable:%s:%d" % (键, 序),
                "variable", 名, 名, 键, _合成索引语言名.get(后缀, ""),
                行号, 行号, 列号, 列号 + len(名), "",
            ))
    return 行表


def 建合成索引(仓根: Path, 件表: dict) -> Path:
    """把 `件表` 写成一份索引库 ⇒ **库路径**（`Path`）。

    `件表` 必须是**当场那一份**（`上["文件"]` 的 `{键: 文本}`）—— 不能从 `干净合成仓()`
    重取：`--自测` 的反向样本是在 `造干净仓` **之后**才往夹具里注入违规的
    （实测：重取 ⇒ 注入件不在索引里 ⇒ ㉒ 的反向样本抓不到，三条断言全红）。

    写在**仓外**（`<仓根>._合成索引_/codegraph.db`）：写进被扫的树会多出一个目录，
    那样 ⑰（临时件）与 ⑳（运行数据）会拿它当对象 —— 面被自己改了，读数就不真。
    """
    import sqlite3

    库 = Path(str(仓根) + "." + 合成索引目录名) / 合成索引文件名
    库.parent.mkdir(parents=True, exist_ok=True)
    if 库.is_file():
        库.unlink()  # 每轮重建：同一夹具被跑多次时不许读到上一轮的节点
    连接 = sqlite3.connect(str(库))
    try:
        for 语句 in _合成索引建表:
            连接.execute(语句)
        连接.executemany("insert into nodes values (?,?,?,?,?,?,?,?,?,?,?)",
                       _合成索引节点(件表))
        连接.commit()
    finally:
        连接.close()
    return 库


# 合成索引的按仓缓存（键 = 仓根路径）。**一次 `验证` 只建一次**：`上["文件"]`
# 在一次调用里不变，而 `数命中` / `命名扫描件` 会各取一次面 ⇒ 不缓存就白重建两遍。
# 不跨调用复用：`--自测` 的注入发生在两次 `验证` 之间（照 `跑一遍` 里「一次验证只读一次仓」同一理由）。
_合成索引缓存: dict = {}

# **哪些仓是夹具**（`造干净仓` 登记）。只给它们造合成索引 —— 真仓没有索引时**不许**造：
# 真仓缺索引是「代码地图没建」⇒ 那是**未判**；造一份合成索引会把真仓的符号面偷偷换掉，
# 而且会在仓外留一个 `<仓根>._合成索引_` 目录（垃圾）。夹具是**本仓自己造的**，
# 它的面由本仓包底才成立。
_夹具仓根集: set = set()


def 登记夹具仓根(仓根) -> None:
    """`造干净仓` 叫一声：这个仓是夹具（写面那一侧的**唯一**登记口）。"""
    _夹具仓根集.add(str(仓根))


def 索引路径(仓根: Path, 件表: dict) -> Path:
    """本仓**该读哪个索引**：真仓读真索引，**夹具仓**（无真索引）现场造一份合成索引。

    真库的落点是 `<被扫的仓>/.codegraph/codegraph.db`（**不是**判据自身所在那个仓的库 ——
    拿后者的库去扫夹具，读到的是真仓的符号，那是假绿）。返回 `Path`
    （`索引库.全部定义` 吃 `Path`）。

    真仓缺索引 ⇒ 返回那个**不存在的真路径**（`索引库.全部定义` 回空表 ⇒ 判据报**未判**）——
    那是诚实的读数，不是通过。不许拿合成索引顶替（那就把真仓的面换掉了）。
    """
    真库 = Path(str(仓根)) / ".codegraph" / "codegraph.db"
    if 真库.is_file():
        return 真库
    if str(仓根) not in _夹具仓根集:
        return 真库  # 真仓没索引 = 未判（调用方据空表报未判），不造合成索引
    键 = str(仓根)
    记住 = _合成索引缓存.get(键)
    if 记住 is not None and 记住.is_file():
        return 记住
    库 = 建合成索引(仓根, 件表)
    _合成索引缓存[键] = 库
    return 库
