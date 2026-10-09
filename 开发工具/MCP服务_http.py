#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP HTTP 服务入口 —— 具名后台管理（启动 / 停止 / 状态 / 重启）+ 前台 Streamable HTTP 服务。

用法：
    python3 开发工具/MCP服务_http.py                    # 前台起 HTTP 传输（永不返回）
    python3 开发工具/MCP服务_http.py --服务 [--端口 N]    # 同上（显式）
    python3 开发工具/MCP服务_http.py --启动 [--端口 N]    # 后台启动（PID/日志落运行数据根）
    python3 开发工具/MCP服务_http.py --停止
    python3 开发工具/MCP服务_http.py --状态
    python3 开发工具/MCP服务_http.py --重启 [--端口 N]
    python3 开发工具/MCP服务_http.py --自检               # HTTP 传输自检（判据 ㊽ 调用）

HTTP 面用**同一份** `协议.派发` / 工具表 / 统一信封 ⇒ 写工具仍走同样的开工 /
认领 / 指纹 / 门禁，不因换传输而绕授权。前台服务永不返回（结构边界），故不带壳。

依据：`项目文档/决策记录/2026-09-27_MCP适配层.md`。
"""
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根 / "开发工具"))
sys.path.insert(0, str(仓根))

from MCP服务 import 工具表, 服务管理, 传输_http, http传输样本, http自愈  # noqa: E402
from MCP服务.服务常量 import 默认监听端口  # noqa: E402


def 入口函数(命令行参数):
    if "--启动预检" in 命令行参数:
        return 0
    if "--自检" in 命令行参数:
        return http传输样本.跑自检(仓根, 工具表)
    监听端口 = 默认监听端口
    if "--端口" in 命令行参数:
        监听端口 = int(命令行参数[命令行参数.index("--端口") + 1])
    if "--启动" in 命令行参数:
        退出码, 说明 = 服务管理.启动服务(仓根, 监听端口)
    elif "--停止" in 命令行参数:
        退出码, 说明 = 服务管理.停止服务()
    elif "--状态" in 命令行参数:
        退出码, 说明 = 服务管理.服务状态()
    elif "--重启" in 命令行参数:
        退出码, 说明 = 服务管理.重启服务(仓根, 监听端口)
    else:
        传输_http.起传输(仓根, 工具表, 监听端口)  # 永不返回
        return 0
    print(说明)
    return 退出码


if __name__ == "__main__":
    from 构建装配.门禁 import 自门禁

    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="HTTP 传输是秒级；前台服务永不返回（那条不产生读数）。"))
