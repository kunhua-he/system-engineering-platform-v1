# -*- coding: utf-8 -*-
"""反馈源样本 —— 清点/回填的**索引稳定与异常反例**（真跑，不联网、不写原件）。

覆盖：归属过滤（root / root 子目录 / 官方工作树 / 旧项目不误吞）· 终态自算（status 撒谎）·
失败类别 · 载荷构造（有/无指纹）· 内容重复保来源 · 分页边界 · 快照落盘。
"""

import hashlib
import json
import tempfile
from pathlib import Path

from . import 反馈源清点 as 清点
from . import 反馈源回填 as 回填


def 建假源(基准根: Path, 代理号: str, 工作目录: str, 状态: str, 输出文本=None) -> None:
    """在假客户端根下造一份代理目录（`metadata.json` + 可选 `output.txt`）。"""
    代理目录 = Path(基准根) / ("sess_%s" % 代理号) / ("agent_%s" % 代理号)
    代理目录.mkdir(parents=True, exist_ok=True)
    元数据 = {"agentId": "agent_%s" % 代理号, "cwd": 工作目录, "status": 状态,
            "createdAt": "2026-10-08T00:00:00.000Z", "updatedAt": "2026-10-08T00:00:01.000Z",
            "completedAt": None, "description": "样本", "profileId": "样本",
            "parentSessionId": "sess_%s" % 代理号, "totalToolUseCount": 1}
    (代理目录 / "metadata.json").write_text(json.dumps(元数据, ensure_ascii=False), encoding="utf-8")
    if 输出文本 is not None:
        (代理目录 / "output.txt").write_text(输出文本, encoding="utf-8")


def 归属样本() -> list:
    """归属过滤正反例：本体 / 子目录 / 工作树收，旧项目与前缀干扰不收。"""
    基准根 = "/proj/假项目根"
    工作树根基 = 基准根 + ".工作树"
    用例 = [
        (基准根, True), (基准根 + "/开发工具", True), (工作树根基, True),
        (工作树根基 + "/v1-100618", True),
        ("/proj/旧项目", False), ("/proj/假项目根x", False),
        (基准根 + ".工作树x", False), ("", False), (None, False),
    ]
    return [("归属 %s" % (值,), 清点.归属本项目(值, 基准根, 工作树根基) == 期望) for 值, 期望 in 用例]


def 终态样本() -> list:
    """终态自算：completed/failed 为终态，running 一律待核（缺件 / 空报告 / 有输出）。"""
    用例 = [
        ("completed", 100, "完成", "未读"),
        ("failed", 40, "失败", "未读"),
        ("running", None, "待核", "缺件待核"),
        ("running", 0, "待核", "空报告待核"),
        ("running", 55, "待核", "未读"),
    ]
    return [("终态 %s/%s" % (状态, 字节), 清点.判终态(状态, 字节) == (终态, 读取档))
            for 状态, 字节, 终态, 读取档 in 用例]


def 失败类别样本() -> list:
    """失败错误分类：模型请求失败 / 上游中断 / 其他。"""
    用例 = [("Model request failed.", "模型请求失败"),
          ("Upstream response stream ended before completion", "上游中断"),
          ("Upstream response stream was interrupted", "上游中断"),
          ("别的", "其他失败")]
    return [("类别 %s" % 判定文本[:12], 清点.失败类别(判定文本) == 期望) for 判定文本, 期望 in 用例]


def 载荷样本() -> list:
    """载荷构造：有指纹 / 无指纹（缺件）· 状态透传 · 条目恒空。"""
    有指纹载荷 = 回填.构造载荷({"来源标识": "agent_1", "报告指纹": "a" * 64,
                        "报告路径": "/p", "读取状态": "已读"})
    无指纹载荷 = 回填.构造载荷({"来源标识": "agent_2", "报告指纹": None, "读取状态": "缺件待核"})
    缺状态载荷 = 回填.构造载荷({"来源标识": "agent_3", "报告指纹": "b" * 64})
    return [
        ("载荷有指纹", 有指纹载荷["报告指纹"] == "a" * 64 and 有指纹载荷["条目"] == []
         and "agent_1" in 有指纹载荷["幂等键"]),
        ("载荷无指纹", 无指纹载荷["报告指纹"] is None and "无指纹" in 无指纹载荷["幂等键"]),
        ("载荷状态透传", 无指纹载荷["读取状态"] == "缺件待核"),
        ("缺状态默认未读", 缺状态载荷["读取状态"] == "未读"),
    ]


