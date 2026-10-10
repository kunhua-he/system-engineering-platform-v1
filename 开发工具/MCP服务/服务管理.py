# -*- coding: utf-8 -*-
"""MCP HTTP 服务的具名后台管理 —— 启动 / 停止 / 状态 / 重启（真实 PID + 启动身份核验）。

状态与日志落**运行数据根**（`开发工具/运行数据根/口径.py` 解析，本件不自身拼路径）：状态件记
`{进程号, 监听端口, 绑定, 网址, 入口件, 仓根, 启动时刻}`；日志件收子进程 stdout/stderr。
**只停本服务**：停之前核 `进程号` 活着 ∧ 其命令行含本服务入口件名 ∧ 端口与本服务一致 ⇒ 才发
SIGTERM；身份对不上（端口被别的进程占了 / 进程号不是我们的）⇒ 报准确错误，**不杀陌生进程**。

依据：`项目文档/决策记录/2026-09-27_MCP适配层.md`。
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .服务常量 import 绑定地址, 服务路径, 默认监听端口

服务件名 = "MCP服务_http.py"
状态件名 = "MCP服务_http.状态.json"
日志件名 = "MCP服务_http.日志.txt"


def 状态路径():
    """状态件绝对路径（落运行数据根 `临时件`）—— 建目录后交路径。"""
    from 运行数据根.口径 import 确保子目录, 解析当前环境
    return 确保子目录(解析当前环境(), "临时件") / 状态件名


def 日志路径():
    """日志件绝对路径（落运行数据根 `日志`）—— 建目录后交路径。"""
    from 运行数据根.口径 import 确保子目录, 解析当前环境
    return 确保子目录(解析当前环境(), "日志") / 日志件名


def 入口件路径(仓根):
    """本服务入口绝对路径 —— 从**当前树**解析（不用跑着的进程路径 ⇒ 腿树删了也能从主干起）。"""
    return str(Path(仓根) / "开发工具" / 服务件名)


def 读状态():
    """读状态件 ⇒ 字段字典；不存在 / 读不动 ⇒ 空字典（不编话）。"""
    状态件 = 状态路径()
    if not 状态件.is_file():
        return {}
    try:
        return json.loads(状态件.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def 进程在跑(进程号):
    """进程号是否活着（信号 0 探测）。"""
    try:
        os.kill(进程号, 0)
    except (OSError, ValueError):
        return False
    return True


def 是本服务进程(进程号):
    """启动身份核验：该进程号命令行里含本服务入口件名 ⇒ 是本服务（否则可能是陌生进程占端口）。"""
    命令读数 = subprocess.run(["ps", "-p", str(进程号), "-o", "command="],
                          capture_output=True, text=True).stdout or ""
    return 服务件名 in 命令读数


def 端口占用(监听端口):
    """端口是否已被占用：试连一次 —— 连得上 = 有人听；拒连 = 空闲。"""
    探测套接字 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    探测套接字.settimeout(0.5)
    try:
        探测套接字.connect((绑定地址, 监听端口))
        return True
    except OSError:
        return False
    finally:
        探测套接字.close()


def 启动服务(仓根, 监听端口=默认监听端口):
    """后台启动：已在本服务 ⇒ 拒重复；端口被占 ⇒ 拒且不杀；否则拉起并等端口就绪。"""
    当前状态 = 读状态()
    进程号 = 当前状态.get("进程号")
    if 进程号 and 进程在跑(进程号) and 是本服务进程(进程号):
        return 2, "本服务已在跑：PID %d · %s" % (进程号, 当前状态.get("网址"))
    if 端口占用(监听端口):
        return 2, "端口 %d 已被占用（可能是别的进程）⇒ 拒绝启动，不杀陌生进程" % 监听端口
    入口件 = 入口件路径(仓根)
    if not Path(入口件).is_file():
        return 2, "入口件不在：%s" % 入口件
    日志件 = 日志路径()
    日志句柄 = open(日志件, "ab")
    try:
        子进程 = subprocess.Popen(
            [sys.executable, "-B", "-u", 入口件, "--服务", "--端口", str(监听端口)],
            cwd=str(仓根), stdout=日志句柄, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
            env={**os.environ, "V1_PY": sys.executable})
    finally:
        日志句柄.close()
    for 等待轮次 in range(40):
        if 子进程.poll() is not None:
            return 1, "服务进程退出（码 %s）⇒ 见日志 %s" % (子进程.returncode, 日志件)
        if 端口占用(监听端口):
            break
        time.sleep(0.1)
    else:
        return 1, "启动后端口 %d 未在 4 秒内就绪 ⇒ 见日志 %s" % (监听端口, 日志件)
    记录表 = {"进程号": 子进程.pid, "监听端口": 监听端口, "绑定": 绑定地址,
            "网址": "http://%s:%d%s" % (绑定地址, 监听端口, 服务路径),
            "入口件": 入口件, "仓根": str(仓根), "启动时刻": time.time()}
    状态路径().write_text(json.dumps(记录表, ensure_ascii=False), encoding="utf-8")
    return 0, "已启动：PID %d · %s" % (子进程.pid, 记录表["网址"])


def 停止服务():
    """只停本服务：核进程活着 ∧ 命令行含本件 ⇒ SIGTERM；身份不符 ⇒ 报错不杀。"""
    当前状态 = 读状态()
    进程号 = 当前状态.get("进程号")
    if not 进程号:
        return 0, "无状态件 / 无 PID ⇒ 本服务未在跑（无物可停）"
    if not 进程在跑(进程号):
        状态路径().unlink(missing_ok=True)
        return 0, "PID %d 已不在 ⇒ 清理状态件" % 进程号
    if not 是本服务进程(进程号):
        return 2, "PID %d 命令行不含本服务入口 ⇒ 身份不符，拒绝停止（不杀陌生进程）" % 进程号
    os.kill(进程号, signal.SIGTERM)
    for 等待轮次 in range(50):
        if not 进程在跑(进程号):
            break
        time.sleep(0.1)
    else:
        return 1, "PID %d 收到 SIGTERM 后仍存活" % 进程号
    状态路径().unlink(missing_ok=True)
    return 0, "已停止：PID %d" % 进程号


def 服务状态():
    """只读状态：PID / 网址 / 存活 / 身份核验。"""
    当前状态 = 读状态()
    进程号 = 当前状态.get("进程号")
    if not 进程号:
        return 1, "本服务未在跑（无状态件）"
    存活 = 进程在跑(进程号)
    本服务 = 存活 and 是本服务进程(进程号)
    return (0 if 本服务 else 1), "PID %s · 存活=%s · 本服务=%s · %s" % (
        进程号, 存活, 本服务, 当前状态.get("网址"))


def 重启服务(仓根, 监听端口=默认监听端口):
    """停止 + 启动（用当前树入口 ⇒ 腿树删了也能从主干重启）。"""
    停止码, 停止说明 = 停止服务()
    if 停止码 != 0:
        return 停止码, 停止说明
    启动码, 启动说明 = 启动服务(仓根, 监听端口)
    return 启动码, "重启：%s；%s" % (停止说明, 启动说明)
