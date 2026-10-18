# -*- coding: utf-8 -*-
"""日志查询 —— `v1_log` 的实现：宿主日志（`zcode-*.jsonl`，100MB+）按 event / 名称 / 时间窗有界取数。

**为什么要有它**（多路代理实测）：调研宿主行为时最费往返的一项 —— 现在只能把整份 jsonl 拉进
Bash 流式解析，动辄 100MB+。本件从**件尾**倒着读（最近的在先）、命中够 `条数` 即停，
一次调用拿到有界结果。

**落点**：宿主日志**不属于本仓运行数据根**（它是 ZCode 宿主的，不是系统工程的）⇒ 本件默认
`家目录/.zcode/cli/log`，可由环境变量 `V1_ZCODE_LOG_DIR` 覆盖。本件只读，不写任何件。

**★ 别翻错目录（两套日志并存）**：`家目录/.zcode/` 下**两套**日志同时在写 —— 本件读的是
`cli/log/zcode-*.jsonl`（宿主的**事件流**，v1 工具的调用记录都在这里）；另一套 `v2/logs/*.log`
是宿主**自身**的运行日志，**不含** v1 工具的调用记录 ⇒ 先去翻它只会白花一轮。本件只认前者；
要换根就设 `V1_ZCODE_LOG_DIR`，别在工具外自行拼路径。
"""
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # 开发工具/

from .仓状态 import 参数错, 取记录条数, 拒未知, 收尾, 建操作处理, 声明键集   # noqa: E402

上限字节 = 8 * 1024 * 1024

def 解析日志根(取值) -> Path:
    """日志根：参数 > 环境变量 `V1_ZCODE_LOG_DIR` > 家目录下 `.zcode/cli/log`。"""
    if 取值:
        return Path(str(取值))
    取值 = os.environ.get("V1_ZCODE_LOG_DIR")
    if 取值:
        return Path(取值)
    return Path.home().joinpath(".zcode", "cli", "log")

def 选日志件(日志根, 日志件) -> list:
    """选要扫的件：给了 `日志件`（日期 `2026-10-07` 或文件名）就选它；否则选 mtime 最新的那一件。"""
    if 日志件:
        名称 = 日志件 if 日志件.endswith(".jsonl") else "zcode-%s.jsonl" % 日志件
        件路径 = 日志根 / 名称
        return [件路径] if 件路径.is_file() else []
    全表 = sorted(日志根.glob("zcode-*.jsonl"), key=lambda 件路径: 件路径.stat().st_mtime)
    return 全表[-1:]

def _尾块(件路径, 上限) -> tuple:
    """取件尾至多 `上限` 字节的原文 ⇒ `(原文, 起点)`；起点 > 0 时首行可能被切掉（调用方丢弃）。"""
    文件长度 = 件路径.stat().st_size
    起点 = max(0, 文件长度 - 上限)
    句柄 = open(件路径, "rb")
    try:
        句柄.seek(起点)
        return 句柄.read(), 起点
    finally:
        句柄.close()

def _过窗(时刻, 起始时刻, 结束时刻) -> bool:
    """时刻在不在时间窗里（ISO8601 串按字典序比，够用）；窗两端留空 = 不限。"""
    if 起始时刻 and 时刻 < 起始时刻:
        return False
    if 结束时刻 and 时刻 > 结束时刻:
        return False
    return True

def 取分位(有序耗时表, 分位) -> float:
    """最近秩法：取第 ceil(分位 × n) 个（1 基，n ≥ 1）。"""
    if not 有序耗时表:
        return 0.0
    序号 = min(len(有序耗时表), max(1, int(math.ceil(len(有序耗时表) * 分位))))
    return 有序耗时表[序号 - 1]

def _收过滤(参数表) -> dict:
    """把参数表收成过滤条件（缺省 = 不过滤）。"""
    耗时下限 = 参数表.get("耗时下限毫秒")
    return {
        "事件": str(参数表.get("事件") or "").strip(),
        "模块名": str(参数表.get("模块名") or "").strip(),
        "级别": str(参数表.get("级别") or "").strip(),
        "会话": str(参数表.get("会话") or "").strip(),
        "工具名": str(参数表.get("工具名") or "").strip(),
        "耗时下限": 耗时下限 if type(耗时下限) is int else None,
        "起始": str(参数表.get("起始时刻") or "").strip(),
        "结束": str(参数表.get("结束时刻") or "").strip(),
    }

