# -*- coding: utf-8 -*-
"""合主干有界跑 —— 跑一条子进程：完整输出落有界日志件并回路径，超时回已收到的部分输出。

为什么本组件自带一份（不借 仓操作.跑命令）：仓操作.py 整件归 W1（它正在里面抽「干净环境」），
本工具（W12）与它分属两条腿 ⇒ 同函数双主会在合并期对撞。故各写各的，口径同源（与
开发工具/MCP服务/shell.py 一致）。

口径：
  · 两条线程边读边截断：每个流前 输出上限 字符留内存，超出即把完整内容（头部 + 后续）
    懒写进一个临时日志件（至多 日志上限 字符）⇒ 输出有界，完整日志在，回路径；
  · 必须读干：不读干，子进程会堵在写满的管道上（假超时）；
  · 超时 ⇒ 杀整进程组（start_new_session 开的组），退出码给 -1，回已收到的部分输出
    + 退出码 + 日志路径 —— 不再是一句「超时」；
  · 起不来给 -2；编码 utf-8 + errors=replace（坏字节不炸工具）。
"""

import os
import subprocess
import tempfile
import threading

输出上限 = 16000
日志上限 = 8 * 1024 * 1024
读块大小 = 65536
禁终端提示环境 = {"GIT_TERMINAL_PROMPT": "0"}
继承定位变量 = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
             "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX")


def 干净环境(子进程环境=None) -> dict:
    """当前环境剔除 Git 定位变量 + 禁终端提示，再并入调用方给的键（并进，不是替换）。"""
    环境表 = dict(os.environ)
    for 键名 in 继承定位变量:
        环境表.pop(键名, None)
    环境表.update(禁终端提示环境)
    if 子进程环境:
        环境表.update(子进程环境)
    return 环境表


def 建日志夹(流名: str) -> dict:
    """一个流的日志夹：懒开的完整日志件 + 多线程共用的锁。"""
    return {"流名": 流名, "路径": None, "文件": None, "锁": threading.Lock(),
            "已写": 0, "截顶": False}


def 写溢出(日志夹: dict, 溢出文本: str, 头部文本: str) -> None:
    """溢出内容落进日志件；首次调用懒开件并落下头部 ⇒ 日志件是完整输出（至多 日志上限 字符）。"""
    with 日志夹["锁"]:
        if 日志夹["路径"] is None:
            句柄, 日志夹["路径"] = tempfile.mkstemp(prefix="v1_合主干_", suffix=".log")
            日志夹["文件"] = os.fdopen(句柄, "w", encoding="utf-8", errors="replace")
            日志夹["文件"].write("=== %s ===\n%s" % (日志夹["流名"], 头部文本))
            日志夹["已写"] = len(头部文本)
        if 日志夹["已写"] >= 日志上限:
            日志夹["截顶"] = True
            return
        可写文本 = 溢出文本[:日志上限 - 日志夹["已写"]]
        日志夹["文件"].write(可写文本)
        日志夹["已写"] += len(可写文本)
        if len(可写文本) < len(溢出文本):
            日志夹["截顶"] = True


def 收流(输入流, 日志夹: dict) -> str:
    """读干一个流 ⇒ 内存留存文本（前 输出上限 字符）；超出即把完整内容落进日志夹。"""
    留存表 = []
    留存长 = 0
    while True:
        数据块 = 输入流.read(读块大小)
        if not 数据块:
            break
        if 留存长 < 输出上限:
            头部块 = 数据块[:输出上限 - 留存长]
            留存表.append(头部块)
            留存长 += len(头部块)
            数据块 = 数据块[len(头部块):]
        if 数据块:
            写溢出(日志夹, 数据块, "".join(留存表))
    return "".join(留存表)


def 杀进程组(子进程) -> None:
    """超时 ⇒ 杀整个进程组（shell 及其子进程）⇒ 不留孤儿（start_new_session 开的组）。"""
    import signal
    try:
        os.killpg(子进程.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        子进程.wait(timeout=2)
    except subprocess.TimeoutExpired:
        子进程.kill()


def 跑有界命令(命令表, 工作目录, 超时秒数=None, 输入文本=None, 子进程环境=None, 保留日志=False) -> tuple:
    """跑一条命令 ⇒ (退出码, 有界输出文本, 日志路径 或 None)。超时给 -1（不许当成通过）。

    超时秒数=None ⇒ 不设超时（环境步：合腿 · 全案例 —— 一趟就是它自身的长度）。
    保留日志 = 真 ⇒ 即使输出未超上限也把完整输出落一个日志件（回执里好给路径）。
    """
    环境表 = 干净环境(子进程环境)
    try:
        子进程 = subprocess.Popen(命令表, cwd=str(工作目录), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding="utf-8", errors="replace", env=环境表,
                             start_new_session=True)
    except OSError as 起不来:
        return -2, "起不了：%r" % (起不来,), None
    try:
        if 输入文本 is not None:
            子进程.stdin.write(输入文本)
    except (BrokenPipeError, OSError):
        pass
    try:
        子进程.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    标准输出夹 = 建日志夹("标准输出")
    标准错误夹 = 建日志夹("标准错误")
    收集表 = {}
    线程表 = [
        threading.Thread(target=lambda: 收集表.update({"out": 收流(子进程.stdout, 标准输出夹)})),
        threading.Thread(target=lambda: 收集表.update({"err": 收流(子进程.stderr, 标准错误夹)})),
    ]
    for 线程 in 线程表:
        线程.start()
    超时了 = False
    try:
        子进程.wait(timeout=超时秒数)
    except subprocess.TimeoutExpired:
        超时了 = True
        杀进程组(子进程)
    for 线程 in 线程表:
        线程.join(timeout=3)
    标准输出 = 收集表.get("out", "")
    标准错误 = 收集表.get("err", "")
    回执码 = -1 if 超时了 else 子进程.returncode
    if 保留日志 and 标准输出夹["路径"] is None and 标准错误夹["路径"] is None:
        句柄, 日志路径 = tempfile.mkstemp(prefix="v1_合主干_", suffix=".log")
        with os.fdopen(句柄, "w", encoding="utf-8", errors="replace") as 文件句柄:
            文件句柄.write(标准输出 + 标准错误)
        标准输出夹["路径"] = 日志路径
    for 日志夹 in (标准输出夹, 标准错误夹):
        if 日志夹["文件"] is not None:
            日志夹["文件"].close()
    日志件表 = [日志夹["路径"] for 日志夹 in (标准输出夹, 标准错误夹) if 日志夹["路径"]]
    合并输出 = 标准输出 + 标准错误
    if 超时了:
        合并输出 = "★ 超时（%s 秒）⇒ 已杀整进程组；下面是已收到的部分输出\n%s" % (超时秒数, 合并输出)
    if 日志件表:
        合并输出 += "\n★ 输出超 %d 字符已截断；完整日志：%s" % (输出上限, " ；".join(日志件表))
    return 回执码, 合并输出, (日志件表[0] if 日志件表 else None)
