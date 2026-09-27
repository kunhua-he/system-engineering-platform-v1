# -*- coding: utf-8 -*-
"""形状 —— 三条形状的判定（读盘 · 查一步 · 查一份 · 扫案例 · 打读数）。

口径与判法（含「③ 纯确定性」那一半的可判口径）全在本文件的 `模块说明` 段，
逐条抄自 `测试验证/案例/形状.md` §十。三条形状的**键名与白名单**在 `常量.py`。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .常量 import (
    产物判据白名单,
    旁路键名,
    关键值判据,
    期望结果文件名,
    判定_违反,
    判定_未判,
    形状错,
)


def 读JSON(路: Path):
    return json.loads(路.read_text(encoding="utf-8"))


def 找旁路键(值, 路: str = "") -> list:
    """在期望对象里递归找旁路键名；返回 [(位置, 键名)]。"""
    出 = []
    if isinstance(值, dict):
        for 键, 子 in 值.items():
            小写 = str(键).strip().lower()
            小写位 = f"{路}/{键}" if 路 else str(键)
            if 小写 in 旁路键名:
                出.append((小写位, 键))
            出.extend(找旁路键(子, 小写位))
    elif isinstance(值, list):
        for 序, 子 in enumerate(值):
            出.extend(找旁路键(子, f"{路}[{序}]"))
    return 出


def 查一步(目录: Path, 步: dict, 位: str, 备了关键值: bool, 报告: list) -> int:
    """查一步期望的三条形状。返回**未判**条数（0 表示这一步没有未判）。"""
    # ── 形状②：旁路键 ──
    for 键路, 键名 in 找旁路键(步):
        raise 形状错(
            f"{位}：出现旁路键 `{键名}`（位置 {键路}）—— 载体必须是**返回值槽**，"
            f"标准输出与退出码是**旁路**（形状.md §10.1②）"
        )
    # ── 形状①：产物判据必须在那五个里 ──
    产物 = 步.get("产物")
    if 产物 is None:
        报告.append((位, "`产物` 缺失 ⇒ 这一步连载体都没声明", 判定_未判))
        return 1
    if not isinstance(产物, dict):
        raise 形状错(f"{位}：`产物` 不是对象")
    判据 = 产物.get("判据")
    if 判据 not in 产物判据白名单:
        raise 形状错(
            f"{位}：产物判据 `{判据}` 不在封闭枚举里"
            f"（{' / '.join(产物判据白名单)}）—— 载体只能是返回值槽（形状.md §1.2 + §10.1①）"
        )
    # ── 形状③：关键值断言 ──
    if 判据 == 关键值判据:
        目标 = 产物.get("文件")
        if not isinstance(目标, str) or not 目标:
            raise 形状错(f"{位}：`{关键值判据}` 缺 `文件`（关键值断言要指到比对目标）")
        实路 = Path(目标) if Path(目标).is_absolute() else (目录 / 目标)
        if not 实路.is_file():
            raise 形状错(
                f"{位}：`{关键值判据}` 的比对目标 `{目标}` 在案例目录里**不存在**（{实路}）"
                f"⇒ **断言是坏的**（尺子指到空处，比对时才会炸，且那时已在门禁里）——"
                f"形状.md §10.2：关键值 = 落到案例目录里一个文件，那个文件必须真在"
            )
        return 0
    if 判据 in ("非空字节集", "不判"):
        if 备了关键值:
            报告.append((
                位,
                f"期望停在 `{判据}`，而案例目录里已备 `{期望结果文件名}`（关键值就在手边）"
                f"⇒ 纯确定性不许只写「非空」/「不判」（形状.md §10.1③）",
                判定_违反,
            ))
            return 0
        报告.append((
            位,
            f"期望是 `{判据}` 且没有 `{期望结果文件名}` ⇒ 本案例还没到「写关键值」那一步"
            f"（如实报未判，不算通过）",
            判定_未判,
        ))
        return 1
    return 0


def 查一份(目录: Path, 期望: dict, 报告: list) -> int:
    """查一份 `期望.json`。返回未判条数。"""
    名 = 目录.name
    步表 = 期望.get("步骤")
    if not isinstance(步表, list) or not 步表:
        raise 形状错(f"{名}/期望.json：`步骤` 缺失、不是数组、或是空集（空集不算通过）")
    备了关键值 = (目录 / 期望结果文件名).is_file()
    未判 = 0
    for 序, 步 in enumerate(步表):
        if not isinstance(步, dict):
            raise 形状错(f"{名}/期望.json 步骤[{序}]：不是对象")
        未判 += 查一步(目录, 步, f"{名}/期望.json 步骤[{序}]", 备了关键值, 报告)
    return 未判


def 扫案例(根: Path) -> tuple:
    """扫案例根下每一份 `期望.json` ⇒ (报告, 工具错误或 None)。"""
    报告 = []
    未判 = 0
    有案例 = False
    for 目录 in sorted(一个 for 一个 in 根.iterdir() if 一个.is_dir()):
        期 = 目录 / "期望.json"
        if not 期.is_file():
            continue  # 非案例目录（`跑案例/` 那类）
        有案例 = True
        try:
            未判 += 查一份(目录, 读JSON(期), 报告)
        except 形状错 as 错:
            return [], str(错)
    if not 有案例:
        return [], f"案例根 {根} 下 0 份 期望.json —— 空集不算通过（判据的可信性.md 第二节）"
    return 报告, None


def 查根(根: Path) -> int:
    """查一个案例根并打读数。返回退出码（0 = 无违反无未判）。"""
    报告, 错 = 扫案例(根)
    if 错:
        print(f"工具错误：{错}", file=sys.stderr)
        return 2
    违反 = [条 for 条 in 报告 if 条[2] == 判定_违反]
    未判 = [条 for 条 in 报告 if 条[2] == 判定_未判]
    print(f"形状检查：违反 {len(违反)} 条 · 未判 {len(未判)} 条 · 案例根 {根}")
    for 位, 说, _ in 违反:
        print(f"- 违反 ｜ {位} ｜ {说}")
    for 位, 说, _ in 未判:
        print(f"- 未判 ｜ {位} ｜ {说}")
    return 0 if (not 违反 and not 未判) else 1
