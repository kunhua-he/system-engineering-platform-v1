# -*- coding: utf-8 -*-
"""代码地图 · 索引 —— 读 rust-analyzer 的 **LSIF**（JSON 行）建成内存符号表。

**为什么读 LSIF 不读 SCIP**：两者都是 rust-analyzer 的产出，语义相同；SCIP 是 protobuf
（标准库解不了，要引第三方 ⇒ 违反零第三方依赖），LSIF 是**一行一个 JSON**（`json` 模块就够）。
实测全量 23.8 万行 · 347 文档 · 9101 个符号，解析 **379 ms**。

**为什么要有索引而不是每次现查**：rust-analyzer 的 `symbols` / `search` / `unresolved-references`
每次都要**加载整个工程**（实测 ≈ 11.6 s）⇒ 超五秒硬顶。老仓的同一课：
`项目文档`…（老仓 `代码解析支持库/代码地图/说明/设计说明.md` §1）—— 外部 CLI 每查一次起一个
子进程，底座改成**直读预建库**。本件照此：建一次（环境步）· 查只读文件。

**本件是叶子**：只 import 标准库 + Python 侧唯一解析器（`运行数据根`）。不写盘、不建目录。
"""

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 开发工具/：取 运行数据根
from 运行数据根 import 解析当前, 子目录路径  # noqa: E402

缓存类 = "缓存"
缓存子目录 = "代码地图"
索引名 = "索引.lsif"


def 索引路径() -> Path:
    """索引落点 = `<运行数据根>/缓存/代码地图/索引.lsif`（判据 ⑳：不落源码树）。"""
    return 子目录路径(解析当前(), 缓存类) / 缓存子目录 / 索引名


def 索引状态() -> dict:
    """索引在不在、多大、多新 —— 只读文件元数据，不解析。"""
    路 = 索引路径()
    if not 路.is_file():
        return {"有": False, "路径": str(路)}
    元 = 路.stat()
    return {"有": True, "路径": str(路), "字节": 元.st_size, "改于": 元.st_mtime}


def _路径(uri: str, 仓根: Path) -> str:
    """`file:///…` → 相对仓根的路径（URL 里中文是百分号编码，要解回来）。"""
    路文本 = urllib.parse.unquote(urllib.parse.urlparse(uri).path)
    try:
        return str(Path(路文本).relative_to(仓根))
    except ValueError:
        return 路文本


