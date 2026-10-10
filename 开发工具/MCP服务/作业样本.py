# -*- coding: utf-8 -*-
"""作业正反样本；隔离短替身不推进主线、不访问远端。"""
import json
import os
import re
import shlex
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import patch
from 开发工具.运行数据根.口径 import 覆盖变量名


def 作业样本(仓根, 工具表):
    """检查真实工具声明、拒绝与固定合并命令的目标转发。"""
    from . import 作业
    样本表 = []
    for 工具名, 期望操作 in (("v1_job", {"start", "list", "status", "log", "cancel", "启动", "查", "日志", "取消"}),
                        ("v1_search", {"搜索"})):
        if 工具名 not in 工具表:
            样本表.append((工具名 + "注册缺失", False))
            continue
        退出码, 输出文本 = 工具表[工具名][0]({}, 仓根)
        结果表 = json.loads(输出文本)["结果"]["操作目录"]
        样本表.append((工具名 + "注册与空发现", 退出码 == 0 and set(结果表) == 期望操作))
    if "v1_job" not in 工具表:
        return 样本表
    for 实参 in (
        {"操作": "start", "参数": {"具名": "未知"}},
        {"操作": "start", "参数": {"具名": "闸0", "命令": "任意代码"}},
        {"操作": "write"},
        {"操作": "start", "参数": {"具名": "合主线", "作业参数": {"路径": "/tmp"}}},
        {"操作": "start", "参数": {"具名": "合主线", "作业参数": {"目标开工ID": "v1-100001", "推送": "假"}}},
    ):
        with patch.object(作业, "起作业") as 启动替身:
            退出码, 输出文本 = 工具表["v1_job"][0](实参, 仓根)
            样本表.append(("作业拒未知具名/参数/写操作：" + str(实参), 退出码 == 2 and not 启动替身.called))
    模块名 = 作业.__package__ + ".合主干集成树"
    定位替身 = types.ModuleType(模块名)
    定位替身.定位主仓 = lambda 候选目录: (0, Path(仓根))
    with patch.dict(sys.modules, {模块名: 定位替身}):
        for 推送 in (False, True):
            with patch.object(作业, "起作业", return_value=(0, "短替身")) as 启动替身:
                退出码, 输出文本 = 工具表["v1_job"][0]({"开工ID": "v1-100002", "操作": "start", "参数": {
                    "具名": "合主线", "作业参数": {"目标开工ID": "v1-100001", **({"推送": True} if 推送 else {})}}}, 仓根)
                命令表 = shlex.split(启动替身.call_args.args[0]) if 启动替身.called else []
                样本表.append(("合主线目标与定位号分离、默认不推/显式推参数转发", 退出码 == 0
                    and 命令表 == [sys.executable, str(Path(仓根) / "开发工具/MCP服务/合并主干.py"), "v1-100001"]
                        + (["--推送"] if 推送 else []) and 启动替身.call_args.args[1] == "v1-100002"))
        定位替身.定位主仓 = lambda 候选目录: (2, "定位拒绝")
        with patch.object(作业, "起作业") as 启动替身:
            退出码, 输出文本 = 作业.起具名作业("合主线", "", 1, 仓根, {"目标开工ID": "v1-100001"})
            样本表.append(("唯一定位拒绝透传不启动", 退出码 == 2 and not 启动替身.called))
    样本表.append(("标准具名·自测 / 案例在册（一次调用拿结论，不必回落 Bash）",
             作业.具名作业表.get("自测", "").endswith("一键验证.py --自测")
             and 作业.具名作业表.get("案例", "").endswith("-p v1-case-runner")))
    # ★ 放行档：自测**按档跑**（判据面进暂存才跑），与 pre-commit 钩子同一口径 ——
    #   防回潮：本档曾硬跑一遍自测 ⇒ 加上合并提交那一遍就是两遍（实测 48.9 s → 9 s）。
    放行串 = 作业.具名作业表.get("放行", "")
    样本表.append(("标准具名·放行按档跑自测（判据面进暂存才跑；不再硬跑一遍）",
             放行串.count("--自测") == 1
             and "git diff --cached --quiet" in 放行串
             and "构建装配/一键验证 测试验证/案例" in 放行串
             and 放行串.count("闸0.py") == 1
             and 放行串.endswith("-p v1-case-runner")))
    return 样本表 + 异步短样本(仓根, 工具表) + 账本列样本(仓根)


