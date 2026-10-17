# -*- coding: utf-8 -*-
"""自愈预检 —— 自愈重启前的**有界可启动校验**：新服务入口真起得来才 `execv`，否则留着旧码。

**为什么要有它**（实测 2026-10-07）：服务原先的 `os.execv` **不做任何校验**。
盘上代码一旦带语法错 / 冲突标记（实测 `开发工具/MCP服务/工具.py::工具表` 处残留 `<<<<<<< HEAD`），exec 出的新进程在
import 阶段就 `SyntaxError` 退出 ⇒ 整个服务断开、客户端重连失败后不再连接、四个工具从
模型侧全部消失（日志 `mcp.server.connection_lost` · pid 4487 · exit 1）。**自愈反而成了自杀。**

**怎么做**：exec 之前先**有界跑一次入口的 `--启动预检`**（同一解释器 / 同一工作目录 / 真入口），
它只走模块级 import 全图就退 0；起不来（非 0 / 超时 / OSError）⇒ **不 exec**，继续用旧码，并把该
指纹记成「坏版本」——**同一坏指纹只预检一次**（不每帧重复跑子进程），指纹一变（改好或再改）才重判。
失败走**结构化 stderr**，不静默、不写假绿。

**旧码能安全续跑的范围**：进程内已 import 的模块与已建的工具表照旧服务；**新版本才有的操作 /
新工具调不到**；每次回执头带一行「新版预检不通过」的提示。

**覆盖边界**：预检跑真入口，故覆盖**启动 import 全图**（语法错 / 冲突标记 / 顶层 import 失败）；
**不覆盖** import 之后的运行期错误（如某工具第一次被调时才炸）。

依据：华哥 2026-10-07「坏代码不 exec · 旧内存服务安全续跑 · 坏版本重试要省」。
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from .服务指纹 import 仓根 as 服务仓根, 入口件 as 服务入口件

预检超时秒 = 5.0

_已拒指纹 = None
_拒因 = ""
_拒时刻 = 0.0


def 预检入口(入口路径: Path, 工作目录: Path, 超时秒: float = 预检超时秒) -> tuple:
    """有界跑 `入口路径 --启动预检` ⇒ `(可启动, 说明)`（同一解释器 / 工作目录 / 真入口）。"""
    try:
        子进程 = subprocess.run(
            [sys.executable, "-B", str(入口路径), "--启动预检"],
            cwd=str(工作目录), capture_output=True, text=True, timeout=超时秒)
    except subprocess.TimeoutExpired:
        return False, "预检超时（%s 秒）" % 超时秒
    except OSError as 起不来:
        return False, "预检起不来：%s" % (起不来,)
    if 子进程.returncode == 0:
        return True, ""
    末段文本 = ((子进程.stderr or "") + (子进程.stdout or "")).strip()[-600:]
    return False, "退出码 %d：%s" % (子进程.returncode, 末段文本)


def 判定重启(当前指纹: str, 预检替身=None) -> tuple:
    """自愈决策 ⇒ `(放行重启, 拒绝原因, 首记坏版)`。同一坏指纹只预检一次（省掉每帧昂贵重试）。"""
    global _已拒指纹, _拒因, _拒时刻
    if 当前指纹 == _已拒指纹:
        return False, _拒因, False
    预检替身 = 预检替身 or _默认预检
    通过, 说明 = 预检替身()
    if 通过:
        _已拒指纹, _拒因, _拒时刻 = None, "", 0.0
        return True, "", False
    _已拒指纹, _拒因, _拒时刻 = 当前指纹, 说明, time.time()
    return False, 说明, True


def _默认预检() -> tuple:
    """真服务默认预检：跑真入口的 `--启动预检`。"""
    return 预检入口(服务入口件, 服务仓根)


def 拒绝提示行() -> str:
    """派发时拼给模型的提示行（无拒绝 ⇒ 空串）—— 结构化说明，不静默。"""
    if _已拒指纹 is None:
        return ""
    return ("★ 服务代码已过期且**新版预检不通过** ⇒ 继续用旧码（原因：%s）；"
            "修好 `MCP服务/**` 后下一帧自动切换" % _拒因)


def 拒绝记录(说明: str) -> str:
    """结构化拒绝记录（一行 JSON）⇒ 服务写 stderr，供客户端日志抓取。"""
    return json.dumps({"event": "mcp.selfheal.rejected", "原因": 说明,
                       "指纹": _已拒指纹, "时刻": _拒时刻}, ensure_ascii=False)
