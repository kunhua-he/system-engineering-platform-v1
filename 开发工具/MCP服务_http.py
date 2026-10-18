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
    python3 开发工具/MCP服务_http.py --帮助               # 只打用法就退（-h / --help 同义；不绑端口）

HTTP 面用**同一份** `协议.派发` / 工具表 / 统一信封 ⇒ 写工具仍走同样的开工 /
认领 / 指纹 / 门禁，不因换传输而绕授权。前台服务永不返回（结构边界），故不带壳。

依据：`项目文档/决策记录/2026-09-27_MCP适配层.md`。
"""
import os
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根 / "开发工具"))
sys.path.insert(0, str(仓根))

from MCP服务 import 工具表
from MCP服务.服务协议 import 服务管理, 传输_http, http自愈
from MCP服务.验证样本.服务协议 import http传输样本  # noqa: E402
from MCP服务.服务协议.服务常量 import 默认监听端口  # noqa: E402

# 用法面（`--帮助` / `-h` / `--help` 只打它然后返回 0）：**先打用法、不碰端口** ——
# 新会话查用法不能把服务起了（端口已被占时会抛 OSError）。
用法文本 = """用法：MCP服务_http.py [开关] [--端口 N]

  （不带参数）        前台起 HTTP 传输（永不返回），等同 --服务
  --服务             同上（显式）
  --启动 [--端口 N]   后台启动（PID / 日志落运行数据根）
  --停止             停后台服务
  --状态             报后台服务状态
  --重启 [--端口 N]   重启后台服务
  --自检             HTTP 传输自检
  --启动预检         只做启动前置预检
  -h / --帮助 / --help  本说明（只打用法，不绑端口、不写 PID、不起停服务）

不认的参数 ⇒ 退出码 2（只打提示与用法，同样不碰服务）。"""


def 入口函数(命令行参数):
    if "--启动预检" in 命令行参数:
        return 0
    if "--自检" in 命令行参数:
        return http传输样本.跑自检(仓根, 工具表)
    # 显式解析：帮助先出、未知参数拒绝 —— **两者都不进启动分支**（旧实现里它们落 else 起传输）。
    监听端口 = 默认监听端口
    动作 = []
    未知集 = []
    序号 = 0
    while 序号 < len(命令行参数):
        参数词 = 命令行参数[序号]
        if 参数词 in ("-h", "--帮助", "--help"):
            print(用法文本)
            return 0
        elif 参数词 == "--端口":
            if 序号 + 1 >= len(命令行参数):
                print("--端口 后面要跟一个端口号", file=sys.stderr)
                print(用法文本, file=sys.stderr)
                return 2
            序号 += 1
            try:
                监听端口 = int(命令行参数[序号])
            except ValueError:
                print("--端口 只收整数：%s" % 命令行参数[序号], file=sys.stderr)
                print(用法文本, file=sys.stderr)
                return 2
        elif 参数词 in ("--服务", "--启动", "--停止", "--状态", "--重启"):
            动作.append(参数词)
        else:
            未知集.append(参数词)
        序号 += 1
    if 未知集:
        print("不认的参数：%s" % " ".join(sorted(set(未知集))), file=sys.stderr)
        print(用法文本, file=sys.stderr)
        return 2
    # 动作优先级与旧实现一致：启动 > 停止 > 状态 > 重启 > （无动作 / 仅 --服务）前台起传输。
    if "--启动" in 动作:
        退出码, 说明 = 服务管理.启动服务(仓根, 监听端口)
    elif "--停止" in 动作:
        退出码, 说明 = 服务管理.停止服务()
    elif "--状态" in 动作:
        退出码, 说明 = 服务管理.服务状态()
    elif "--重启" in 动作:
        退出码, 说明 = 服务管理.重启服务(仓根, 监听端口)
    else:
        传输_http.起传输(仓根, 工具表, 监听端口)  # 永不返回
        return 0
    print(说明)
    return 退出码


if __name__ == "__main__":
    from 构建装配.门禁 import 自门禁

    # ★ 解释器唯一化（入口层）：一行赋值即可 —— 直跑时 sys.path[0] 是脚本目录，import 仓内模块不可靠。
    os.environ.setdefault("V1_PY", sys.executable)
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="HTTP 传输是秒级；前台服务永不返回（那条不产生读数）。"))