def 指纹样本() -> list:
    """指纹口径：空文件取 sha256(空字节)；缺件（无 output）指纹为 None。"""
    with tempfile.TemporaryDirectory() as 临时根:
        假源根 = Path(临时根) / "agents"
        建假源(假源根, "6", "/proj/假项目根", "completed", "")
        建假源(假源根, "7", "/proj/假项目根", "running", None)
        源条目表 = 清点.扫一遍("/proj/假项目根", 假源根)
        按号 = {源条目["来源标识"]: 源条目 for 源条目 in 源条目表}
    空哈希 = hashlib.sha256(b"").hexdigest()
    return [
        ("空文件取空字节 sha", 按号["agent_6"]["报告指纹"] == 空哈希
         and 按号["agent_6"]["读取状态"] == "空报告待核"),
        ("缺件指纹为 None", 按号["agent_7"]["报告指纹"] is None
         and 按号["agent_7"]["读取状态"] == "缺件待核"),
    ]


def 扫描样本() -> list:
    """真造假源：归属过滤 · 终态计数 · 重复保来源 · 分页边界（4 条 / 每页 2 ⇒ 2 页）。"""
    with tempfile.TemporaryDirectory() as 临时根:
        基准根 = Path(临时根) / "假项目根"
        基准根.mkdir()
        根文本 = str(基准根.resolve())
        假源根 = Path(临时根) / "agents"
        建假源(假源根, "1", 根文本, "completed", "有正文")
        建假源(假源根, "2", 根文本 + "/开发工具", "failed", "Model request failed.")
        建假源(假源根, "3", 根文本 + ".工作树/v1-1", "running", None)
        建假源(假源根, "4", "/别的项目", "completed", "别项目")
        建假源(假源根, "5", 根文本, "completed", "有正文")
        源条目表 = 清点.扫一遍(基准根, 假源根)
        读数 = 清点.汇总(源条目表)
        快照 = 清点.分页快照(源条目表, Path(临时根) / "快照", 页大小=2)
    return [
        ("扫描只收本项目 4 条", len(源条目表) == 4),
        ("别项目不误吞", all(源条目["来源标识"] != "agent_4" for 源条目 in 源条目表)),
        ("工作树算本项目", any(源条目["来源标识"] == "agent_3" for 源条目 in 源条目表)),
        ("终态计数", 读数["终态计数"] == {"完成": 2, "失败": 1, "待核": 1}),
        ("缺件待核", 读数["读取计数"]["缺件待核"] == 1),
        ("有输出记未读", 读数["读取计数"]["未读"] == 3),
        ("失败类别", 读数["失败计数"]["模型请求失败"] == 1),
        ("重复组保来源", 读数["重复组数"] == 1
         and len(next(iter(读数["重复组"].values()))) == 2),
        ("分页 4 条 2 页", 快照["页数"] == 2),
    ]


def 样本列表() -> list:
    """全部样本（顺序即执行序）。"""
    return 归属样本() + 终态样本() + 失败类别样本() + 载荷样本() + 指纹样本() + 扫描样本()


def 样本入口() -> int:
    """跑全部样本 ⇒ 退出码（0 全过）。"""
    样本 = 样本列表()
    for 说明, 通过 in 样本:
        print("%s %s" % ("OK" if 通过 else "FAIL", 说明))
    失败数 = sum(1 for _, 通过 in 样本 if not 通过)
    print("样本 %d 条，失败 %d 条" % (len(样本), 失败数))
    return 1 if 失败数 else 0