def _命中(数据行, 过滤条件) -> bool:
    上下文 = 数据行.get("context") if isinstance(数据行.get("context"), dict) else {}
    工具名 = str(上下文.get("toolName") or 上下文.get("mcpToolName") or "")
    if 过滤条件["事件"] and 过滤条件["事件"] not in str(数据行.get("event") or ""):
        return False
    if 过滤条件["模块名"] and 过滤条件["模块名"] not in str(数据行.get("module") or ""):
        return False
    if 过滤条件["级别"] and 过滤条件["级别"] != str(数据行.get("level") or ""):
        return False
    if 过滤条件["会话"] and 过滤条件["会话"] not in str(数据行.get("sessionId") or ""):
        return False
    if 过滤条件["工具名"] and 过滤条件["工具名"] not in 工具名:
        return False
    if 过滤条件["耗时下限"] is not None and (
            not isinstance(数据行.get("durationMs"), (int, float))
            or 数据行.get("durationMs") < 过滤条件["耗时下限"]):
        return False
    return _过窗(str(数据行.get("timestamp") or ""), 过滤条件["起始"], 过滤条件["结束"])

def _逐条命中(件表, 上限, 过滤条件):
    """从件尾倒着读、逐行判定 ⇒ 依次 yield 命中的数据行（最近在先）。"""
    for 件路径 in 件表:
        原文, 起点 = _尾块(件路径, 上限)
        段表 = 原文.decode("utf-8", errors="replace").split("\n")
        if 起点 > 0 and 段表:
            段表 = 段表[1:]
        for 源码行 in reversed(段表):
            if not 源码行.strip():
                continue
            try:
                数据行 = json.loads(源码行)
            except ValueError:
                continue
            if _命中(数据行, 过滤条件):
                yield 数据行

def _取日志面(参数表) -> tuple:
    """公共前置：校验 `上限字节`、定位日志根与件表 ⇒ (错误行, 日志根, 件表, 上限, 过滤条件)。"""
    过滤条件 = _收过滤(参数表)
    上限 = 参数表.get("上限字节", 上限字节)
    if type(上限) is not int or not 1024 <= 上限 <= 64 * 1024 * 1024:
        raise 参数错("`上限字节` 要是 1024..67108864 的整数（收到 %r）" % (上限,))
    日志根 = 解析日志根("")
    if not 日志根.is_dir():
        return "日志根不在：%s（可用环境变量 V1_ZCODE_LOG_DIR 指过去）" % 日志根, None, None, 上限, 过滤条件
    件表 = 选日志件(日志根, str(参数表.get("日志件") or "").strip())
    if not 件表:
        return "日志根下没有这个件（也没有 zcode-*.jsonl）：%s" % 日志根, None, None, 上限, 过滤条件
    return None, 日志根, 件表, 上限, 过滤条件

def 查日志(仓根, 参数表) -> tuple:
    """有界取数：按 `事件` / `模块名` / `级别` / `会话` / `起始时刻` / `结束时刻` 过滤，最多 `条数` 条。"""
    拒未知(参数表, 声明键集(操作表, "查日志"))
    记录条数 = 取记录条数(参数表)
    错误行, 日志根, 件表, 上限, 过滤条件 = _取日志面(参数表)
    if 错误行:
        return 1, 错误行
    命中表 = []
    for 数据行 in _逐条命中(件表, 上限, 过滤条件):
        上下文 = 数据行.get("context") if isinstance(数据行.get("context"), dict) else {}
        消息 = str(数据行.get("message") or "").replace("\n", " ")[:160]
        耗段 = "" if 数据行.get("durationMs") is None else " · 耗时 %sms" % 数据行.get("durationMs")
        错段 = " · ✗ 工具报错" if 上下文.get("isError") else ""
        命中表.append("%s [%s] %s · %s · 工具 %s%s%s | 会话 %s"
                 % (str(数据行.get("timestamp") or ""), 数据行.get("level") or "—",
                    数据行.get("event") or "—", 消息,
                    上下文.get("toolName") or 上下文.get("mcpToolName") or "—", 耗段, 错段,
                    str(数据行.get("sessionId") or "—")[:24]))
        if len(命中表) >= 记录条数:
            break
    行表 = ["日志根 %s · 扫 %d 件（各取尾部 ≤%d 字节）· 命中 %d 条%s"
           % (日志根, len(件表), 上限, len(命中表),
              "（已到条数上限 ⇒ 可能还有更早的）" if len(命中表) >= 记录条数 else "")]
    行表 += 命中表
    return 0, 收尾(行表)

