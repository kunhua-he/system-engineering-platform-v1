"""真实测试进程行为；控制标记仅供夹具使用，不是生产IPC。"""

import json
import os
import resource
import signal
import sys
import time
from pathlib import Path

from 开发工具.运行数据根 import 子目录路径, 解析当前环境

故障模式表 = (
    "正常返回", "启动失败", "夹具初始化失败", "调用崩溃", "永久阻塞",
    "持续标准输出", "持续错误输出", "持续双路输出",
)


def 写阶段标记(故障模式, 授权令牌, 阶段名称):
    标记文本 = json.dumps({"模式": 故障模式, "令牌": 授权令牌,
                         "阶段": 阶段名称, "进程号": os.getpid()}, ensure_ascii=False)
    os.write(2, (标记文本 + "\n").encode("utf-8"))


def 初始化故障状态():
    raise RuntimeError("夹具自身的初始化函数故意失败；没有装载原生库")


def 执行故障样本(故障模式, 授权令牌, 受控目录, 触发方式="手动"):
    工作目录 = Path(受控目录).resolve()
    临时根 = 子目录路径(解析当前环境(), "临时件").resolve()
    if (故障模式 not in 故障模式表 or not 工作目录.is_relative_to(临时根)
            or 触发方式 not in ("手动", "自动")):
        raise ValueError("故障模式或受控运行目录不合法")
    if Path.cwd().resolve() != 工作目录 or len(授权令牌) != 32:
        raise ValueError("样本必须在授权目录启动")
    if (工作目录 / "故障夹具授权").read_text(encoding="utf-8") != 授权令牌:
        raise ValueError("缺少本轮样本授权")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    写阶段标记(故障模式, 授权令牌, "启动")
    if 故障模式 == "启动失败":
        sys.exit(71)
    写阶段标记(故障模式, 授权令牌, "夹具初始化")
    if 故障模式 == "夹具初始化失败":
        try:
            初始化故障状态()
        except RuntimeError:
            写阶段标记(故障模式, 授权令牌, "夹具初始化失败")
            sys.exit(72)
    写阶段标记(故障模式, 授权令牌, "就绪")
    if 触发方式 == "手动" and sys.stdin.buffer.readline(34) != (授权令牌 + "\n").encode("ascii"):
        sys.exit(73)
    if 故障模式 == "永久阻塞" or 故障模式.startswith("持续"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    写阶段标记(故障模式, 授权令牌, "调用触发")
    if 故障模式 == "正常返回":
        os.write(1, ("正常返回:" + 授权令牌 + "\n").encode("utf-8"))
        return
    if 故障模式 == "调用崩溃":
        os.kill(os.getpid(), signal.SIGABRT)
    if 故障模式 == "永久阻塞":
        while True:
            time.sleep(60)
    输出字节块 = b"Z" * 4096
    while True:
        if 故障模式 in ("持续标准输出", "持续双路输出"):
            os.write(1, 输出字节块)
        if 故障模式 in ("持续错误输出", "持续双路输出"):
            os.write(2, 输出字节块)
