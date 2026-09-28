#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息核心 · 建库 —— 确保表齐 · 派生表刷新 · 源表只填空的。

用法：
    python3 开发工具/信息核心/信息核心.py 建库           # 建库 / 刷新（秒级）
    python3 开发工具/信息核心/信息核心.py 建库 --读数     # 建完打每张表的行数

**库是源**（`开发工具/信息核心/信息核心.db`，仓内）：md 全删之后，`规则` · `条款` · `未完成` ·
`命名定义` · `命名模式` 的事实只住在库里 ⇒ 这几张（`表定义.源表`）**只填空表，不覆盖**。

**派生表**（`代码名` · `节点` · `连接` 出自代码地图索引；`能力` · `能力参数` · `类型` · `错误码`
出自 `契约声明/`；`文档` 出自 `文档账本.json`）每次重抽 —— 它们是查询缓存，不是源。
"""
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(仓根))
sys.path.insert(0, str(仓根 / "开发工具"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402

# 三张「一次扫描 → 多张表」的中间结果缓存：`装X定义`/`装X模式` 两个入口共用一次解析。
_命名缓存: dict = {}
_拓扑缓存: dict = {}
_契约缓存: dict = {}


# ── 通用 ───────────────────────────────────────────────────────────
def 读JSON(路径: Path):
    try:
        return json.loads(路径.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def 读文本(路径: Path) -> str:
    try:
        return 路径.read_text(encoding="utf-8")
    except OSError:
        return ""


def 扫md(根目录: Path) -> list:
    跳过 = {"构建环境", "只读参考", ".git", ".codegraph", "__pycache__", "node_modules", "target"}
    结果 = []
    for 路径 in 根目录.rglob("*.md"):
        if any(路径段 in 跳过 for 路径段 in 路径.relative_to(根目录).parts):
            continue
        结果.append(路径.relative_to(根目录).as_posix())
    return sorted(结果)


# ── 规则：从各规范件的表 / 编号列表里抽 ─────────────────────────────
表头词 = {"#", "层", "原则", "语义", "种类", "规则", "不做", "问", "档", "条", "腿", "工具", "判据", "形式", "单元"}


def 取节(文本: str, 前缀: str) -> list:
    输出行, 在内 = [], False
    for 一行 in 文本.splitlines():
        if 一行.startswith("## "):
            在内 = 一行.startswith(前缀)
            continue
        if 在内:
            输出行.append(一行)
    return 输出行


def 抽规则(类别: str, 文本: str, 前缀: str, 形式: str) -> list:
    节行 = 取节(文本, 前缀)
    结果行 = []
    序号 = 0
    if 形式 == "table":
        for 一行 in 节行:
            条目 = 一行.strip()
            if not 条目.startswith("|"):
                continue
            格表 = [格值.strip() for 格值 in 条目.strip("|").split("|")]
            if not 格表 or set("".join(格表)) <= set("-: "):
                continue
            if 格表[0] in 表头词:
                continue
            序号 += 1
            规则名 = 格表[0] if len(格表) > 1 else ""
            内容 = " · ".join(格值 for 格值 in 格表[1:] if 格值)
            if 内容:
                结果行.append((f"{类别}-{序号}", 类别, 规则名, 内容, f"{前缀}（表行）"))
    else:
        for 一行 in 节行:
            匹配 = re.match(r"^\s*(\d+)\.\s+(.*)$", 一行)
            if not 匹配:
                continue
            序号 += 1
            正文 = 匹配.group(2).strip()
            规则名 = 匹配.group(1)
            标题匹配 = re.match(r"^\*\*(.+?)\*\*[。：—\s]*(.*)$", 正文)
            if 标题匹配:
                规则名, 正文 = 标题匹配.group(1), (标题匹配.group(2).strip() or 标题匹配.group(1))
            结果行.append((f"{类别}-{序号}", 类别, 规则名[:60], 正文[:2000],
                          f"{前缀}（编号 {匹配.group(1)}）"))
    return 结果行


def 装规则(根目录: Path) -> list:
    输出行 = []
    for 类别, 件名, 前缀, 形式名 in 表定义.规则来源:
        输出行 += 抽规则(类别, 读文本(根目录 / 件名), 前缀, 形式名)
    return 输出行


# ── 其余各表 ──────────────────────────────────────────────────────
def 装条款(根目录: Path, 文档行: list) -> list:
    """全部 md 的正文入库：一行一节（以 `# ` / `## ` 为界）。

    这是「md 只留索引」的**载荷步骤**：正文进了库，原件才可删。所以它跑在 `装文档` 之后 ——
    档位从 `文档` 表继承（账本定档），不另判一次。
    """
    输出行 = []
    for 文档路径, 档位, _表达 in 文档行:
        for 节号, (节标题, 节正文) in enumerate(拆节(读文本(根目录 / 文档路径))):
            输出行.append((文档路径, 节号, 节标题, 节正文, 档位))
    return 输出行


def 拆节(文本: str) -> list:
    """md → `[(节标题, 节正文)]`。`# ` 与 `## ` 都是界（`###` 及以下归上一节）。"""
    节表, 节标题, 缓冲 = [], "", []
    for 一行 in 文本.splitlines():
        if 一行.startswith("# ") or 一行.startswith("## "):
            节表.append((节标题, "\n".join(缓冲).strip()))
            节标题, 缓冲 = 一行.lstrip("#").strip(), []
        else:
            缓冲.append(一行)
    节表.append((节标题, "\n".join(缓冲).strip()))
    return [(节题, 节体) for 节题, 节体 in 节表 if 节题 or 节体]


def 装文档(根目录: Path) -> list:
    账本 = 读JSON(根目录 / "项目文档" / "文档账本.json") or {}
    显式 = {}
    for 条目 in 账本.get("件") or []:
        if isinstance(条目, dict) and isinstance(条目.get("路径"), str):
            显式[条目["路径"]] = 条目
    定档规则 = [
        条目 for 条目 in (账本.get("按路径定档") or [])
        if isinstance(条目, dict) and isinstance(条目.get("前缀"), str)
    ]
    输出行 = []
    for 文档路径 in 扫md(根目录):
        if 文档路径 in 显式:
            输出行.append((文档路径, str(显式[文档路径].get("档")),
                          str(显式[文档路径].get("表达什么") or "")))
            continue
        for 条目 in 定档规则:
            if 文档路径.startswith(条目["前缀"]):
                输出行.append((文档路径, str(条目.get("档")),
                              "（按路径规则）" + 文档路径.rsplit("/", 1)[-1]))
                break
        else:
            输出行.append((文档路径, "（未定义）", "—— 账本里没有它（判据 ㊶ 会报红）"))
    return 输出行


def 装未完成(根目录: Path) -> list:
    输出行 = []
    for 一行 in 读文本(根目录 / "项目文档" / "未完成事项.md").splitlines():
        匹配 = re.match(r"^\|\s*(\d+)\s*\|(.*)$", 一行)
        if not 匹配:
            continue
        格表 = [格值.strip() for 格值 in 匹配.group(2).split("|")]
        缺什么 = 格表[0] if 格表 else ""
        落点 = 格表[1] if len(格表) > 1 else ""
        验证命令 = 格表[-2] if len(格表) >= 3 else ""
        输出行.append((int(匹配.group(1)), 缺什么[:2000], 落点[:500], 验证命令[:500]))
    return 输出行


def 装命名定义(根目录: Path) -> list:
    return _命名表(根目录)[0]


def 装命名模式(根目录: Path) -> list:
    """模式表**由 `表定义.py` 供源** —— 它是机器可判的那一份（正则），md §七 只是它的散文说明。

    两边各一份必然漂（实测：`表定义` 改了正则，库里还是旧表）。⇒ 只留 `表定义` 一份，
    库里的 `命名模式` 是它的副本。
    """
    return [(种类, 正则式, 例文) for 种类, 正则式, 例文 in 表定义.命名模式]


def _命名表(根目录: Path) -> tuple:
    """`命名规范.md` §七/§八 → `(定义行, 模式行)`。缓存住，两张表共用一次解析。"""
    if 根目录 in _命名缓存:
        return _命名缓存[根目录]
    规范文本 = 读文本(根目录 / "项目文档" / "决策记录" / "2026-09-27_命名规范.md")
    节名 = ""
    定义, 模式 = [], []
    for 一行 in 规范文本.splitlines():
        # 一行 = `| 左格 | 中格 | 右格 |`
        if 一行.startswith("### "):
            节名 = 一行[4:].strip()
            continue
        if 一行.startswith("## "):
            节名 = 一行[3:].strip()
            continue
        匹配 = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*$", 一行)
        if not 匹配:
            continue
        格首, 格次, 格三 = 匹配.group(1), 匹配.group(2), 匹配.group(3)
        if 格首 in ("语义", "种类") or set(格首) <= set("-: "):
            continue
        if re.match(r"^8\.\d", 节名):
            定义.append((格首, 格次, 格三))
        elif 节名.startswith("七"):
            模式.append((格首, 格次, 格三))
    _命名缓存[根目录] = (定义, 模式)
    return _命名缓存[根目录]


def 装代码名(根目录: Path) -> list:
    索引 = 根目录 / ".codegraph" / "codegraph.db"
    if not 索引.is_file():
        return []
    索引库 = sqlite3.connect(索引)
    输出行 = 索引库.execute(
        "select id, name, kind, language, qualified_name, file_path, start_line from nodes"
    ).fetchall()
    索引库.close()
    return 输出行


def 节点名(键名: str) -> tuple:
    路径段 = 键名.split("/")
    顶层 = 路径段[0]
    层名 = 表定义.顶层目录到层.get(顶层, 顶层)
    if 顶层 in 表定义.底座树 and len(路径段) > 1:
        return 层名, f"{顶层}/{路径段[1]}"
    return 层名, 顶层


def 装节点(根目录: Path) -> list:
    return _拓扑表(根目录)[0]


def 装连接(根目录: Path) -> list:
    return _拓扑表(根目录)[1]


def _拓扑表(根目录: Path) -> tuple:
    """代码地图索引 → `(节点行, 连接行)`。缓存住，两张表共用一次读。"""
    if 根目录 in _拓扑缓存:
        return _拓扑缓存[根目录]
    索引 = 根目录 / ".codegraph" / "codegraph.db"
    if not 索引.is_file():
        _拓扑缓存[根目录] = ([], [])
        return _拓扑缓存[根目录]
    索引库 = sqlite3.connect(索引)
    文件到节点, 节点集 = {}, {}
    for (文件,) in 索引库.execute("select distinct file_path from nodes where file_path is not null"):
        所在层, 节点键 = 节点名(文件)
        文件到节点[文件] = 节点键
        节点集[节点键] = 所在层
    边表 = {}
    for (源件, 目标件) in 索引库.execute(
        "select n1.file_path, n2.file_path from edges e "
        "join nodes n1 on n1.id = e.source join nodes n2 on n2.id = e.target "
        "where e.kind = 'imports'"
    ):
        起点, 终点 = 文件到节点.get(源件), 文件到节点.get(目标件)
        if not 起点 or not 终点 or 起点 == 终点:
            continue
        边表[(起点, 终点)] = 边表.get((起点, 终点), 0) + 1
    索引库.close()
    _拓扑缓存[根目录] = (
        [(节点键, 所在层, "节点", 表定义.节点职责.get(节点键, ""))
         for 节点键, 所在层 in 节点集.items()],
        [(起点, 终点, "imports", 条数) for (起点, 终点), 条数 in 边表.items()],
    )
    return _拓扑缓存[根目录]


def 装能力(根目录: Path) -> list:
    return _契约表(根目录)[0]


def 装能力参数(根目录: Path) -> list:
    return _契约表(根目录)[1]


def 装类型(根目录: Path) -> list:
    return _契约表(根目录)[2]


def 装错误码(根目录: Path) -> list:
    return _契约表(根目录)[3]


def _契约表(根目录: Path) -> tuple:
    """`契约声明/` 三个子目录 → `(能力行, 参行, 类型行, 错误码行)`。缓存住，四张表共用一次扫。"""
    if 根目录 in _契约缓存:
        return _契约缓存[根目录]
    契约 = 根目录 / "契约声明"
    能力行, 参行, 类型行, 错误行 = [], [], [], []
    for 声明件 in sorted((契约 / "能力声明").glob("*.json")):
        声明数据 = 读JSON(声明件) or {}
        能力编号 = 声明数据.get("编号", 0)
        参数表 = 声明数据.get("参数表") or []
        能力行.append((能力编号, str(声明数据.get("名称", "")), len(参数表),
                      声明数据.get("返回类型", 0),
                      ",".join(str(码文) for 码文 in (声明数据.get("可抛错误码") or []))))
        for 参号, 参数 in enumerate(参数表, 1):
            参行.append((能力编号, 参号, str(参数.get("名称", "")), 参数.get("类型标签", 0), "入参"))
    for 声明件 in sorted((契约 / "类型声明").glob("*.json")):
        声明数据 = 读JSON(声明件) or {}
        类型行.append((声明数据.get("类型标签", 0), str(声明数据.get("名称", "")),
                      str(声明数据.get("说明", ""))[:200]))
    for 声明件 in sorted((契约 / "错误码表").glob("*.json")):
        声明数据 = 读JSON(声明件) or {}
        错误行.append((声明数据.get("码", 0), 声明数据.get("段位", 0),
                      str(声明数据.get("名称", "")),
                      1 if 声明数据.get("可重试") else 0,
                      1 if 声明数据.get("可自愈") else 0,
                      1 if 声明数据.get("需人工") else 0))
    _契约缓存[根目录] = (能力行, 参行, 类型行, 错误行)
    return _契约缓存[根目录]


# ── 入口 ──────────────────────────────────────────────────────────
def 装表(连接, 表名: str, 现抽, *参数) -> int:
    """装一张表，返回行数。

    **源还在就重抽**（md 还没删时，改 md 即刻生效）；**源没了就保住库里的行**
    （md 删掉之后库自身就是源 —— 重抽会把它清空）。判定 = 「现抽抽出空集 且 库里已有行
    且 本表是源表」⇒ 认为源已消失，保留旧行。派生表不受此保护（它们的源永远在）。
    """
    已有行数 = 连接.execute(f"select count(*) from {表名}").fetchone()[0]
    数据行 = 现抽(*参数)
    if not 数据行 and 已有行数 and 表名 in 表定义.源表:
        return 已有行数
    连接.execute(f"delete from {表名}")
    if 数据行:
        连接.executemany(
            f"insert or replace into {表名} values({','.join('?' * len(数据行[0]))})", 数据行)
    return len(数据行)


def 建库(指定根: Path = None, 打读数: bool = False) -> dict:
    根目录 = 指定根 or 仓根
    库路径 = 表定义.库路径(根目录)
    连接 = sqlite3.connect(库路径)
    for 语句 in 表定义.建表语句:
        连接.execute(语句)
    连接.execute("insert or replace into 元 values(?,?)",
               ("生成物声明", 表定义.生成物声明))
    计数 = {
        "文档": 装表(连接, "文档", 装文档, 根目录),
        # `条款` 现抽要拿 `文档` 的行当入参 —— 文档表是派生表，始终现抽，所以这里总拿得到。
        "条款": 装表(连接, "条款", 装条款, 根目录, 装文档(根目录)),
        "规则": 装表(连接, "规则", 装规则, 根目录),
        "未完成": 装表(连接, "未完成", 装未完成, 根目录),
        "命名定义": 装表(连接, "命名定义", 装命名定义, 根目录),
        "命名模式": 装表(连接, "命名模式", 装命名模式, 根目录),
        "代码名": 装表(连接, "代码名", 装代码名, 根目录),
        "节点": 装表(连接, "节点", 装节点, 根目录),
        "连接": 装表(连接, "连接", 装连接, 根目录),
        "能力": 装表(连接, "能力", 装能力, 根目录),
        "能力参数": 装表(连接, "能力参数", 装能力参数, 根目录),
        "类型": 装表(连接, "类型", 装类型, 根目录),
        "错误码": 装表(连接, "错误码", 装错误码, 根目录),
    }
    连接.commit()
    连接.close()
    if 打读数:
        print(f"库：{库路径}")
        for 表名, 行数 in 计数.items():
            print(f"  {表名}：{行数}")
    return 计数


def 入口函数(参数: list) -> int:
    """`信息核心.py 建库 …` 调它 —— 本件**不带** `__main__`（入口只有一个壳，见 信息核心.py）。"""
    建库(打读数="--读数" in 参数)
    return 0
