# -*- coding: utf-8 -*-
"""读盘 —— 读盘 · 单趟扫描 · 对外接口 `扫实现`（连跑两遍）· 找仓根。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .常量 import 读上限字节, 契约目录名, 常量表相对, 判据名表
from .小工具 import 相对
from .掩码 import 掩码
from .夹具判定 import 建夹具集
from .符号解析 import 建符号表
from .抽实现面 import 抽实现面
from .声明侧 import 读声明侧
from .比对 import 比对
from .判据工具 import 记
from .组装 import _组装
from .不覆盖 import 元记录


def 读盘(仓根: str, 范围: list) -> dict:
    根 = Path(仓根)
    件表 = {}
    坏 = []

    def 收(路径: Path):
        键 = 相对(根, 路径)
        try:
            if 路径.stat().st_size > 读上限字节:
                坏.append((键, f"超过读上限 {读上限字节} 字节（不截断——截断会让解析腿拿到半个文件）"))
                return
            件表[键] = 路径.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as 错:
            坏.append((键, f"读不动：{错}"))

    for 范围项 in 范围:
        基 = 根 / 范围项
        if not 基.is_dir():
            continue
        for 根目录, 目录表, 文件表 in os.walk(基):
            目录表[:] = [目录 for 目录 in 目录表 if 目录 not in {".git", "__pycache__", "构建缓存", "target"}]
            for 名 in 文件表:
                if 名.endswith((".rs", ".json")) or 名 == "Cargo.toml":
                    收(Path(根目录) / 名)
    契约 = 根 / 契约目录名
    if 契约.is_dir():
        for 根目录, 目录表, 文件表 in os.walk(契约):
            目录表[:] = [目录 for 目录 in 目录表 if 目录 not in {"__pycache__"}]
            for 名 in 文件表:
                # `.rs` 全收（含 `契约声明/src/` 子目录）——符号表的落点是符号不是文件，
                # 写死文件名会让拆分后的子件静默丢出符号表（甲3）。
                if 名.endswith((".json", ".rs")):
                    收(Path(根目录) / 名)
    return {"件表": 件表, "坏": 坏}


def 常量表名集(件表: dict) -> set:
    文 = 件表.get(常量表相对)
    if not 文:
        return set()
    try:
        数 = json.loads(文)
    except json.JSONDecodeError:
        return set()
    常量名集 = set()
    for 常量条 in 数.get("常量") or []:
        if isinstance(常量条, dict) and isinstance(常量条.get("名"), str):
            常量名集.add(常量条["名"])
    return 常量名集


def _扫一遍(仓根: str, 范围: list, 件表=None, 坏=None) -> list:
    if 件表 is None:
        读回 = 读盘(仓根, 范围)
        件表, 坏 = 读回["件表"], 读回["坏"]
    坏 = 坏 or []
    掩表 = {件键: 掩码(掩前) for 件键, 掩前 in 件表.items() if 件键.endswith(".rs") and 掩前 is not None}
    夹具 = 建夹具集(件表, 掩表)
    符号表 = 建符号表(件表, 掩表)
    实现面 = 抽实现面(件表, 范围, 符号表, 夹具, 掩表)
    声明根表 = 读声明侧(件表)
    比对结果 = 比对(实现面, 声明根表, 符号表, 常量表名集(件表))
    # 读不动的文件：不许静默——挂到第一条判据的明细上（位置与原因都具体）
    for 键, 因 in 坏:
        比对结果[判据名表[0]]["明细"].append(
            记(判据名表[0], "未判", 键,
               f"判不了：这个文件读不动（{因}）⇒ 它可能是实现面或声明面的一部分，漏读就是漏判",
               "读不动有两种：文件被别的腿写到一半（瞬时），或权限/编码问题（持久）。"
               "验证面不能替它猜内容 ⇒ 只能由该文件的作者确认")
        )
    结果 = _组装(比对结果)
    # 「不覆盖登记表」自洽（fail-closed）：登记表长霉 ⇒ 追加一条**失败**元记录（不是未判）。
    # 传 `仓根`/`范围` ⇒ 按范围过滤：窄范围（扩展专属档）不因范围外的底座登记而假红（#56）。
    结果.extend(元记录(实现面["单元"], 仓根=仓根, 范围=范围))
    return 结果


def 扫实现(仓根: str, 范围: list) -> list:
    """**冻结接口**：`扫实现(仓根: str, 范围: list[str]) -> list[dict]`。

    一条判据一条记录（含 `明细`）。内部**连跑两遍**：同一条判据两遍都红才算「源码错」，
    只红一遍的标「疑似瞬时」并不当阻断（`判据的可信性.md` §四.1）。
    """
    r1 = 读盘(仓根, 范围)
    首遍读数 = _扫一遍(仓根, 范围, 件表=r1["件表"], 坏=r1["坏"])
    r2 = 读盘(仓根, 范围)
    if r2["件表"] == r1["件表"] and r2["坏"] == r1["坏"]:
        # 两遍读到的**字节完全一致** ⇒ 判定必然一致（解析是纯函数：同一输入 → 同一输出）。
        # 这一条短路把「连跑两遍」的成本在稳态下变成「只多读一遍文件」（≈10 ms），
        # 而**真变了**的场合仍然会走第二趟解析并逐条比判定 —— 判据的严格性没有放宽。
        return 首遍读数
    次遍读数 = _扫一遍(仓根, 范围, 件表=r2["件表"], 坏=r2["坏"])
    次遍索引 = {条["项"]: 条 for 条 in 次遍读数}
    for 条 in 首遍读数:
        对条 = 次遍索引.get(条["项"])
        if 对条 is None or 对条["判定"] != 条["判定"]:
            条["红类"] = "疑似瞬时" if 条["判定"] == "失败" else 条["红类"]
            if 条["判定"] == "失败":
                条["缺什么"] = (
                    "疑似瞬时（两遍读数不一致）：" + 条["缺什么"]
                    + f"｜第二遍的判定是「{对条['判定'] if 对条 else '缺'}」"
                )
                条["为什么不能自愈"] = (
                    "两遍读数不一致 ⇒ 多半是别的腿正在写文件（半成品），不是源码问题。"
                    "按 判据的可信性 §四.1：只红一次不当阻断，重跑一次仍红才算 ⇒ 只能等文件写完后重跑"
                )
    return 首遍读数


def 找仓根() -> str:
    for 起 in [Path.cwd(), Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (起 / 契约目录名).is_dir():
            return str(起)
    return str(Path.cwd())
