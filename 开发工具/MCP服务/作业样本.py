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
    for 工具名, 期望操作 in (("v1_job", {"start", "status", "log", "cancel"}), ("v1_search", {"搜索"})):
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
    return 样本表 + 异步短样本(仓根, 工具表)


def 异步短样本(仓根, 工具表):
    """临时运行数据根内跑真实start/status/log/cancel。"""
    from . import 作业
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="v1-job-sample-") as 临时根:
        with patch.dict(os.environ, {覆盖变量名: 临时根, "PYTHONPATH": str(仓根)}), patch.dict(
                作业.具名作业表, {"闸0": "python3 -B -c 'print(12345)'"}):
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
                    "退出码：0" in 说明 if 操作名 == "status" else "12345" in 说明 if 操作名 == "log" else "终态" in 说明)))
            if 作业.读行(任务ID)["状态"] not in 作业.终态集:
                作业.取消作业(任务ID)
            作业.收僵尸()
    return 样本表
