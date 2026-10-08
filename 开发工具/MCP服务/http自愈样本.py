# -*- coding: utf-8 -*-
"""长自测：临时源码副本上的真 HTTP、真 exec 与失败保旧服务。"""
import concurrent.futures
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .http传输样本 import _报文, 标准头
from .合主干有界跑 import 干净环境
from .服务常量 import 服务路径


def 发初始化(监听端口, 报文号=1):
    连接 = http.client.HTTPConnection("127.0.0.1", 监听端口, timeout=5)
    try:
        连接.request("POST", 服务路径, _报文({"jsonrpc": "2.0", "id": 报文号,
                      "method": "initialize", "params": {}}), 标准头)
        应答 = 连接.getresponse()
        return 应答.status, json.loads(应答.read())
    finally:
        连接.close()


def 等版本(监听端口, 期望版本):
    截止时刻 = time.monotonic() + 5
    while time.monotonic() < 截止时刻:
        try:
            状态码, 应答 = 发初始化(监听端口)
            if 状态码 == 200 and 应答["result"]["serverInfo"]["version"] == 期望版本:
                return True
        except (OSError, ValueError, http.client.HTTPException):
            pass
        time.sleep(0.25)
    return False


def 等拒绝(样本日志):
    截止时刻 = time.monotonic() + 5
    while time.monotonic() < 截止时刻:
        if "mcp.http.selfheal.rejected" in 样本日志.read_text():
            return True
        time.sleep(0.04)
    return False


def 启动隔离(样本仓根, 样本日志, 样本环境, 监听套接字=None):
    if 监听套接字 is None:
        监听套接字 = socket.socket()
        监听套接字.bind(("127.0.0.1", 0))
        监听套接字.listen(128)
    监听端口 = 监听套接字.getsockname()[1]
    样本环境["V1_MCP_HTTP_LISTENER"] = json.dumps({"描述符": 监听套接字.fileno(),
                                              "地址": list(监听套接字.getsockname())})
    with 样本日志.open("wb") as 日志句柄:
        子进程 = subprocess.Popen([sys.executable, "-B", "-u",
                    str(样本仓根 / "开发工具/MCP服务_http.py"), "--服务", "--端口", str(监听端口)],
                    cwd=样本仓根, env=样本环境, pass_fds=(监听套接字.fileno(),),
                    stdout=日志句柄, stderr=subprocess.STDOUT)
    监听套接字.close()
    return 子进程, 监听端口


def 清隔离(子进程):
    if 子进程.poll() is None:
        子进程.terminate()
    try:
        子进程.wait(timeout=5)
    except subprocess.TimeoutExpired:
        子进程.kill()
        子进程.wait(timeout=5)


