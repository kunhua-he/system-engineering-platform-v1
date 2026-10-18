#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 开发工具 —— 自检 / 长样本入口（stdio 传输已移除，服务只走 HTTP 43140）。

用法：

    python3 开发工具/MCP服务.py --自检            # 协议三帧 + 工具表形状 + 拒绝样本 + 只读发现 + 冒烟
    python3 开发工具/MCP服务.py --长样本          # 重事务认领链 7 场景
    python3 开发工具/MCP服务.py --长样本全套      # 合主干 + 释放 + 反馈专项 全套长回归
    python3 开发工具/MCP服务.py --启动预检        # 只验 import 全图与公开面

**服务本身只走 HTTP**（`开发工具/MCP服务_http.py`，端口 43140）；本入口不再提供 stdio 协议主循环。

**无状态 HTTP 端点可被脚本直调**（债务 588）：POST 一帧 JSON-RPC（`tools/list` / `tools/call`）
到 `http://127.0.0.1:43140/` 即可 —— 服务不分配、不校验会话头 ⇒ **每请求自带全部上下文**，
批量调用 / 批量写盘不必逐个走客户端（帧形见 `MCP服务/传输_http.py`；同一份工具表与信封）。

**当前有哪些工具、每个工具有哪些操作 —— 用 `tools/list` 与「操作留空」的只读发现调用现看**；
本入口不写死清单（写死即第二事实源、必漂）。**工具名必须 ASCII**：客户端把非 ASCII 截掉
（实测只活下来一个），理由见 `MCP服务/工具.py` 顶部那段；中文显示名放协议的 `title` 字段。

`--自检` 是**工具面的身份证**，跑 `MCP服务/自检样本.py::跑自检` —— 判据 ㊽
（`构建装配/一键验证/一键验证/检查规则/执行发布/判据_MCP自检.py`）跑它：退出码非 0 ⇒ 闸 0 当场红。

依据：`项目文档/决策记录/2026-09-27_构建段归环境步.md` §六 · `2026-09-27_MCP适配层.md`。
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
from MCP服务.验证管理 import 自检样本  # noqa: E402


def 入口函数(argv=None):
    命令行参数 = list(sys.argv[1:] if argv is None else argv)
    if "--启动预检" in 命令行参数:
        # 模块级 import 全图已过；再核公开面非空（不光「import 包空壳」）⇒ 自愈预检用它。
        return 0 if 工具表 else 6
    if "--自检" in 命令行参数:
        return 自检样本.跑自检(仓根, 工具表)
    if "--长样本" in 命令行参数:
        # 已发布入口：重事务认领链 7 场景（约 3 秒，硬顶 10 秒内）。
        from MCP服务.验证样本.施工管理 import 认领样本
        return 认领样本.入口(命令行参数, 仓根, 工具表)
    if "--长样本全套" in 命令行参数:
        # 追加入口（不偷换 `--长样本` 语义）：合主干 + 释放 + 反馈专项 全套长回归（环境步，预算宽松）。
        from MCP服务.验证管理 import 长样本
        return 长样本.入口(命令行参数, 仓根, 工具表)
    # stdio 传输已移除：本入口只提供 --自检 / --长样本 / --长样本全套；服务请连 HTTP 43140。
    print("stdio 传输已移除：本入口只提供 --自检 / --长样本 / --长样本全套。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    # 壳自量自门禁（裁决 §六.1）：`--自检` / `--长样本` 也在量程内。
    from 构建装配.门禁 import 自门禁

    # ★ 解释器唯一化（入口层）：本件当脚本直跑时 sys.path[0] 是脚本目录、不是仓根，
    #   而样本夹具仓里更没有 `开发工具/MCP服务/作业.py` ⇒ **不许 import**，一行赋值即可。
    #   语义同 `作业.确保注入()`：把本进程的解释器传给全部后代，缺失即拒（不回落 PATH）。
    os.environ.setdefault("V1_PY", sys.executable)
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="本件是样本 / 自检入口；重活移出命令路或调小样本面（裁决 §三.3）"))