def 异步短样本(仓根, 工具表):
    """临时运行数据根内跑真实start/status/log/cancel。"""
    from . import 作业
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="v1-job-sample-") as 临时根:
        with patch.dict(os.environ, {覆盖变量名: 临时根, "PYTHONPATH": str(仓根)}), patch.dict(
                作业.具名作业表, {"闸0": "\"$V1_PY\" -B -c 'print(12345)'"}):
            退出码, 输出文本 = 工具表["v1_job"][0]({"操作": "start", "参数": {"具名": "闸0", "超时秒": 1}}, 仓根)
            匹配 = re.search(r"任务ID：([0-9a-f]{32})", json.loads(输出文本)["说明"])
            样本表.append(("真实start返回任务ID", 退出码 == 0 and 匹配 is not None))
            if 匹配 is None:
                return 样本表
            任务ID = 匹配.group(1)
            截止时刻 = time.monotonic() + 2
            while time.monotonic() < 截止时刻:
                if 作业.读行(任务ID)["状态"] in 作业.终态集:
                    break
                time.sleep(0.02)
            for 操作名 in ("status", "log", "cancel"):
                退出码, 输出文本 = 工具表["v1_job"][0]({"操作": 操作名, "参数": {"任务ID": 任务ID}}, 仓根)
                说明 = json.loads(输出文本)["说明"]
                样本表.append(("真实" + 操作名 + "短作业", 退出码 == 0 and (
                    ("退出码：0" in 说明 and "开工ID：" in 说明) if 操作名 == "status"
                    else ("12345" in 说明 and "开工ID：" in 说明) if 操作名 == "log"
                    else "终态" in 说明)))
            退出码, 输出文本 = 工具表["v1_job"][0]({"操作": "list"}, 仓根)
            说明 = json.loads(输出文本)["说明"]
            样本表.append(("真实 list 短作业：含该任务ID与「非终态在前」", 退出码 == 0
                      and 任务ID in 说明 and "非终态在前" in 说明))
            退出码, 输出文本 = 工具表["v1_job"][0]({"操作": "list", "参数": {"条数": 999}}, 仓根)
            样本表.append(("list 反向：条数越界 ⇒ 退出码 %d（期望 2）" % 退出码,
                      退出码 == 2 and "条数" in json.loads(输出文本)["说明"]))
            if 作业.读行(任务ID)["状态"] not in 作业.终态集:
                作业.取消作业(任务ID)
            作业.收僵尸()
    return 样本表


def 账本列样本(仓根) -> list:
    """`作业.开工ID` 列：落行可查 + 老库幂等迁移不丢行（临时运行数据根，跑完即删）。

    正：`落新行` 带开工ID ⇒ `读行` 读得回真值。
    反：老库（无 `开工ID` 列、已有一行）经 `连账本` 迁移 ⇒ 补出列且旧行一个字节不丢。
    空：不给开工ID ⇒ 落空串（不编造）。
    """
    import os
    import sqlite3
    import tempfile
    from unittest.mock import patch

    from . import 作业账本

    样本表 = []
    with tempfile.TemporaryDirectory(prefix="v1-账本列-") as 临时根:
        with patch.dict(os.environ, {覆盖变量名: 临时根}):
            库件 = 作业账本.作业账本路径()
            库件.parent.mkdir(parents=True, exist_ok=True)
            连接 = sqlite3.connect(str(库件))
            try:
                连接.execute(
                    "create table 作业 (任务ID text primary key, 状态 text not null, "
                    "命令 text not null, 工作树 text not null, 开始时间 text not null, "
                    "完成时间 text, 退出码 integer, 组号 integer, 组代次 text, 命令组号 integer, "
                    "命令代次 text, 截断 integer not null default 0, 说明 text)")
                连接.execute("insert into 作业 (任务ID, 状态, 命令, 工作树, 开始时间) "
                          "values (?, ?, ?, ?, ?)", ("a" * 32, "已完成", "echo", "/tmp", "2026-01-01"))
                连接.commit()
            finally:
                连接.close()
            作业账本.落新行("b" * 32, "echo 2", "/tmp", "2026-01-02", "v1-100999")
            作业账本.落新行("c" * 32, "echo 3", "/tmp", "2026-01-03")
            旧行 = 作业账本.读行("a" * 32)
            新行 = 作业账本.读行("b" * 32)
            空行 = 作业账本.读行("c" * 32)
        样本表.append(("老库迁移补出 开工ID 列且旧行不丢：%s"
                 % ("旧行在" if 旧行 is not None and 旧行["状态"] == "已完成" else "旧行丢了"),
                 旧行 is not None and 旧行["状态"] == "已完成" and "开工ID" in 旧行.keys()))
        样本表.append(("落新行写 开工ID 可查（值 %s）" % (新行["开工ID"] if 新行 else None),
                 新行 is not None and 新行["开工ID"] == "v1-100999"))
        样本表.append(("不给开工ID ⇒ 落空串（不编造）：%r" % (空行["开工ID"] if 空行 else None),
                 空行 is not None and not 空行["开工ID"]))
    return 样本表
