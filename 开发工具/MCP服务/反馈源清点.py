# -*- coding: utf-8 -*-
"""反馈源清点 —— 客户端代理反馈源的**有界清点**（只读原件 · 不提取问题 · 不判词 · 不删原件）。

**只读两样**：客户端 `~/.zcode/cli/agents/<会话>/<代理>/` 下的 `metadata.json` 与 `output.txt`
（实测 `task.output` 与 `output.txt` 逐字节相同 ⇒ 只锚一份，不双份计数）。

**归属过滤一处实现**：`cwd` 命中 ①项目根本体 ②项目根下的子目录 ③官方工作树
`<项目根>.工作树/<开工号>`（树根与树内都算）。同名前缀的旧项目（无 `V1`）不误吞。

**source 键**：`来源标识 = 代理号` + `报告指纹 = output.txt 内容 sha256`
⇒ 同一代理被 resume 出新报告 = 同标识 + 新指纹 = **新版本行**，旧版本不被覆盖。

**终态自算**：`metadata.status` 会撒谎（实测 12 条进程早死的腿永远写 `running`）⇒
`完成` / `失败`（附错误类别）/ `待核`（running 且无输出 · 空报告 · 缺件，一律待核，**不判永久死**）。

**输出**：分页快照落 `<运行数据根>/临时件/反馈源清点-<随机后缀>/`（唯一目录，绝不清任何旧目录）。
本件零写原件、零改台账。
"""

import hashlib
import json
import secrets
from pathlib import Path

from 运行数据根 import 子目录路径, 解析当前环境

客户端相对 = (".zcode", "cli", "agents")
工作树后缀 = ".工作树"

终态_完成 = "完成"
终态_失败 = "失败"
终态_待核 = "待核"
终态档表 = (终态_完成, 终态_失败, 终态_待核)

读取_未读 = "未读"
读取_已读 = "已读"
读取_空报告 = "空报告待核"
读取_缺件 = "缺件待核"
读取状态档表 = (读取_未读, 读取_已读, 读取_空报告, 读取_缺件)

失败_上游中断 = "上游中断"
失败_模型请求失败 = "模型请求失败"
失败_其他 = "其他失败"
失败类别档表 = (失败_上游中断, 失败_模型请求失败, 失败_其他)
上游片段表 = ("Upstream response stream", "stream ended before completion", "stream was interrupted")
模型片段表 = ("Model request failed",)

分页默认 = 100
重复明细上限 = 50
快照前缀 = "反馈源清点-"


def 客户端根(家目录=None) -> Path:
    """客户端代理源根（默认 `<家目录>/.zcode/cli/agents`）。"""
    return Path(家目录 or Path.home()).joinpath(*客户端相对)


def 项目根(仓根) -> str:
    """项目根绝对路径（去尾斜杠）—— 归属过滤的唯一基准。

    给官方工作树（`<主根>.工作树/<开工号>`）也认：剥回主根 —— 客户端代理的 `cwd` 记的是
    主根与各工作树，本件在腿里跑时也能正确定位。
    """
    基准文本 = str(Path(仓根).resolve()).rstrip("/")
    return 基准文本.split(工作树后缀 + "/", 1)[0] if (工作树后缀 + "/") in 基准文本 else 基准文本


def 工作树根(仓根) -> str:
    """官方工作树根 = 项目根 + `.工作树`（仓根的兄弟目录）。"""
    return 项目根(仓根) + 工作树后缀


def 归属本项目(工作目录, 基准根: str, 工作树根基: str) -> bool:
    """`cwd` 是否属本项目：项目根本体 / 项目根子目录 / 官方工作树（树根与树内）。"""
    判定文本 = str(工作目录 or "").rstrip("/")
    if not 判定文本:
        return False
    for 归属前缀 in (基准根, 工作树根基):
        if 判定文本 == 归属前缀 or 判定文本.startswith(归属前缀 + "/"):
            return True
    return False


def 失败类别(判定文本: str) -> str:
    """终态失败的**错误类别**（只按已知片段分档，认不出归 `其他失败`）。"""
    for 已知片段 in 模型片段表:
        if 已知片段 in 判定文本:
            return 失败_模型请求失败
    for 已知片段 in 上游片段表:
        if 已知片段 in 判定文本:
            return 失败_上游中断
    return 失败_其他


def 判终态(状态: str, 输出字节) -> tuple:
    """`(终态, 读取状态)` —— 终态按 status 自算；**读取状态只按输出有无**。

    `已读` 是**读方的判定**（主策划明确审读后才置），清点**永不**自置 `已读`：
    有输出（含空文件）先记 `未读` / `空报告待核`，无输出记 `缺件待核`。
    """
    状态文本 = str(状态 or "").strip()
    if 状态文本 == "completed":
        终态 = 终态_完成
    elif 状态文本 == "failed":
        终态 = 终态_失败
    else:
        终态 = 终态_待核
    if 输出字节 is None:
        return 终态, 读取_缺件
    if 输出字节 == 0:
        return 终态, 读取_空报告
    return 终态, 读取_未读


