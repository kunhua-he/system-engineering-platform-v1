# -*- coding: utf-8 -*-
"""代码地图 · 索引库 —— 读 codegraph 的 sqlite 库，转成本仓的统一形状。

**索引器是外部成熟件**：`@colbymchenry/codegraph`（npm · MIT · tree-sitter 解析 + sqlite 落库）。
本模块只做两件事：① 调它建/刷库；② 把库里的 `nodes` / `edges` 读成本仓要的形状。
**零解析逻辑**（解析归 tree-sitter，本仓不再自研剥器）。

**为什么不再用 SCIP 那套**（2026-09-27 裁决，原话「直接移除掉，替换成 codegraph 不就好了？」）：
SCIP 要四个外部工具（`rust-analyzer` / `scip-python` / `scip-typescript` / `scip`）＋ 一份
353 行前端解析器 ＋ 12.3 秒冷构建；codegraph 一条命令、**1.4 秒**、库本身就是索引。
裁决与实测见 `项目文档/决策记录/2026-09-27_代码地图换 codegraph.md`。

**★ 换过来的代价：引用面少约 7%**（实测：400 个随机符号的代码行出现位，SCIP 634 · codegraph 592）。
缺的是这四类 ——
  · `match` 模式里的枚举变体（`版本 | 支持库 | … | 子程序`）
  · 路径表达式（`行类::子程序`）
  · 方法调用（`.取文本()` · `.and_then(协议值::取文本)`）
  · 常量用在条件 / 字段初始化里（`底座宿主版本.满足(…)` · `实际: 底座宿主版本.主`）
它的 `unresolved_refs` 兜不住这些（实测漏的那几处一条都不在里面）⇒ **漏是静默的**。
故 `替换` 工具的口径是：改完**必须跑门禁编译** —— 编译不过就是「索引漏了几处」，
用 `rg` 按词边界复核。**浏览用它是够的**（谁定义了它 / 它还在哪被用），改名要拿编译兜底。

**列的口径与 SCIP 不同**（实测过，别照抄旧注释）：codegraph 的 `col` 是**字符下标**
（Python 直接切片就对）；SCIP 是 UTF-8 **字节**偏移。`替换` 的按列换吃的是本件的字符列。
"""

import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from .落点 import 库文件名, 库目录名
from .落点 import 库路径 as 默认库路径

索引器命令 = "codegraph"
# ★ **有意不设超时**（与仓里 `cargo` / `nm` / 闸 0 起子进程同一口径）：建索引是**环境步**，
#   它一趟就是它自身的长度；给它一个「容忍度」只会把五秒硬顶让给被调方。判据 ㊲ 也不许
#   任何 `超时设置 > 5 秒`（实测撞过：先写了 `建库超时秒 = 300`，门禁当场红）。
#   墙钟照实报（`建` 的返回值里有），但**不判顶** —— 判顶的是查询那三条。
# 「定义面」剔掉的两类：`file` 是件本身；`import` 是**模块绑定**（`sys` · `crate` · `std` ·
# `v1_contract`），不是作者给某个符号起的名字 —— 留着它只会让「查符号」命中一堆导入行、
# 让「检名」的西文档灌水（实测多 1901 条，全是模块名）。
非标识符种类 = ("file", "import")

_行缓存: dict = {}


# ── 库的开关与读数 ──────────────────────────────────────────────────────────────────────

def 有库() -> bool:
    return 默认库路径().is_file()


def 连库(库路径=None) -> sqlite3.Connection:
    """**只读**连库（`mode=ro`：本仓绝不写索引器的库）。

    `库路径` 给了就连那一个库 —— 一开工一工作树时，要查的必须是**那条树**的索引
    （不带就查主树）。**不许**靠改模块级状态来切库：那是隐式第二来源。
    """
    return sqlite3.connect("file:%s?mode=ro" % (库路径 or 默认库路径()), uri=True)


def 找命令() -> str:
    """索引器可执行件在不在 ⇒ 路径 或 `""`（环境依赖，不是底座能力）。"""
    return shutil.which(索引器命令) or ""


def 库读数(库路径=None) -> dict:
    """库里的节点 / 边 / 件数（库不在 ⇒ 全 0）。"""
    if not (库路径 or 默认库路径()).is_file():
        return {"节点": 0, "边": 0, "件": 0, "索引器版本": ""}
    动态库 = 连库(库路径)
    try:
        读数 = {"节点": 动态库.execute("select count(*) from nodes").fetchone()[0],
               "边": 动态库.execute("select count(*) from edges").fetchone()[0],
               "件": 动态库.execute("select count(*) from files").fetchone()[0],
               "索引器版本": ""}
        元数据行 = 动态库.execute(
            "select value from project_metadata where key='indexed_with_version'").fetchone()
        if 元数据行:
            读数["索引器版本"] = 元数据行[0]
        return 读数
    finally:
        动态库.close()