def 重载样本(源仓根):
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="HTTP真实重载-") as 临时目录:
        样本仓根 = Path(临时目录)
        for 目录名 in ("开发工具", "构建装配", "契约声明"):
            shutil.copytree(源仓根 / 目录名, 样本仓根 / 目录名,
                            ignore=shutil.ignore_patterns("__pycache__", "*.db", "target"))
        样本环境 = 干净环境()
        协议源件 = 样本仓根 / "开发工具/MCP服务/协议.py"
        原文本 = 协议源件.read_text()
        样本日志 = 样本仓根 / "服务输出.txt"
        监听套接字 = socket.socket()
        监听套接字.bind(("127.0.0.1", 0))
        监听套接字.listen(128)
        监听端口 = 监听套接字.getsockname()[1]
        排队客户端 = http.client.HTTPConnection("127.0.0.1", 监听端口, timeout=5)
        排队客户端.request("POST", 服务路径, _报文({"jsonrpc": "2.0", "id": "启动排队",
                          "method": "initialize", "params": {}}), 标准头)
        子进程, 监听端口 = 启动隔离(样本仓根, 样本日志, 样本环境, 监听套接字)
        连接 = None
        try:
            启动回执 = 排队客户端.getresponse()
            样本表.append(("继承校验accept接到排队连接交正式处理器不丢",
                         启动回执.status == 200 and json.loads(启动回执.read())["id"] == "启动排队"))
            排队客户端.close()
            assert 等版本(监听端口, "0.4.0"), 样本日志.read_text()
            连接 = http.client.HTTPConnection("127.0.0.1", 监听端口, timeout=5)
            正文 = _报文({"jsonrpc": "2.0", "id": "在途", "method": "initialize", "params": {}})
            连接.putrequest("POST", 服务路径)
            连接.putheader("Content-Length", str(len(正文)))
            连接.endheaders()
            连接.send(正文[:5])
            time.sleep(0.15)
            协议源件.write_text(原文本.replace('服务版本 = "0.4.0"', '服务版本 = "样本新版"'))
            time.sleep(0.4)
            样本表.append(("在途半帧未排空不exec", "mcp.http.selfheal.exec" not in 样本日志.read_text()))
            连接.send(正文[5:])
            应答 = 连接.getresponse()
            读数 = json.loads(应答.read())
            样本表.append(("在途旧请求完整回应自身id和旧加载版本", 应答.status == 200
                        and 读数["id"] == "在途" and 读数["result"]["serverInfo"]["version"] == "0.4.0"))
            连接.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as 进程池:
                并发应答 = list(进程池.map(lambda 序号: 发初始化(监听端口, 序号), range(24)))
            样本表.append(("重载窗口24真请求不丢不串，允许新旧版本", all(状态码 == 200
                         and 读数["id"] == 序号 and 读数["result"]["serverInfo"]["version"]
                         in ("0.4.0", "样本新版")
                         for 序号, (状态码, 读数) in enumerate(并发应答))))
            样本表.append(("同PID同端口真exec后加载新版", 等版本(监听端口, "样本新版")
                         and 子进程.poll() is None and "mcp.http.selfheal.exec" in 样本日志.read_text()))
            协议源件.write_text(原文本 + "\n非法语法 = (\n")
            样本表.append(("真实语法预检失败保旧HTTP", 等拒绝(样本日志)
                         and 等版本(监听端口, "样本新版") and 子进程.poll() is None))
            协议源件.write_text(原文本.replace('服务版本 = "0.4.0"', '服务版本 = "修复新版"'))
            样本表.append(("坏版本修复后真exec恢复", 等版本(监听端口, "修复新版")))
            事件表 = [json.loads(源码行) for 源码行 in 样本日志.read_text().splitlines()
                      if 源码行.startswith('{"event":')]
            目标指纹表 = [明细条["指纹"] for 明细条 in 事件表
                         if 明细条["event"] == "mcp.http.selfheal.exec"]
            加载记录表 = [明细条 for 明细条 in 事件表 if 明细条["event"] == "mcp.http.loaded"]
            样本表.append(("两个exec目标指纹逐次等于真加载指纹且PID端口不变",
                         len(目标指纹表) == 2 and len(加载记录表) == 3
                         and 目标指纹表 == [明细条["指纹"] for 明细条 in 加载记录表[1:]]
                         and all(明细条["进程号"] == 子进程.pid
                                 and 明细条["地址"] == ["127.0.0.1", 监听端口]
                                 for 明细条 in 加载记录表)))
        finally:
            排队客户端.close()
            if 连接 is not None:
                连接.close()
            清隔离(子进程)
            if not all(通过 for _, 通过 in 样本表):
                print(样本日志.read_text(), flush=True)
        自愈源件 = 样本仓根 / "开发工具/MCP服务/http自愈.py"
        自愈源件.write_text(自愈源件.read_text().replace('os.execv(sys.executable,',
                            'os.execv("/不存在的HTTP解释器",'))
        协议源件.write_text(原文本)
        样本日志.write_text("")
        子进程, 监听端口 = 启动隔离(样本仓根, 样本日志, 样本环境)
        try:
            assert 等版本(监听端口, "0.4.0"), 样本日志.read_text()
            协议源件.write_text(原文本.replace('服务版本 = "0.4.0"', '服务版本 = "exec失败新版"'))
            样本表.append(("真实exec系统调用失败保旧服务", 等拒绝(样本日志)
                         and 等版本(监听端口, "0.4.0") and 子进程.poll() is None
                         and "exec 失败" in 样本日志.read_text()))
            time.sleep(0.3)
            样本表.append(("同失败版本不重试exec", 样本日志.read_text().count("mcp.http.selfheal.exec") == 1))
        finally:
            清隔离(子进程)
        样本环境["V1_MCP_HTTP_LISTENER"] = json.dumps({"描述符": -1, "地址": ["127.0.0.1", 1]})
        回执 = subprocess.run([sys.executable, "-B", str(样本仓根 / "开发工具/MCP服务_http.py"),
                            "--服务", "--端口", "1"], cwd=样本仓根, env=样本环境,
                            capture_output=True, text=True, timeout=5)
        样本表.append(("真实入口拒非法继承FD", 回执.returncode != 0 and "监听描述符非法" in 回执.stderr))
    return [(说明, 通过, "隔离真实socket/子进程") for 说明, 通过 in 样本表]
