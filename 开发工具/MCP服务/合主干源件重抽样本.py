# -*- coding: utf-8 -*-
"""合主干源件重抽样本 —— 源件权威（`未完成.json`）重抽的**正反**样本（临时真仓 + 真 git）。

收口方实测的缺陷：三方重放对源件权威表（`未完成` · 活 md 的 `条款` 片）只「跳过」并说
「建库 重抽」，却从不真跑 ⇒ 合主干绿而库台账仍旧（实测 `未完成.json` 四行、库只两行）。
本件给五态：① 台账only（腿只改 JSON）⇒ 合主干后库 == JSON；② 源与台账同变 ⇒ 库 == JSON；
③ 派生表only（腿只动不受版本的表）⇒ 无损失、库仍 == JSON；④ 恢复现场 ⇒ 库 == JSON；
⑤ 反例：仓内建源库失败 ⇒ 拒、主干不动、现场保留（fail-closed）；
⑥ 反例：主干已推进后**对齐本机生成物失败** ⇒ 如实报「主干已推进 · 对齐未完成」、现场保留、
   主干确已前进（不假称整体合并零写）；`--对齐索引` 同提交重试 + `--清理现场` 收尾。

夹具是系统临时目录里的真仓，跑完删净；子进程一律走仓内 `干净环境()`。
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from . import 合主干编排 as 编排, 合主干集成树 as 集成, 集成接管
from .现场清理样本 import 假信息核心源码, _跑git, _搭基座, _建腿树, _改库, _读库值, _开工记录

源件重抽态表 = ("台账only", "源与台账同变", "派生表only", "恢复现场", "建源库失败", "对齐失败")


def _写台账(树根, 台账行表):
    """把 `未完成.json` 写成源件形态（`{"说明": …, "行": [[…], …]}`）。"""
    JSON件 = 树根 / "开发工具/信息核心/未完成.json"
    JSON件.parent.mkdir(parents=True, exist_ok=True)
    JSON件.write_text(json.dumps({"说明": "样本台账", "行": 台账行表}, ensure_ascii=False),
                   encoding="utf-8")


def _读未完成行表(库件):
    """读库 `未完成` 四栏 ⇒ 行表（按 `号` 排序）。"""
    连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
    try:
        return sorted(tuple(数据行) for 数据行 in
                      连接.execute("select 号, 缺什么, 落点, 验证命令 from 未完成"))
    finally:
        连接.close()


def _建源件夹具(临时根, 名称):
    """建源件重抽夹具 ⇒ (主目录, 腿树, 台账行表)。"""
    主目录 = _搭基座(临时根)
    _改库(主目录, "create table if not exists 未完成 (号 integer primary key, 缺什么 text, 落点 text, 验证命令 text)")
    _改库(主目录, "insert or replace into 未完成 values (7, '基缺', '基落点', '基验证')")
    _写台账(主目录, [[7, "基缺", "基落点", "基验证"]])
    if 名称 == "建源库失败":
        信息核心件 = 主目录 / "开发工具/信息核心/信息核心.py"
        信息核心件.write_text(假信息核心源码.replace(
            "if 子命令 == '建源库':\n",
            "if 子命令 == '建源库':\n    sys.stderr.write('ORIGINAL-建源库-FIRST\\n')\n    raise SystemExit(29)\n"),
            encoding="utf-8")
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "台账基线")
    腿树 = _建腿树(主目录, "v1-999007")
    台账行表 = [[7, "基缺", "基落点", "基验证"]]
    if 名称 == "台账only":
        台账行表 = [[7, "基缺", "基落点", "基验证"], [8, "腿新增", "腿落点", "腿验证"]]
        _写台账(腿树, 台账行表)
    elif 名称 == "源与台账同变":
        台账行表 = [[7, "腿缺", "腿落点", "腿验证"]]
        _写台账(腿树, 台账行表)
        _改库(腿树, "update 未完成 set 缺什么='腿缺' where 号=7")
        _改库(主目录, "update 规则 set 内容='主干值' where 编号=1")
        _跑git(主目录, "add", ".")
        _跑git(主目录, "commit", "-m", "主改源库")
    elif 名称 == "派生表only":
        _改库(腿树, "create table 命名出现 (名字 text primary key, 处数 integer)")
        _改库(腿树, "insert into 命名出现 values ('样本名', 3)")
    elif 名称 in ("恢复现场", "建源库失败"):
        台账行表 = [[7, "缺改", "落点改", "验证改"], [8, "新增", "落点", "验证"]]
        _写台账(腿树, 台账行表)
    (腿树 / "新增.txt").write_text("腿成果\n", encoding="utf-8")
    _跑git(腿树, "add", ".")
    _跑git(腿树, "commit", "-m", "腿成果")
    return 主目录, 腿树, 台账行表


def 验源件重抽():
    """跑源件重抽五态；不过即断言炸 ⇒ 退出码 0（临时仓跑完删净）。"""
    for 名称 in 源件重抽态表:
        with tempfile.TemporaryDirectory(prefix="v1源件重抽-") as 临时目录:
            主目录, 腿树, 台账行表 = _建源件夹具(Path(临时目录), 名称)
            开工记录 = _开工记录(腿树, "v1-999007")
            with mock.patch.object(编排, "_读开工记录", return_value=开工记录), \
                 mock.patch.object(集成接管, "解除接管", return_value=(0, "样本：解除接管跳过")):
                if 名称 == "恢复现场":
                    with mock.patch.object(集成, "同步主工作区", return_value=(31, "样本：同步失败替身")):
                        退出码, 报告文本 = 编排.派发("v1-999007", False, 主目录)
                    assert 退出码 != 0 and "同步失败替身" in 报告文本, 报告文本
                    退出码, 报告文本 = 编排.派发("v1-999007", False, 主目录, 操作="恢复现场")
                elif 名称 == "对齐失败":
                    with mock.patch.object(集成, "对齐本机生成物",
                                         return_value=(1, "样本：索引重建失败替身")):
                        退出码, 报告文本 = 编排.派发("v1-999007", False, 主目录)
                else:
                    退出码, 报告文本 = 编排.派发("v1-999007", False, 主目录)
            树在 = 集成.找集成树(主目录, "v1-999007") is not None
            if 名称 == "对齐失败":
                # 主干已推进 · 对齐未完成：如实报（不假称整体合并零写）· 现场保留 · 主干确已前进
                assert 退出码 != 0 and "主干已推进" in 报告文本 and "对齐未完成" in 报告文本, 报告文本
                assert "索引重建失败替身" in 报告文本 and "失败现场保留" in 报告文本 and 树在, 报告文本
                assert _跑git(主目录, "log", "-1", "--format=%s", "主干") != "台账基线", 报告文本
                # 同提交重试（不重复推进）：--对齐索引 成功；再 --清理现场 收尾
                退出码, 报告文本 = 编排.派发("v1-999007", False, 主目录, 操作="对齐索引")
                assert 退出码 == 0 and "跳过" in 报告文本, 报告文本
                退出码, 报告文本 = 编排.派发("v1-999007", False, 主目录, 操作="清理现场")
                assert 退出码 == 0 and 集成.找集成树(主目录, "v1-999007") is None, 报告文本
            elif 名称 == "建源库失败":
                assert 退出码 != 0 and "ORIGINAL-建源库-FIRST" in 报告文本 and "失败现场保留" in 报告文本, 报告文本
                assert 树在, 报告文本
                assert _读库值(主目录 / 编排.库相对路径, "select 缺什么 from 未完成 where 号=7") == "基缺", 报告文本
            else:
                assert 退出码 == 0 and not 树在, 报告文本
                assert _读未完成行表(主目录 / 编排.库相对路径) == sorted(tuple(数据行) for 数据行 in 台账行表), 报告文本
                if 名称 == "派生表only":
                    assert _读库值(主目录 / 编排.库相对路径, "select 内容 from 规则 where 编号=1") == "基值"
                if 名称 == "台账only":
                    assert "仓内建源库" in 报告文本 and "核源库" in 报告文本, 报告文本
            print("通过 源件重抽", 名称, "退出码", 退出码)
    return 0