def 读索引(路: Path, 仓根: Path) -> dict:
    """解析 LSIF ⇒ `{"符号": [...], "文档数": n, "行数": n}`。

    符号 = 一个 `resultSet`（LSIF 里「同一个符号的全部出现」的锚）。名字取 moniker 的
    `identifier`（限定名，如 `v1_dataroot::解析件`）；没有 moniker（非导出项）时退取
    hover 第一段代码块里的声明文本。定义位置取 `textDocument/definition` 指向的 range。
    """
    单: dict = {}
    出边: dict = {}   # (outV, label) → [inV…]
    行数 = 0
    with 路.open(encoding="utf-8") as 文:
        for 行 in 文:
            if not 行.strip():
                continue
            行数 += 1
            条 = json.loads(行)
            if 条.get("type") == "vertex":
                单[条["id"]] = 条
            elif 条.get("type") == "edge":
                键 = (条.get("outV"), 条.get("label"))
                值 = 条.get("inV")
                表 = 条.get("inVs")
                出边.setdefault(键, []).extend([值] if 值 is not None else (表 or []))

    范围归属: dict = {}   # range id → 相对路径
    for (外, 标), 内表 in 出边.items():
        if 标 != "contains":
            continue
        文 = 单.get(外)
        if not 文 or 文.get("label") != "document":
            continue
        相 = _路径(文.get("uri", ""), 仓根)
        for 内 in 内表:
            范围归属[内] = 相

    符号表 = []
    for 结果集, 顶点 in 单.items():
        if 顶点.get("label") != "resultSet":
            continue
        限定名 = ""
        for 怪 in 出边.get((结果集, "moniker"), []):
            限定名 = 单.get(怪, {}).get("identifier", "") or 限定名
        悬停 = ""
        for 怪 in 出边.get((结果集, "textDocument/hover"), []):
            悬停 = 单.get(怪, {}).get("result", {}).get("contents", {}).get("value", "") or 悬停
        定义 = []
        for 怪 in 出边.get((结果集, "textDocument/definition"), []):
            for 段 in 出边.get((怪, "item"), []):
                段点 = 单.get(段, {})
                路 = 范围归属.get(段)
                if 路 and 段点.get("start"):
                    定义.append((路, 段点["start"]["line"] + 1))
        # **全部出现位置**（定义 + 引用）——符号级批量替换靠它：LSIF 的 `item` 边指向 `range`
        # 顶点，range 带 `start` 的 line/character（**UTF-16** 列）。实测可用（校输入形状 3 处）。
        出现 = []
        for 标 in ("textDocument/definition", "textDocument/references"):
            for 怪 in 出边.get((结果集, 标), []):
                for 段 in 出边.get((怪, "item"), []):
                    段点 = 单.get(段, {})
                    路 = 范围归属.get(段)
                    起 = 段点.get("start")
                    if 路 and 起:
                        出现.append((路, 起["line"] + 1, 起["character"]))
        引用数 = 0
        for 怪 in 出边.get((结果集, "textDocument/references"), []):
            引用数 += len(出边.get((怪, "item"), []))
        符号表.append({
            "限定名": 限定名,
            "悬停": 悬停,
            "定义": 定义,
            "出现": sorted(set(出现)),
            "引用数": 引用数,
        })

    # rust-analyzer 对同一个符号会出**两套**记录（一套带 moniker、一套只有 hover）⇒
    # 按「定义位置 ＋ 显示名」去重；优先留**有 moniker** 的那条（它的名字更规范）。
    去重: dict = {}
    for 符号 in 符号表:
        名 = 符号["限定名"]
        if 名.startswith("rust "):
            符号["限定名"] = 名[len("rust "):]
        键 = (tuple(符号["定义"]), 名字(符号))
        旧 = 去重.get(键)
        if 旧 is not None:
            符号["引用数"] = max(符号["引用数"], 旧["引用数"])
            if 旧["限定名"]:
                continue
        elif not 符号["限定名"] and not 符号["定义"]:
            continue  # 既没名字也没位置 ⇒ 报不出来，不入表
        去重[键] = 符号

    return {"符号": list(去重.values()), "文档数": sum(1 for 顶点 in 单.values() if 顶点.get("label") == "document"),
            "行数": 行数}


def 声明行(符号: dict) -> str:
    """从 hover 文本里取**第一段代码块**的内容当「声明行」（LSIF 里没有单独的签名字段）。"""
    文 = 符号.get("悬停", "")
    段 = 文.split("```")
    return 段[1].strip().replace("\n", " ") if len(段) >= 3 else ""


def 名字(符号: dict) -> str:
    """**显示名**：有 moniker 就用限定名；没有（非导出项）就用声明行，并去掉 rust-analyzer
    给路径式显示加的那个 `rust ` 前缀（实测它出现在「只有路径、没有签名」的那些 hover 里）。"""
    名 = 符号.get("限定名", "")
    if 名:
        return 名
    文 = 声明行(符号)
    return 文[len("rust "):] if 文.startswith("rust ") else 文


def 查(索引: dict, 关键词: str, 上限: int = 40) -> list:
    """按**限定名 / 声明行 / 路径**子串查符号 ⇒ 命中清单（稳定排序、可截断）。

    排序把**有名字的符号**排在前面：没 moniker 的（参数 · 局部变量）名字从声明行退取，
    它们是 `rg` 就能答的噪声 —— 不是代码地图买的那件事。
    """
    出 = []
    for 符号 in 索引["符号"]:
        路 = " · ".join(路 for 路, _行 in 符号["定义"])
        if 关键词 in 名字(符号) or 关键词 in 声明行(符号) or 关键词 in 路:
            出.append(符号)
    出.sort(key=lambda 符号: (符号["限定名"] == "", 名字(符号), 符号["定义"]))
    return 出[:上限]


def 引用(索引: dict, 限定名: str, 上限: int = 60) -> list:
    """按**限定名精确**找符号 ⇒ 它的定义位置与引用处数（引用位置清单不在 LSIF 的行级细节里，
    故只报「处数」；要具体位置用 `rg` —— 本工具买的是**语义**：谁是定义、谁在引用）。"""
    return [符号 for 符号 in 索引["符号"] if 名字(符号) == 限定名][:上限]
