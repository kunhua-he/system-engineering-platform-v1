# -*- coding: utf-8 -*-
"""反馈长样本 —— 反馈专项（正反 + 真 stdio/HTTP 帧）+ 真实清树接缝，挂 `长样本.py`（提交放行路）。

**为什么要有它**：反馈样本此前只有独立入口，**没进正式提交放行** —— 判据 ㊽ 的 `--自检` 装不进
（5 秒硬顶），`--长样本`（环境步，预算宽松）才是重回归的正档。本件把两件事拉进同一条路：

  · **反馈专项**：`反馈样本.跑全套`（正反 / 核验 / 重启迁移 / 并发 / 真 stdio+HTTP 帧）；
  · **真实清树接缝**：`清树门禁.核清树条件` 真调 `反馈关联.未蒸馏反馈集`（两边都是真实现，
    不造 `sys.modules` 假模块、不另写第二保护口）—— 未蒸馏非空 ⇒ 拒清。

另附**生产零写核对**：样本跑完，生产运行数据根里没有本样本号的反馈 / 开工行（只读打开）。
本件**不依运行数据根脚本**：仓内自带、可单独启动。
"""

import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from 运行数据根.口径 import 覆盖变量名, 解析当前环境, 子目录路径

接缝开工号 = "v1-900005"


def 生产零写样本() -> list:
    """样本跑完 ⇒ 生产运行数据根里没有本样本号的反馈 / 开工行（**只读**打开，零写核对）。"""
    from . import 开工账本
    暂存 = os.environ.pop(覆盖变量名, None)
    try:
        生产根 = 解析当前环境()
    finally:
        if 暂存 is not None:
            os.environ[覆盖变量名] = 暂存
    库件 = 子目录路径(生产根, "数据库") / 开工账本.库文件名
    if not 库件.is_file():
        return [("生产零写核对：生产库不存在（无对象可写）⇒ 零写", True)]
    连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    try:
        有表 = 连接.execute("select count(*) from sqlite_master where type = 'table' and name = ?",
                       ("反馈来源",)).fetchone()[0]
        有开工表 = 连接.execute("select count(*) from sqlite_master where type = 'table' and name = ?",
                         ("开工",)).fetchone()[0]
        反馈行数 = 连接.execute("select count(*) from 反馈来源 where 开工号 = ?",
                          (接缝开工号,)).fetchone()[0] if 有表 else 0
        开工行数 = 连接.execute("select count(*) from 开工 where 开工号 = ?",
                          (接缝开工号,)).fetchone()[0] if 有开工表 else 0
    finally:
        连接.close()
    return [("生产零写核对：生产运行数据根里 反馈来源 %d 条 · 开工 %d 条（本样本号 %s · 只读打开）"
             % (反馈行数, 开工行数, 接缝开工号), 反馈行数 == 0 and 开工行数 == 0)]