def 建索引(仓根: Path) -> tuple:
    """跑索引器全量重建 ⇒ `(退出码, 墙钟毫秒, 说明)`。属**环境步**（不判顶）。

    **库不在 ⇒ 先 `init`**：`index` 只刷已有的库，对全新目录直接报
    `✗ CodeGraph not initialized in <路径>`（退出码 1）。实测撞到两处 —— 一开工一工作树
    登记时刚建出的工作树、以及**新克隆的仓**。
    """
    命令 = 找命令()
    if not 命令:
        return 1, 0, ("代码地图：索引器 `%s` 不在（环境依赖，不是底座能力）。装法："
                    "`npm i -g @colbymchenry/codegraph`" % 索引器命令)
    库文件 = Path(仓根) / 库目录名 / 库文件名
    动作 = "index" if 库文件.is_file() else "init"
    开始时刻 = time.monotonic()
    try:
        回执 = subprocess.run([命令, 动作, str(仓根)], cwd=str(仓根),
                            capture_output=True, text=True)     # 不设超时，见 `索引器命令` 上方
    except OSError as 起不来的原因:
        return -2, 0, "代码地图：起不了索引器：%r" % (起不来的原因,)
    墙钟毫秒 = int((time.monotonic() - 开始时刻) * 1000)
    if 回执.returncode != 0:
        return 回执.returncode, 墙钟毫秒, "代码地图：索引器退出码 %d ⇒ %s" % (
            回执.returncode, (回执.stderr or 回执.stdout or "").strip()[-400:])
    读数 = 库读数()
    return 0, 墙钟毫秒, "索引 %d 节点 · %d 边 · %d 件（索引器 %s）⇒ %s" % (
        读数["节点"], 读数["边"], 读数["件"], 读数["索引器版本"] or "—", 库文件)


def 同步(仓根: Path) -> tuple:
    """增量同步（改了件之后刷索引）⇒ `(退出码, 说明)`。

    **为什么用 `sync` 不用 `index`**：实测改 1 件后 `sync` 全链 **389 ms**，`index` 要 1.0–1.4 s。
    写盘后每条改动都要刷一次（下一条改动要拿到新行号与新指纹）⇒ 这一档必须便宜。
    `仓根` 是**显式参数**：一开工一工作树时，刷的必须是那条树的索引，不是主树的。
    """
    命令 = 找命令()
    if not 命令:
        return 1, "索引器不在（`%s`）⇒ 索引没刷，下次查符号会读到旧行号" % 索引器命令
    回执 = subprocess.run([命令, "sync", str(仓根)], cwd=str(仓根),
                       capture_output=True, text=True)     # 不设超时，见 `索引器命令` 上方
    if 回执.returncode != 0:
        return 回执.returncode, (回执.stderr or 回执.stdout or "").strip()[-300:]
    return 0, "索引已同步"


def 报缺工具() -> int:
    """索引器不在 ⇒ 报装法与退法（它是**环境依赖**，不是底座能力）。"""
    if 找命令():
        return 0
    print("代码地图：索引器不在（它是**环境依赖**，不是底座能力）。缺：")
    print("  · %-16s 装法：`npm i -g @colbymchenry/codegraph`" % 索引器命令)
    print("  不装也行 —— 底座与判据面照跑（`构建装配/一键验证/` 里 0 处调它）；")
    print("  退法：删 <仓根>/.codegraph/，其余一切照跑。")
    return 1


# ── 读库：节点 → 统一形状 ────────────────────────────────────────────────────────────────

def _件行表(件路径: str) -> list:
    if 件路径 not in _行缓存:
        try:
            件文本 = Path(件路径).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            _行缓存[件路径] = []
        else:
            _行缓存[件路径] = 件文本.split("\n")
    return _行缓存[件路径]


def 名字列(件路径: str, 行号: int, 名字: str, 起始列: int) -> int:
    """**定义处**名字所在列。

    `variable` / `enum_member` / `field` 这几类，索引给的 `start_column` **就是名字起点**；
    而 `function` / `method` / `class` / `struct` / `enum` / `trait` / `constant` 给的是
    **声明起点**（Rust 里常常是 0）⇒ 得在那一行里再找一次名字。

    找法：**行内首个「独立出现」且不早于 `起始列`** 的那处。实测（3996 个节点）：
    1529 个列直接对 · 2452 个行内唯一 · 15 个行内多处 —— 那 15 处全是
    `fn 名(&self) -> 名` 这种「名字同时是返回类型」，首个出现正是要的那处。
    找不到（索引器把列报歪了）⇒ 返回 `起始列`，由调用方按位置切不动时 fail-closed。
    """
    行表 = _件行表(件路径)
    if not (1 <= 行号 <= len(行表)):
        return 起始列
    整行 = 行表[行号 - 1]
    if 整行[起始列:起始列 + len(名字)] == 名字:
        return 起始列
    起始位 = 0
    while True:
        命中位 = 整行.find(名字, 起始位)
        if 命中位 < 0:
            return 起始列
        前一位 = 整行[命中位 - 1] if 命中位 else ""
        后一位 = 整行[命中位 + len(名字)] if 命中位 + len(名字) < len(整行) else ""
        是独立 = not (前一位.isalnum() or 前一位 == "_") and not (后一位.isalnum() or 后一位 == "_")
        if 是独立 and 命中位 >= 起始列:
            return 命中位
        起始位 = 命中位 + 1


