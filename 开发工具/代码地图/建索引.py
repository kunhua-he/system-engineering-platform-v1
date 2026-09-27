# -*- coding: utf-8 -*-
"""代码地图 · 建索引 —— 跑三条 SCIP 腿，落**统一形状**的两份 JSONL（环境步）。

三条腿都由**开源的成熟索引器**产出（见 `SCIP前端.py` docstring），本模块只做编排：
并发跑索引器 → `scip print --json` 读回 → 转统一形状 → 写 `定义.jsonl` / `出现.jsonl`。

**这是一次性冷构建，属环境步**（`决策记录/2026-09-27_构建段归环境步.md` §四）：
三条腿都要加载整棵工程（实测合计 ≈ 12 s）⇒ **照实报墙钟、不判顶**。
查的时候才是判顶对象（只读 JSONL，实测 0.1–0.3 s）。

**环境依赖**（四条，都**不是底座能力**）：`rust-analyzer` · `scip-python` · `scip-typescript` · `scip`。
缺哪条 ⇒ 那条腿不跑，`建` 如实报「哪条腿没跑」，其余照跑。退法：删缓存目录 + 卸工具 ⇒
底座与判据面**照跑**（`构建装配/一键验证/` 里 0 处调它）。
"""

import json
import time
from pathlib import Path

from . import SCIP前端
from .落点 import 出现路径, 定义路径, 原始路径, 确保目录

# 扫哪些后缀、跳哪些目录（与判据面同一套口径，不另立一份）
代码后缀表 = (".rs", ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".svelte")
跳过目录表 = {"构建环境", "只读参考", ".git", "__pycache__", "node_modules", "target", "制品产物"}
js后缀表 = (".js", ".ts", ".tsx", ".jsx", ".vue", ".svelte")

# 语言键 → 打印用的短名（与 `落点.原始名` 的键同一套）
腿显示名 = {"rs": "rs", "py": "py", "js": "js/ts"}


def 收件(仓根: Path) -> list:
    """扫仓里的代码件 ⇒ `[(相对路径, 文件文本)]`（读不动的件跳过 —— 它不进索引，不假装它在）。"""
    代码件表 = []
    for 当前目录, 目录名表, 文件名表 in 仓根.walk():
        目录名表[:] = [目录名 for 目录名 in 目录名表 if 目录名 not in 跳过目录表]
        for 文件名 in sorted(文件名表):
            文件路径 = 当前目录 / 文件名
            if 文件路径.suffix not in 代码后缀表:
                continue
            try:
                代码件表.append((str(文件路径.relative_to(仓根)), 文件路径.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
    return 代码件表


def js目录(代码件表: list) -> list:
    """有 JS/TS 的**目录**（去重、排序）—— `scip-typescript` 不扫全仓，得把目录逐个点出来。"""
    目录集 = {str(Path(相对路径).parent) for 相对路径, _ in 代码件表
             if Path(相对路径).suffix in js后缀表}
    return sorted(目录集)


def _写索引行(落点路径: Path, 记录表: list) -> None:
    with 落点路径.open("w", encoding="utf-8") as 索引文件:
        for 一条记录 in 记录表:
            索引文件.write(json.dumps(一条记录, ensure_ascii=False, sort_keys=True) + "\n")


def _后缀属该腿(相对路径: str, 语言键: str) -> bool:
    后缀 = Path(相对路径).suffix
    if 语言键 == "rs":
        return 后缀 == ".rs"
    if 语言键 == "py":
        return 后缀 == ".py"
    return 后缀 in js后缀表


def _拼腿读数(代码件表: list, 腿读数表: list, 统一结果表: list) -> str:
    """一条腿一段读数：跑了多少件、出了多少定义；没跑的**点名**。"""
    各腿件数 = {语言键: sum(1 for 相对路径, _ in 代码件表 if _后缀属该腿(相对路径, 语言键))
              for 语言键 in 腿显示名}
    各腿定义数 = {语言键: len(结果["定义"]) for 语言键, 结果 in 统一结果表}
    跑过的腿表 = {读数["语言键"]: 读数 for 读数 in 腿读数表}
    读数段表 = []
    for 语言键, 显示名 in 腿显示名.items():
        读数 = 跑过的腿表.get(语言键)
        if 读数 is None:
            读数段表.append("%s %d 件 **未跑**（缺 %s）" % (
                显示名, 各腿件数[语言键], SCIP前端.三条腿表[语言键][0]))
        elif 读数["退出码"] != 0:
            读数段表.append("%s %d 件 **索引器退出码 %d**" % (
                显示名, 各腿件数[语言键], 读数["退出码"]))
        else:
            读数段表.append("%s %d 件/%d 定义" % (
                显示名, 各腿件数[语言键], 各腿定义数.get(语言键, 0)))
    return " · ".join(读数段表)


def 建(仓根: Path) -> tuple:
    """跑三条 SCIP 腿 + 写两份 JSONL ⇒ `(退出码, 墙钟毫秒, 说明)`。"""
    确保目录()
    开始时刻 = time.monotonic()
    代码件表 = 收件(仓根)
    腿读数表, 读回结果表 = SCIP前端.跑三条腿(仓根, 原始路径, js目录(代码件表))

    定义表, 出现表, 统一结果表 = [], [], []
    for 语言键, 索引 in 读回结果表:
        if not 索引:
            continue
        结果 = SCIP前端.转统一形状(索引, 语言键, 仓根.name)
        统一结果表.append((语言键, 结果))
        定义表.extend(结果["定义"])
        出现表.extend(结果["出现"])
    定义表.sort(key=lambda 定义记录: (定义记录["路径"], 定义记录["行"], 定义记录["限定名"]))
    出现表.sort(key=lambda 出现记录: (出现记录["路径"], 出现记录["行"], 出现记录["列"]))
    _写索引行(定义路径(), 定义表)
    _写索引行(出现路径(), 出现表)

    墙钟毫秒 = int((time.monotonic() - 开始时刻) * 1000)
    缺失工具表 = SCIP前端.缺哪些工具()
    说明 = "索引 %d 定义 · %d 出现（%s）⇒ %s" % (
        len(定义表), len(出现表), _拼腿读数(代码件表, 腿读数表, 统一结果表), 定义路径().parent)
    清理数 = sum(读数.get("清理数", 0) for 读数 in 腿读数表)
    if 清理数:
        说明 += "；收了 %d 个索引器写进源码树的临时 tsconfig" % 清理数
    if 缺失工具表:
        说明 += "；缺工具 %d 件 ⇒ %s" % (
            len(缺失工具表), " · ".join("%s(%s)" % (工具名, 装法)
                                      for _, 工具名, 装法 in 缺失工具表))
    return 0, 墙钟毫秒, 说明


def 报缺工具() -> int:
    print("代码地图：索引器不齐（它们是**环境依赖**，不是底座能力）。缺：")
    for _, 工具名, 装法说明 in SCIP前端.缺哪些工具():
        print("  · %-16s 装法：%s" % (工具名, 装法说明))
    print("  不装也行 —— 底座与判据面照跑（`构建装配/一键验证/` 里 0 处调它）；")
    print("  退法：删 <运行数据根>/缓存/代码地图/，其余一切照跑。")
    return 0