def 清树接缝样本(仓根) -> list:
    """真接缝：`清树门禁`（615 真实现）真调 `反馈关联.未蒸馏反馈集`（613 真实现）⇒ 样本表。

    **本件自带隔离**：把运行数据根指到临时根，不靠调用方 —— 本件会被 `长样本.py` 直接调
    （外层无覆盖）⇒ 不隔离就会把夹具开工与反馈**写进生产库**（实测踩到，`生产零写样本` 当场红）。
    """
    from . import 开工账本, 反馈账本, 反馈提交, 反馈判词, 反馈审完, 清树门禁
    临时根 = Path(tempfile.mkdtemp(prefix="v1反馈接缝-"))
    旧值 = os.environ.get(覆盖变量名)
    os.environ[覆盖变量名] = str(临时根)
    样本表 = []

    def 记样本(说明, 通过):
        样本表.append((说明, bool(通过)))

    try:
        临时仓 = 临时根 / "仓"
        (临时仓 / "开发工具/信息核心").mkdir(parents=True)
        (临时仓 / "开发工具/信息核心/未完成.json").write_text(
            json.dumps({"行": [[311, "接缝验收现存"]]}, ensure_ascii=False), encoding="utf-8")
        连接 = 开工账本.连账本()
        try:
            开工账本.登记开工(连接, 接缝开工号, "接缝验收腿", "腿/" + 接缝开工号, str(临时根 / "树"))
        finally:
            连接.close()
        记样本("接缝·反馈保护口在场（`反馈关联.py` 与 `清树门禁.py` 同目录）",
           清树门禁.反馈保护启用() is True)
        退出码, 回执 = 反馈提交.提交反馈(临时仓, 接缝开工号, {
            "幂等键": "接缝-001", "来源标识": "接缝/报告.md", "报告指纹": "ab" * 16,
            "条目": [{"现象": "接缝发现", "证据": "读数", "未测": "落点未定位"}]})
        读数 = json.loads(回执) if 回执.strip().startswith("{") else {}
        条目号 = (读数.get("条目号") or [None])[0]
        来源号 = 读数.get("来源号")
        记样本("接缝·反馈真实现 提交反馈 码 %s · 来源号 %s · 条目号 %s" % (退出码, 来源号, 条目号),
           退出码 == 0)
        连接 = 反馈账本.连反馈库()
        try:
            未蒸馏 = 清树门禁.未蒸馏反馈行(连接, 临时仓, 接缝开工号)
        finally:
            连接.close()
        记样本("接缝·清树真口 未审完 + 未判词 ⇒ 非空（%d 条）" % len(未蒸馏), len(未蒸馏) >= 2)
        反馈判词.批量判定(临时仓, 接缝开工号, {"判定表": [
            {"条目号": 条目号, "判词": "债务", "理由": "接缝债务",
             "关联种类": "未完成条目", "关联目标": "311"}]})
        反馈审完.登记报告审完(临时仓, 接缝开工号,
                       {"来源号": 来源号, "提取条数": 1, "判词条数": 1})
        连接 = 反馈账本.连反馈库()
        try:
            未蒸馏 = 清树门禁.未蒸馏反馈行(连接, 临时仓, 接缝开工号)
        finally:
            连接.close()
        记样本("接缝·已审完 + 已判词 + 有效承接 ⇒ 空 ⇒ 允许清树（%s）" % 未蒸馏, 未蒸馏 == [])
        连接 = 反馈账本.连反馈库()
        try:
            连接.execute("update 反馈判词 set 关联目标 = ? where 条目号 = ?", ("v1-999999", 条目号))
            连接.commit()
            未蒸馏 = 清树门禁.未蒸馏反馈行(连接, 临时仓, 接缝开工号)
        finally:
            连接.close()
        记样本("接缝·债务承接陈旧失效 ⇒ 拒清（fail-closed）",
           any("无有效承接" in 台账行 for 台账行 in 未蒸馏))
        (临时仓 / "开发工具/信息核心/未完成.json").unlink()
        连接 = 反馈账本.连反馈库()
        try:
            未蒸馏 = 清树门禁.未蒸馏反馈行(连接, 临时仓, 接缝开工号)
        finally:
            连接.close()
        记样本("接缝·台账缺件 ⇒ 承接判无效、拒清",
           any("无有效承接" in 台账行 for 台账行 in 未蒸馏))
        真检查, 真作业 = 清树门禁.检查清树安全, 清树门禁.非终态作业
        清树门禁.检查清树安全 = lambda 仓根, 开工号, 工作树: (0, "接缝夹具：已合主干且净树")
        清树门禁.非终态作业 = lambda 开工号, 工作树: []
        try:
            连接 = 反馈账本.连反馈库()
            try:
                成立, 行表 = 清树门禁.核清树条件(
                    连接, 临时仓, 接缝开工号,
                    {"状态": 开工账本.状态_已释放, "工作树": str(临时根 / "树")})
            finally:
                连接.close()
            记样本("接缝·核清树条件（未蒸馏真口 = 拒）⇒ 不成立",
               成立 is False and any("未蒸馏" in 台账行 and "✗" in 台账行 for 台账行 in 行表))
        finally:
            清树门禁.检查清树安全, 清树门禁.非终态作业 = 真检查, 真作业
    finally:
        if 旧值 is None:
            os.environ.pop(覆盖变量名, None)
        else:
            os.environ[覆盖变量名] = 旧值
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表


def 反馈长样本(仓根) -> tuple:
    """跑反馈专项（全套样本）+ 真实清树接缝 + 生产零写核对 ⇒ `(退出码, 行表)`。"""
    from . import 反馈样本
    样本表 = []
    try:
        样本表 += 反馈样本.跑全套(仓根)
    except BaseException as 错误:
        样本表.append(("反馈专项异常：%r" % (错误,), False))
    try:
        样本表 += 清树接缝样本(仓根)
    except BaseException as 错误:
        样本表.append(("清树接缝异常：%r" % (错误,), False))
    try:
        样本表 += 生产零写样本()
    except BaseException as 错误:
        样本表.append(("生产零写核对异常：%r" % (错误,), False))
    行表 = ["  %s %s" % ("✓" if 通过 else "✗", 说明) for 说明, 通过 in 样本表]
    失败表 = [说明 for 说明, 通过 in 样本表 if not 通过]
    行表.append("反馈专项与清树接缝：共 %d 条 · 失败 %d 条" % (len(样本表), len(失败表)))
    return (1 if 失败表 else 0), 行表
