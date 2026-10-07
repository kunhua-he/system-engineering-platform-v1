# -*- coding: utf-8 -*-
"""日志查询 —— `v1_log` 的实现：宿主日志（`zcode-*.jsonl`，100MB+）按 event / 名称 / 时间窗有界取数。

**为什么要有它**（多路代理实测）：调研宿主行为时最费往返的一项 —— 现在只能把整份 jsonl 拉进
Bash 流式解析，动辄 100MB+。本件从**件尾**倒着读（最近的在先）、命中够 `条数` 即停，
一次调用拿到有界结果。

**落点**：宿主日志**不属于本仓运行数据根**（它是 ZCode 宿主的，不是系统工程的）⇒ 本件默认
`家目录/.zcode/cli/log`，可由环境变量 `V1_ZCODE_LOG_DIR` 覆盖。本件只读，不写任何件。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/

from .仓状态 import 参数错, 取记录条数, 拒未知, 收尾, 骨架            # noqa: E402

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
    长度 = 件路径.stat().st_size
    起点 = max(0, 长度 - 上限)
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

def 查日志(仓根, 参数表) -> tuple:
    """有界取数：按 `事件` / `模块名` / `级别` / `会话` / `起始时刻` / `结束时刻` 过滤，最多 `条数` 条。"""
    拒未知(参数表, ("事件", "模块名", "级别", "会话", "起始时刻", "结束时刻", "日志件", "条数", "上限字节"))
    记录条数 = 取记录条数(参数表)
    事件 = str(参数表.get("事件") or "").strip()
    模块名 = str(参数表.get("模块名") or "").strip()
    级别 = str(参数表.get("级别") or "").strip()
    会话 = str(参数表.get("会话") or "").strip()
    起始时刻 = str(参数表.get("起始时刻") or "").strip()
    结束时刻 = str(参数表.get("结束时刻") or "").strip()
    日志件 = str(参数表.get("日志件") or "").strip()
    上限 = 参数表.get("上限字节", 上限字节)
    if type(上限) is not int or not 1024 <= 上限 <= 64 * 1024 * 1024:
        raise 参数错("`上限字节` 要是 1024..67108864 的整数（收到 %r）" % (上限,))
    日志根 = 解析日志根("")
    if not 日志根.is_dir():
        return 1, "日志根不在：%s（可用环境变量 V1_ZCODE_LOG_DIR 指过去）" % 日志根
    件表 = 选日志件(日志根, 日志件)
    if not 件表:
        return 1, "日志根下没有这个件（也没有 zcode-*.jsonl）：%s" % 日志根
    命中表 = []
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
            if 事件 and 事件 not in str(数据行.get("event") or ""):
                continue
            if 模块名 and 模块名 not in str(数据行.get("module") or ""):
                continue
            if 级别 and 级别 != str(数据行.get("level") or ""):
                continue
            if 会话 and 会话 not in str(数据行.get("sessionId") or ""):
                continue
            时刻 = str(数据行.get("timestamp") or "")
            if not _过窗(时刻, 起始时刻, 结束时刻):
                continue
            消息 = str(数据行.get("message") or "").replace("\n", " ")[:160]
            命中表.append("%s [%s] %s · %s | 会话 %s"
                     % (时刻, 数据行.get("level") or "—", 数据行.get("event") or "—", 消息,
                        str(数据行.get("sessionId") or "—")[:24]))
            if len(命中表) >= 记录条数:
                break
        if len(命中表) >= 记录条数:
            break
    行表 = ["日志根 %s · 扫 %d 件（各取尾部 ≤%d 字节）· 命中 %d 条%s"
           % (日志根, len(件表), 上限, len(命中表),
              "（已到条数上限 ⇒ 可能还有更早的）" if len(命中表) >= 记录条数 else "")]
    行表 += 命中表
    return 0, 收尾(行表)

工具名 = "v1_log"
工具说明 = ("宿主日志查询：`~/.zcode/cli/log/zcode-*.jsonl`（100MB+）从件尾倒着读，按 "
        "`事件`/`模块名`/`级别`/`会话`/`起始时刻`/`结束时刻` 过滤，最多 `条数` 条；`日志件` 指定某天"
        "（默认最新一件），`上限字节` 限扫描量。只读零写、有界。")
操作表 = {
    "查日志": ((), ("事件", "模块名", "级别", "会话", "起始时刻", "结束时刻", "日志件", "条数", "上限字节"),
             '{"操作":"查日志","事件":"model.request.completed","条数":5}'),
}
分发表 = {"查日志": 查日志}
模式 = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "开工ID": {"type": "string", "description": "本工具不按树取；留空即可（三字段同形）"},
        "操作": {"type": "string", "description": "要跑哪个只读操作；留空 = 只读发现调用，返回操作目录"},
        "参数": {"type": "object", "description": "该操作自有的参数（见 操作目录 里各操作的 必需/可选）"},
    },
}

def 派发(参数表, 仓根) -> tuple:
    return 骨架(工具名, 工具说明, 操作表, 分发表, 参数表, 仓根)
