# -*- coding: utf-8 -*-
"""反馈关联 —— 判词**承接校验**与**未蒸馏判据**（唯一口）。

**为什么单开一件**：判词要关联「唯一现行台账条目」或「正式开工」，这要读 `未完成.json`
与开工账本 —— 把它与纯存储分开 ⇒ `反馈账本.py` 不反向依赖业务口径，也不与它成环。

**未蒸馏判据的唯一口** = `未蒸馏反馈集`：收口清理与单纯释放都引它，别处不许自建第二套。
口径（收口方 2026-10-08 纠正）：**已审完 + 已判词 + 有效承接** ⇒ 视为**已蒸馏**，
原腿可清、反馈与处置证据永久保留；只有下面三条任一成立才拒：
  ① 报告未审完（含空报告 / 缺件显式待核）；
  ② 有未判词条目（已并入主条目且主条目有判词者不算）；
  ③ **债务无有效承接**（关联空、或解析不到现行台账条目 / 正式开工）；
  ④ 待核且**有具体保留对象**（带补证证据，或关联目标非空）—— 待核本身**不**一律阻断。
"""

import json
from pathlib import Path

from . import 反馈账本 as 账本

台账相对路径 = ("开发工具", "信息核心", "未完成.json")


def 有反馈表(连接) -> bool:
    """库里是否已有反馈表（`反馈来源`）—— **没有 ⇒ 从未记过反馈**（合法空态，不是错误）。

    为什么要有它（2026-10-08 承接实测）：本件在场 ⇒ `清树门禁.未蒸馏反馈行` 走 fail-closed；
    可一本**从没记过反馈**的账本（老库 / 样本夹具）根本没有六表 ⇒ 裸 SQL 抛 `no such table`
    ⇒ 被当「保护口读不出」⇒ **每次单纯释放都被误拒**。缺表 = 无反馈 ⇒ 未蒸馏必空。
    """
    数据行 = 连接.execute("select count(*) from sqlite_master where type = 'table' and name = ?",
                     ("反馈来源",)).fetchone()
    return bool(数据行 and 数据行[0])


def 读台账号集(仓根) -> set:
    """`未完成.json` 的**现行条目号**集；件不在 / 读不动 ⇒ 空集（调用方 fail-closed 当无效）。"""
    台账件 = Path(仓根).joinpath(*台账相对路径)
    if not 台账件.is_file():
        return set()
    try:
        正文 = json.loads(台账件.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    号集 = set()
    for 台账行 in 正文.get("行") or []:
        if isinstance(台账行, list) and 台账行 and isinstance(台账行[0], int):
            号集.add(台账行[0])
    return 号集


def 承接有效(连接, 仓根, 关联种类, 关联目标) -> bool:
    """判词的关联是否**有效承接**：唯一现行台账条目 / 真实开工。**未知即假**（fail-closed）。"""
    种类值 = str(关联种类 or "").strip()
    目标值 = str(关联目标 or "").strip()
    if not 种类值 or not 目标值:
        return False
    if 种类值 == 账本.关联_台账:
        try:
            号值 = int(目标值)
        except (TypeError, ValueError):
            return False
        return 号值 in 读台账号集(仓根)
    if 种类值 == 账本.关联_开工:
        return 账本.开工在吗(连接, 目标值)
    return False


def 未蒸馏反馈集(连接, 仓根, 开工号: str) -> list:
    """本开工**未蒸馏**的反馈 ⇒ 行表（**非空 ⇒ 收口清理拒**）。**唯一判据口**。

    `仓根` **必须显式传入**（要读该树的 `未完成.json`）—— 不许猜主干 / 旧树。
    """
    行表 = []
    if not 有反馈表(连接):
        return 行表
    for 数据行 in 连接.execute(
            "select 来源号, 来源标识, 读取状态, 提取条数 from 反馈来源 "
            "where 开工号 = ? and 审完时刻 is null order by 来源号", (开工号,)):
        行表.append("未审完来源 %d（%s · 读取状态 %s · 提取 %d 条）"
                 % (数据行["来源号"], 数据行["来源标识"], 数据行["读取状态"], 数据行["提取条数"]))
    for 数据行 in 连接.execute(
            "select 条目号, 现象 from 反馈条目 where 开工号 = ? "
            "and not exists(select 1 from 反馈判词 where 反馈判词.条目号 = 反馈条目.条目号) "
            "and not exists(select 1 from 反馈判词 where 反馈判词.条目号 = 反馈条目.并入主条目) "
            "order by 条目号", (开工号,)):
        行表.append("未判词条目 %d：%s" % (数据行["条目号"], 账本.截断(数据行["现象"])))
    for 数据行 in 连接.execute(
            "select 反馈判词.条目号, 反馈判词.关联种类, 反馈判词.关联目标 from 反馈判词 "
            "join 反馈条目 on 反馈判词.条目号 = 反馈条目.条目号 "
            "where 反馈条目.开工号 = ? and 反馈判词.判词 = ? order by 反馈判词.条目号",
            (开工号, 账本.判词_债务)):
        if not 承接有效(连接, 仓根, 数据行["关联种类"], 数据行["关联目标"]):
            行表.append("债务无有效承接 %d（关联 %s %s）"
                    % (数据行["条目号"], 数据行["关联种类"] or "（未记）",
                       数据行["关联目标"] or "（未记）"))
    for 数据行 in 连接.execute(
            "select 反馈判词.条目号, 反馈判词.理由, 反馈判词.关联目标, "
            "(select count(*) from 反馈证据 where 反馈证据.条目号 = 反馈判词.条目号) as 补证数 "
            "from 反馈判词 join 反馈条目 on 反馈判词.条目号 = 反馈条目.条目号 "
            "where 反馈条目.开工号 = ? and 反馈判词.判词 = ? order by 反馈判词.条目号",
            (开工号, 账本.判词_待核)):
        if 数据行["补证数"] or str(数据行["关联目标"] or "").strip():
            行表.append("待核须保留 %d（补证 %d 条 · 关联 %s）"
                    % (数据行["条目号"], 数据行["补证数"],
                       数据行["关联目标"] or "（无）"))
    return 行表
