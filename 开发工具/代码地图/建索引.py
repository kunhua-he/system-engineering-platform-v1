# -*- coding: utf-8 -*-
"""代码地图 · 建索引 —— 跑三条 SCIP 腿，落**统一形状**的两份 JSONL（环境步）。

三条腿都由**开源的成熟索引器**产出（见 `SCIP前端.py` docstring），本模块只做编排：
并发跑索引器 → `scip print --json` 读回 → 转统一形状 → 写 `定义.jsonl` / `出现.jsonl`。

**这是一次性冷构建，属环境步**（`决策记录/2026-09-27_构建段归环境步.md` §四）：
三条腿都要加载整棵工程（实测合计 ≈ 19 s）⇒ **照实报墙钟、不判顶**。
查的时候才是判顶对象（只读 JSONL，实测 0.2 s 级）。

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
代码后缀 = (".rs", ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".svelte")
跳过目录 = {"构建环境", "只读参考", ".git", "__pycache__", "node_modules", "target", "制品产物"}


def 收件(仓根: Path) -> list:
    """扫仓里的代码件 ⇒ `[(相对路径, 文本)]`（读不动的件跳过 —— 它不进索引，不假装它在）。"""
    出 = []
    for 根, 目录表, 件表 in 仓根.walk():
        目录表[:] = [目录名 for 目录名 in 目录表 if 目录名 not in 跳过目录]
        for 名 in sorted(件表):
            路 = 根 / 名
            if 路.suffix not in 代码后缀:
                continue
            try:
                出.append((str(路.relative_to(仓根)), 路.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
    return 出


def js目录(件表: list) -> list:
    """有 JS/TS 的**目录**（去重、排序）—— `scip-typescript` 不扫全仓，得把目录逐个点出来。"""
    js后缀 = (".js", ".ts", ".tsx", ".jsx", ".vue", ".svelte")
    出 = {str(Path(路).parent) for 路, _ in 件表 if Path(路).suffix in js后缀}
    return sorted(出)


def _写JSONL(路: Path, 表: list) -> None:
    with 路.open("w", encoding="utf-8") as 文:
        for 条 in 表:
            文.write(json.dumps(条, ensure_ascii=False, sort_keys=True) + "\n")


def _腿说明(件表: list, 腿读数: list, 统一表: list) -> str:
    """一条腿一行读数：跑了多少件、出了多少定义；没跑的**点名**。"""
    键名 = {"rs": "rs", "py": "py", "js": "js/ts"}
    件数 = {键: sum(1 for 路, _ in 件表 if _后缀属(路, 键)) for 键 in 键名}
    定义数 = {键: len(果["定义"]) for 键, 果 in 统一表}
    跑过 = {读["键"]: 读 for 读 in 腿读数}
    段 = []
    for 键, 名 in 键名.items():
        读数 = 跑过.get(键)
        if 读数 is None:
            段.append("%s %d 件 **未跑**（缺 %s）" % (名, 件数[键], SCIP前端.腿表[键][0]))
        elif 读数["码"] != 0:
            段.append("%s %d 件 **索引器退出码 %d**" % (名, 件数[键], 读数["码"]))
        else:
            段.append("%s %d 件/%d 定义" % (名, 件数[键], 定义数.get(键, 0)))
    return " · ".join(段)


def _后缀属(路: str, 键: str) -> bool:
    后 = Path(路).suffix
    if 键 == "rs":
        return 后 == ".rs"
    if 键 == "py":
        return 后 == ".py"
    return 后 in (".js", ".ts", ".tsx", ".jsx", ".vue", ".svelte")


def 建(仓根: Path) -> tuple:
    """跑三条 SCIP 腿 + 写两份 JSONL ⇒ `(退出码, 墙钟毫秒, 说明)`。"""
    确保目录()
    起 = time.monotonic()
    件表 = 收件(仓根)
    腿读数, 读回果 = SCIP前端.跑三条腿(仓根, 原始路径, js目录(件表))

    定义, 出现 = [], []
    统一表 = []
    for 键, 索引 in 读回果:
        if not 索引:
            continue
        果 = SCIP前端.转统一(索引, 键, 仓根.name)
        统一表.append((键, 果))
        定义.extend(果["定义"])
        出现.extend(果["出现"])
    定义.sort(key=lambda 条: (条["路径"], 条["行"], 条["限定名"]))
    出现.sort(key=lambda 条: (条["路径"], 条["行"], 条["列"]))
    _写JSONL(定义路径(), 定义)
    _写JSONL(出现路径(), 出现)

    毫秒 = int((time.monotonic() - 起) * 1000)
    缺 = SCIP前端.缺什么()
    说明 = "索引 %d 定义 · %d 出现（%s）⇒ %s" % (
        len(定义), len(出现), _腿说明(件表, 腿读数, 统一表), 定义路径().parent)
    清理 = sum(读.get("清理", 0) for 读 in 腿读数)
    if 清理:
        说明 += "；收了 %d 个索引器写进源码树的临时 tsconfig" % 清理
    if 缺:
        说明 += "；缺工具 %d 件 ⇒ %s" % (len(缺), " · ".join("%s(%s)" % (名, 装) for _, 名, 装 in 缺))
    return 0, 毫秒, 说明


def 报缺工具() -> int:
    print("代码地图：索引器不齐（它们是**环境依赖**，不是底座能力）。缺：")
    for _, 名, 装 in SCIP前端.缺什么():
        print("  · %-16s 装法：%s" % (名, 装))
    print("  不装也行 —— 底座与判据面照跑（`构建装配/一键验证/` 里 0 处调它）；")
    print("  退法：删 <运行数据根>/缓存/代码地图/，其余一切照跑。")
    return 0
