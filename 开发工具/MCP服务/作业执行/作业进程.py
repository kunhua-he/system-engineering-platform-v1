# -*- coding: utf-8 -*-
"""作业进程 —— 后台作业的**进程组所有权**与**运行预算**（后台作业执行器的环境面）。

**进程组所有权**：工作进程 `start_new_session=True` ⇒ 自成会话 / 组长，组号 = 工作进程号；
命令再由工作进程 `start_new_session=True` 另起一组 ⇒ 组号 = 命令进程号。超时 / 取消一律
`killpg` **这两组之一**，绝不向本进程所在组发信号。PID 会被复用 ⇒ 动手前核**代次**
（`ps -o lstart=` 的启动时刻串）；代次不符 = 号被别的进程占了 ⇒ **不杀**。

**预算不靠改单位名藏**：作业运行时上限**从规则库读**（`信息核心.db` 的 `规则` 表，类
`安全边界`）—— 判据 ㊲ 只扫源码字面量，读 DB 是**非字面量**。两条规则：
`后台作业最长运行秒数`（预算）与 `后台作业预算硬顶秒数`（硬顶）。**fail-closed**：规则缺失 /
非整数 / 非正数 ⇒ 拒启动（不回落成无限或默认巨值）；预算 > 硬顶 ⇒ 压回硬顶并如实报 ⇒
**没有「无限运行」这条路径**。`超时秒` 入参只用于**启动握手**（≤5 秒），不是作业预算。

**有界采集口径与 shell 同源**：日志夹预开本作业的件，交给 `shell._收流` / `shell._写溢出`
（每流内存留 16000 字符、磁盘 8 MiB 上限）。
"""

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # 开发工具/
from .命令执行 import 输出上限  # noqa: E402
from ..作业账本 import 终态集, 读行  # noqa: E402

收尾秒 = 2                  # 杀组后等组消失的上限；TERM 一次 + KILL 一次 ⇒ 最坏 4 秒 < 5 秒
等组号秒 = 1                # 取消「启动中」作业时，短等命令组号出现
轮询间隔秒 = 0.05
预算规则类 = "安全边界"
预算规则名 = "后台作业最长运行秒数"
预算硬顶名 = "后台作业预算硬顶秒数"


def 进程读数(进程号) -> tuple:
    """`(状态值字符, 启动时刻串)`；进程不在 ⇒ `("", "")`。代次 = 启动时刻串（PID 复用的判据）。"""
    try:
        回执 = subprocess.run(["ps", "-o", "stat=,lstart=", "-p", str(进程号)],
                          capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return ("", "")
    if 回执.returncode != 0:
        return ("", "")
    段表 = 回执.stdout.strip().split(None, 1)
    if not 段表:
        return ("", "")
    return 段表[0], (段表[1].strip() if len(段表) > 1 else "")


def 组在吗(进程号, 期望代次=None) -> bool:
    """组（组长 = 进程号）还在吗。**僵尸不算在**（`Z` 已死、只是没被收尸）；
    给了 `期望代次` 时**必须对上**（号被复用 ⇒ 不是同一个组 ⇒ 不算在）。"""
    if not 进程号:
        return False
    状态值字符, 代次 = 进程读数(进程号)
    if not 状态值字符 or 状态值字符.startswith("Z"):
        return False
    return not (期望代次 and 代次 != 期望代次)


def 杀组(进程号) -> None:
    """整组 `TERM` → 等 → `KILL`。**只对调用方给的组**（本作业的组），不碰别的组。"""
    for 信号值 in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(进程号, 信号值)
        except (ProcessLookupError, PermissionError):
            return
        截止时刻 = time.monotonic() + 收尾秒
        while time.monotonic() < 截止时刻:
            if not 组在吗(进程号):
                return
            time.sleep(轮询间隔秒)


def 等命令组(任务ID: str) -> tuple:
    """启动中作业：短等「命令组号」出现（工作进程 spawn 命令后立刻落）⇒ `(组号, 代次)`。"""
    截止时刻 = time.monotonic() + 等组号秒
    while time.monotonic() < 截止时刻:
        作业行 = 读行(任务ID)
        if 作业行 and 作业行["命令组号"]:
            return 作业行["命令组号"], 作业行["命令代次"]
        if 作业行 and 作业行["状态"] in 终态集:
            return None, None
        time.sleep(轮询间隔秒)
    return None, None


def 取规则整数(仓根, 规则名):
    """从规则库 `规则` 表取一条**正整数**规则 ⇒ 整数；缺失 / 非整数 / 非正 ⇒ `None`（fail-closed）。"""
    try:
        from 开发工具.信息核心.表定义 import 连规则库
        连接 = 连规则库(仓根)
    except Exception:
        return None
    try:
        规则行 = 连接.execute("select 内容 from 规则 where 类=? and 名=?",
                         (预算规则类, 规则名)).fetchone()
    except Exception:
        return None
    finally:
        连接.close()
    if not 规则行 or 规则行[0] is None:
        return None
    文本值 = str(规则行[0]).strip()
    if not re.fullmatch(r"[0-9]+", 文本值):
        return None
    整数值 = int(文本值)
    return 整数值 if 整数值 > 0 else None


def 读后台预算(仓根):
    """⇒ `(有效预算, 硬顶, 是否压回)` 或 `None`。**没有「无限运行」路径**：
    预算 > 硬顶 ⇒ 压回硬顶（`是否压回` = 真，调用方如实报）；任一条读不到 / 非法 ⇒ `None`。"""
    预算值 = 取规则整数(仓根, 预算规则名)
    硬顶值 = 取规则整数(仓根, 预算硬顶名)
    if 预算值 is None or 硬顶值 is None:
        return None
    if 预算值 > 硬顶值:
        return 硬顶值, 硬顶值, True
    return 预算值, 硬顶值, False


def _开日志夹(路径: Path, 流名称: str) -> dict:
    """预开**本作业的**日志件 ⇒ 交给 shell 的 `_收流` / `_写溢出` 用同一份有界采集口径。
    shell 的 `_写溢出` 只在「路径为空」时懒建临时件；这里路径已给、文件已开 ⇒ 溢出直接进本件。"""
    return {"流名称": 流名称, "路径": str(路径),
            "文件": open(路径, "w", encoding="utf-8", errors="replace"),
            "锁": threading.Lock(), "已写": 0, "截顶": False}


def _补齐小输出(日志夹: dict, 留存文本: str) -> None:
    """输出没到 `输出上限` ⇒ `_写溢出` 一次没调过、日志件还是空的 ⇒ 把内存留存补写进去。"""
    if 日志夹["已写"] or not 留存文本:
        return
    with 日志夹["锁"]:
        if not 日志夹["已写"]:
            日志夹["文件"].write(留存文本)
            日志夹["已写"] = len(留存文本)
