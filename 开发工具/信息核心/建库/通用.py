# -*- coding: utf-8 -*-
"""建库 · 通用 —— 读件与扫件：源件读器 · 全仓 md 扫描。

★ `读JSON件` / `读文本` 的错误策略是**有意的（吞 `OSError`/`ValueError` → `None` ·
吞 `OSError` → `""`）** —— 本包是**抽取器**，读器只做「读得到就读、读不到给空」：源件在不在、
坏不坏由上层处置（`装表` 先判「有源件」再决定要不要重抽；`读源件` 明写「读不动就炸，绝不
返回空」）。与别处同名读器（`形状检查/形状.py` 不吞原样抛 · `生成声明/小工具.py` 抛
`生成失败` · `查文件行数/核心.py` 不吞 `OSError` · `代码地图/形参面.py` `replace` 且吞
`OSError` 返空串）**不是同一事实，勿合并**。
"""
import json
from pathlib import Path

from .路径 import 仓根  # noqa: F401,E402 —— 先挂 sys.path（须在下面那条 import 之前）
from 代码地图.落点 import 排除目录  # noqa: E402


def 读JSON件(路径: Path):
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
    跳过 = set(排除目录) | {"__pycache__", "node_modules", "target"}  # 段形态主人（落点.排除目录）+ 本面增量
    查询读数 = []
    for 路径 in 根目录.rglob("*.md"):
        if any(路径段 in 跳过 for 路径段 in 路径.relative_to(根目录).parts):
            continue
        查询读数.append(路径.relative_to(根目录).as_posix())
    return sorted(查询读数)