def 工具聚合(仓根, 参数表) -> tuple:
    """按工具聚合读数：每工具 次数 / 中位 / 95分位 / 最大（毫秒）。

    ★ 口径：单次工具调用 wall（`durationMs`，毫秒）≠ 代理总耗时（只有 agent 类工具含整个代理）；
    客户端往返 / 服务处理 / 等待三截不许靠两个 wall 相减假精确。本读数按 `context.toolName` /
    `context.mcpToolName` 归属工具；样本 cold/warm 未分档，要分档请用 `起始时刻`/`结束时刻` 收窗。
    """
    拒未知(参数表, 声明键集(操作表, "工具聚合"))
    记录条数 = 取记录条数(参数表)
    错误行, 日志根, 件表, 上限, 过滤条件 = _取日志面(参数表)
    if 错误行:
        return 1, 错误行
    耗时表 = {}
    无耗时数 = 0
    for 数据行 in _逐条命中(件表, 上限, 过滤条件):
        上下文 = 数据行.get("context") if isinstance(数据行.get("context"), dict) else {}
        工具键 = str(上下文.get("toolName") or 上下文.get("mcpToolName") or "（未标工具）")
        耗时 = 数据行.get("durationMs")
        if isinstance(耗时, (int, float)):
            耗时表.setdefault(工具键, []).append(float(耗时))
        else:
            无耗时数 += 1
    工具排行 = sorted(耗时表.items(), key=lambda 聚合条目: (-len(聚合条目[1]), 聚合条目[0]))
    行表 = ["工具聚合 · 日志根 %s · 扫 %d 件（各取尾部 ≤%d 字节）· 窗口 %s ~ %s"
           % (日志根, len(件表), 上限, 过滤条件["起始"] or "不限", 过滤条件["结束"] or "不限"),
           "口径：单次工具调用 wall（durationMs，毫秒）≠ 代理总耗时（只有 agent 类工具含整个代理）；"
           "cold/warm 未分档，要分档请用 `起始时刻`/`结束时刻` 收窗。"]
    for 工具键, 耗时序列 in 工具排行[:记录条数]:
        有序耗时表 = sorted(耗时序列)
        行表.append("  %s | 次数 %d | 中位 %.0f | 95分位 %.0f | 最大 %.0f ms"
                 % (工具键, len(有序耗时表), 取分位(有序耗时表, 0.5),
                    取分位(有序耗时表, 0.95), 有序耗时表[-1]))
    if len(工具排行) > 记录条数:
        行表.append("  …共 %d 个工具（已到条数上限）" % len(工具排行))
    if 无耗时数:
        行表.append("  （另有 %d 条命中无 durationMs，未计入分位）" % 无耗时数)
    return 0, 收尾(行表)

工具名 = "v1_log"
工具说明 = ("宿主日志查询：`~/.zcode/cli/log/zcode-*.jsonl`（100MB+）从件尾倒着读，按 "
        "`事件`/`模块名`/`级别`/`会话`/`工具名`/`耗时下限毫秒`/`起始时刻`/`结束时刻` 过滤，"
        "最多 `条数` 条；`日志件` 指定某天（默认最新一件），`上限字节` 限扫描量。"
        "`查日志` 每条命中**带工具名与耗时**（`context.toolName` / `context.mcpToolName` 与 `durationMs`）"
        "—— 答得出「哪个工具在何时动了哪个件」；`工具聚合` 按工具回**次数 / 中位 / 95分位 / 最大**"
        "（毫秒）—— 答得出「哪个工具最费时间」。只读零写、有界。")
操作表 = {
    '查日志': {"说明": '查日志' , "需开工ID": False, "必需": [],
        "可选": ['事件', '模块名', '级别', '会话', '工具名', '耗时下限毫秒', '起始时刻', '结束时刻', '日志件', '条数', '上限字节'], "最短例": {'操作': '查日志', '参数': {'条数': 5}},
        "处理": 建操作处理(查日志, 并入开工=False)},
    '工具聚合': {"说明": '按工具聚合：每工具 次数 / 中位 / 95分位 / 最大（毫秒）', "需开工ID": False, "必需": [],
        "可选": ['事件', '模块名', '级别', '会话', '工具名', '耗时下限毫秒', '起始时刻', '结束时刻', '日志件', '条数', '上限字节'], "最短例": {'操作': '工具聚合', '参数': {'条数': 10}},
        "处理": 建操作处理(工具聚合, 并入开工=False)},
}
