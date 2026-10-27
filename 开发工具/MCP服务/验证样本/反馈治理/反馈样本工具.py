# -*- coding: utf-8 -*-
"""反馈样本工具 —— 反馈样本共用的取数与造账（常量 · 台账号 · 树头 · 回执 · 造开工）。

**为什么单开一件**（判据 ⑲ 单件 ≤400 行）：三件样本（`反馈样本.py` · `反馈核验样本.py` ·
`反馈并发样本.py`）都要「取真实台账号 / 取树头 / 读回执 / 造临时开工」—— 抽到一处，
三件各自读得完，也不成环（本件不 import 任何样本件）。
"""

import json
from pathlib import Path

from ...反馈治理 import 反馈账本

反馈开工号 = "v1-900001"
核验开工号 = "v1-900002"
并发号 = "v1-900003"
# 空报告的指纹**唯一来源**是 `反馈账本.空字节报告指纹`（校验与样本同源，不许各写一份字面量）。
空字节指纹 = 反馈账本.空字节报告指纹
反馈表集 = frozenset(反馈账本.反馈表名表)


def 取台账号(仓根) -> tuple:
    """真实台账（库 `未完成` 表）里取 `(现存号, 必不存在号)` —— 不写死号（台账会漂）。"""
    import sqlite3
    台账库路径 = Path(仓根) / "开发工具" / "信息核心" / "信息核心.db"
    连接 = sqlite3.connect("file:%s?mode=ro" % 台账库路径, uri=True)
    try:
        号表 = [数据行[0] for 数据行 in 连接.execute("select 号 from 未完成")]
    finally:
        连接.close()
    现存号 = max(号表) if 号表 else 1
    return 现存号, 现存号 + 900000


def 取树头(仓根) -> str:
    """本树 HEAD（`git rev-parse`）—— 关闭样本的承接提交用；读不到给空串。"""
    from ...施工管理.仓操作 import 跑命令
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
    from ... import 开工账本
    连接 = 开工账本.连账本()
    try:
        for 开工号 in 开工号表:
            if not 开工账本.读开工(连接, 开工号):
                开工账本.登记开工(连接, 开工号, "反馈样本腿", "腿/" + 开工号,
                            str(临时根 / 开工号))
    finally:
        连接.close()


def 造夹具仓根(临时根) -> Path:
    """给「按仓根读台账 / 校验承接提交」的样本造一个**夹具仓根**：自带 `未完成` 一行 + 一个真提交。

    **为什么要它**：`承接有效` 的台账那一支读的是**调用方给的仓根**下的 `未完成` 表；
    台账核销到 0 行后，债务正例必然被判「未知台账条目」（码 2），连带审完 / 未蒸馏 /
    关闭 / 对账一起红 —— 夹具不许靠真实台账里恰好有行，得由夹具自建一行（真仓台账保持 0 行）。
    """
    import sqlite3

    from ...施工管理.仓操作 import 跑命令
    仓根 = Path(临时根) / "夹具仓"
    库件 = 仓根 / "开发工具" / "信息核心" / "信息核心.db"
    库件.parent.mkdir(parents=True, exist_ok=True)
    if not 库件.is_file():
        连接 = sqlite3.connect(str(库件))
        连接.execute("create table 未完成(号 integer primary key, 缺什么 text, 落点 text, 验证命令 text)")
        连接.execute("insert into 未完成(号, 缺什么, 落点, 验证命令) values (1, '夹具台账行（样本自建，不代表真实债务）', "
                 "'开发工具/信息核心/信息核心.db', 'python3 构建装配/一键验证/闸0.py')")
        连接.commit()
        连接.close()
    if not (仓根 / ".git").is_dir():
        跑命令(["git", "init", "-q"], cwd=仓根)
        跑命令(["git", "add", "-A"], cwd=仓根)
        跑命令(["git", "-c", "user.name=样本", "-c", "user.email=样本@样例",
              "commit", "-qm", "夹具仓根"], cwd=仓根)
    return 仓根
