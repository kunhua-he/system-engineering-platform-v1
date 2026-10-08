# -*- coding: utf-8 -*-
"""反馈样本工具 —— 反馈样本共用的取数与造账（常量 · 台账号 · 树头 · 回执 · 造开工）。

**为什么单开一件**（判据 ⑲ 单件 ≤400 行）：三件样本（`反馈样本.py` · `反馈核验样本.py` ·
`反馈并发样本.py`）都要「取真实台账号 / 取树头 / 读回执 / 造临时开工」—— 抽到一处，
三件各自读得完，也不成环（本件不 import 任何样本件）。
"""

import json
from pathlib import Path

from . import 反馈账本

反馈开工号 = "v1-900001"
核验开工号 = "v1-900002"
并发号 = "v1-900003"
# 空报告的指纹**唯一来源**是 `反馈账本.空字节报告指纹`（校验与样本同源，不许各写一份字面量）。
空字节指纹 = 反馈账本.空字节报告指纹
反馈表集 = frozenset({"反馈来源", "反馈条目", "反馈判词", "反馈证据", "反馈批次", "反馈关闭"})


def 取台账号(仓根) -> tuple:
    """真实台账里取 `(现存号, 必不存在号)` —— 不写死号（台账会漂）。"""
    台账件 = Path(仓根) / "开发工具" / "信息核心" / "未完成.json"
    正文 = json.loads(台账件.read_text(encoding="utf-8"))
    号表 = [台账行[0] for 台账行 in 正文.get("行") or []
          if isinstance(台账行, list) and 台账行 and isinstance(台账行[0], int)]
    现存号 = max(号表) if 号表 else 1
    return 现存号, 现存号 + 900000


def 取树头(仓根) -> str:
    """本树 HEAD（`git rev-parse`）—— 关闭样本的承接提交用；读不到给空串。"""
    from .仓操作 import 跑命令
    退出码, 输出文本 = 跑命令(["git", "rev-parse", "HEAD"], cwd=仓根)
    return 输出文本.strip() if 退出码 == 0 else ""


def 读回执(回执文本) -> dict:
    """回执文本 ⇒ 字典（非 JSON ⇒ 空字典）。"""
    try:
        读数 = json.loads(回执文本)
    except (TypeError, ValueError):
        return {}
    return 读数 if isinstance(读数, dict) else {}


def 造开工(临时根, 开工号表) -> None:
    """临时根里开一本真账本并登记若干开工（幂等）。"""
    from . import 开工账本
    连接 = 开工账本.连账本()
    try:
        for 开工号 in 开工号表:
            if not 开工账本.读开工(连接, 开工号):
                开工账本.登记开工(连接, 开工号, "反馈样本腿", "腿/" + 开工号,
                            str(临时根 / 开工号))
    finally:
        连接.close()