def 节点记录(一行) -> dict:
    """库里的 `nodes` 行 ⇒ 统一形状（与 SCIP 那版**同一套字段**，上层不用改）。

    `一行` = `(id, kind, name, qualified_name, file_path, start_line, end_line, start_column,
    signature, 引用数)` —— 引用数由调用方的 SQL 一并算好（别在这里单开连接：实测 5897 个节点
    逐个连库要 900 ms，一次 GROUP BY 只要 40 ms）。
    """
    标识, 种类, 名字, 限定名, 件路径, 起始行, 末行, 起始列, 声明, 引用数 = 一行
    return {
        "名字": 名字,
        "限定名": 限定名,
        "种类": 种类,
        "声明": (声明 or "").replace("\n", " ").strip()[:200],
        "路径": 件路径,
        "行": 起始行,
        "列": 名字列(件路径, 起始行, 名字, 起始列),
        "末行": 末行,
        "出现数": 引用数 + 1,
    }


_节点字段 = ("n.id, n.kind, n.name, n.qualified_name, n.file_path, n.start_line, n.end_line, "
           "n.start_column, n.signature, (select count(*) from edges e "
           "where e.target = n.id and e.kind <> 'contains')")


def 全部定义(库路径=None) -> list:
    """定义面上的全部节点（见 `非标识符种类`）⇒ 定义表。库不在 ⇒ 空表（调用方据此报「先建」）。"""
    if not (库路径 or 默认库路径()).is_file():
        return []
    动态库 = 连库(库路径)
    try:
        return [节点记录(一行) for 一行 in 动态库.execute(
            "select %s from nodes n where n.kind <> ? and n.kind <> ?" % _节点字段,
            非标识符种类)]
    finally:
        动态库.close()


# ── 读库：出现位（定义处 + 引用处）────────────────────────────────────────────────────────

def 出现数(标识: str, 库路径=None) -> int:
    """该符号的**出现数** = 定义本身 1 处 ＋ 指向它的引用边（`contains` 不算 —— 那是「件包含它」）。"""
    if not (库路径 or 默认库路径()).is_file():
        return 0
    动态库 = 连库(库路径)
    try:
        引用数 = 动态库.execute(
            "select count(*) from edges where target=? and kind<>'contains'", (标识,)).fetchone()[0]
        return 引用数 + 1
    finally:
        动态库.close()


def _源件路径(动态库: sqlite3.Connection, 来源: str) -> str:
    """边的 `source` ⇒ 件路径。`file:<路径>` 是件节点，否则是符号节点（查它的 `file_path`）。"""
    if 来源.startswith("file:"):
        return 来源[len("file:"):]
    源码行 = 动态库.execute("select file_path from nodes where id=?", (来源,)).fetchone()
    return 源码行[0] if 源码行 else ""


def 出现位(键名: str, 上限: int = 0, 库路径=None) -> dict:
    """该符号的全部出现位置 ⇒ `{"位置": [(路径, 行, 列)…], "总数": n, "口径": "…"}`。

    **口径**：先按 `限定名` **全等**找（精确）；一条都没有才退回按 `名字` 全等
    （名字级 —— 会混进同名不同符号）。用的是哪一种，如实写在 `口径` 里。
    `上限=0` 表示不限（`替换` 要全量 —— 截断会让它漏改）。

    ★ 引用面比编译器索引少约 7%（见本件顶部）⇒ 调用方**必须**拿编译兜底，别当它全。
    """
    if not (库路径 or 默认库路径()).is_file():
        return {"位置": [], "总数": 0, "口径": "没有索引"}
    动态库 = 连库(库路径)
    try:
        for 匹配列, 口径说明 in (("qualified_name", "限定名（精确）"),
                                ("name", "名字（同名不同符号会混进来）")):
            节点行表 = list(动态库.execute(
                "select id, name, file_path, start_line, start_column from nodes where %s = ?"
                % 匹配列, (键名,)))
            if not 节点行表:
                continue
            位置表 = []
            for 标识, 名字, 件路径, 行号, 起始列 in 节点行表:
                位置表.append((件路径, 行号, 名字列(件路径, 行号, 名字, 起始列)))
                for 来源, 边行, 边列 in 动态库.execute(
                        "select source, line, col from edges "
                        "where target=? and kind<>'contains' and line is not null", (标识,)):
                    源件 = _源件路径(动态库, 来源)
                    if 源件:
                        位置表.append((源件, 边行, 边列))
            去重表 = sorted(set(位置表))
            if 上限:
                去重表 = 去重表[:上限]
            return {"位置": 去重表, "总数": len(set(位置表)), "口径": 口径说明}
        return {"位置": [], "总数": 0, "口径": "没找到"}
    finally:
        动态库.close()