def 读一条源(元数据件: Path) -> dict:
    """读一份代理目录 ⇒ 源条目（**只读 metadata 与 output**）；读不动 ⇒ 空表。"""
    try:
        元数据 = json.loads(元数据件.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    代理目录 = 元数据件.parent
    输出件 = 代理目录 / "output.txt"
    输出字节 = 输出件.stat().st_size if 输出件.is_file() else None
    终态, 读取状态 = 判终态(元数据.get("status"), 输出字节)
    指纹 = None
    错误类别 = None
    if 输出字节 is not None:
        报告内容 = 输出件.read_bytes()
        指纹 = hashlib.sha256(报告内容).hexdigest()
        if 终态 == 终态_失败:
            错误类别 = 失败类别(报告内容.decode("utf-8", "replace"))
    return {
        "来源标识": str(元数据.get("agentId") or 代理目录.name),
        "报告路径": str(输出件) if 输出件.is_file() else None,
        "报告指纹": 指纹,
        "读取状态": 读取状态,
        "终态": 终态,
        "错误类别": 错误类别,
        "父会话": 元数据.get("parentSessionId"),
        "代理配置": 元数据.get("profileId"),
        "工作目录": 元数据.get("cwd") or 元数据.get("workspaceRoot"),
        "工作内容": 元数据.get("description"),
        "创建时刻": 元数据.get("createdAt"),
        "更新时刻": 元数据.get("updatedAt"),
        "完成时刻": 元数据.get("completedAt"),
        "输出字节": 输出字节,
        "工具调用数": 元数据.get("totalToolUseCount"),
    }


def 扫一遍(仓根, 客户端目录=None) -> list:
    """有界扫全部 `*/agent_*/metadata.json`，按归属过滤 ⇒ 源条目表（按创建时刻排序）。"""
    基准根 = 项目根(仓根)
    工作树根基 = 工作树根(仓根)
    源根目录 = Path(客户端目录) if 客户端目录 else 客户端根()
    源条目表 = []
    for 元数据件 in sorted(源根目录.glob("*/agent_*/metadata.json")):
        源条目 = 读一条源(元数据件)
        if not 源条目:
            continue
        if not 归属本项目(源条目["工作目录"], 基准根, 工作树根基):
            continue
        源条目表.append(源条目)
    源条目表.sort(key=lambda 源条目: 源条目.get("创建时刻") or "")
    return 源条目表


def 汇总(源条目表: list) -> dict:
    """清点读数：总数 · 逐终态 · 逐读取状态 · 失败类别 · 内容重复组（保来源，明细有界）。"""
    终态计数 = {档名: 0 for 档名 in 终态档表}
    读取计数 = {档名: 0 for 档名 in 读取状态档表}
    失败计数 = {档名: 0 for 档名 in 失败类别档表}
    指纹组 = {}
    for 源条目 in 源条目表:
        终态计数[源条目["终态"]] = 终态计数.get(源条目["终态"], 0) + 1
        读取计数[源条目["读取状态"]] = 读取计数.get(源条目["读取状态"], 0) + 1
        if 源条目["错误类别"]:
            失败计数[源条目["错误类别"]] = 失败计数.get(源条目["错误类别"], 0) + 1
        if 源条目["报告指纹"]:
            指纹组.setdefault(源条目["报告指纹"], []).append(源条目["来源标识"])
    重复组 = {指纹: 来源表 for 指纹, 来源表 in 指纹组.items() if len(来源表) > 1}
    重复明细 = dict(list(重复组.items())[:重复明细上限])
    return {
        "总数": len(源条目表),
        "终态计数": 终态计数,
        "读取计数": 读取计数,
        "失败计数": 失败计数,
        "唯一内容数": len(指纹组),
        "重复组数": len(重复组),
        "重复组": 重复明细,
        "重复组截断": len(重复组) > 重复明细上限,
    }


def 分页快照(源条目表: list, 快照目录: Path, 页大小: int = 分页默认) -> dict:
    """把源条目表分页落盘（`总表.json` + `第NNNN页.json` + `汇总.json`）⇒ 快照读数。"""
    快照目录 = Path(快照目录)
    快照目录.mkdir(parents=True, exist_ok=True)
    (快照目录 / "总表.json").write_text(
        json.dumps(源条目表, ensure_ascii=False, indent=1), encoding="utf-8")
    快照页数 = 0
    for 起点 in range(0, len(源条目表), 页大小):
        快照页数 += 1
        快照页表 = 源条目表[起点:起点 + 页大小]
        (快照目录 / ("第%04d页.json" % 快照页数)).write_text(
            json.dumps(快照页表, ensure_ascii=False, indent=1), encoding="utf-8")
    读数 = 汇总(源条目表)
    (快照目录 / "汇总.json").write_text(
        json.dumps(读数, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"快照目录": str(快照目录), "页数": 快照页数, "每页": 页大小, **读数}


def 清点(仓根, 客户端目录=None, 快照根=None, 页大小: int = 分页默认) -> dict:
    """扫一遍 + 分页落快照 ⇒ 快照读数（快照根默认 `<运行数据根>/临时件`）。"""
    源条目表 = 扫一遍(仓根, 客户端目录)
    if 快照根 is None:
        快照根 = 子目录路径(解析当前环境(), "临时件")
    快照目录 = Path(快照根) / (快照前缀 + secrets.token_hex(4))
    return 分页快照(源条目表, 快照目录, 页大小)
