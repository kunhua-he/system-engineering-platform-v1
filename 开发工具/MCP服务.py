#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 服务 —— 本仓的开发工具按 MCP 协议暴露（stdio）。

一般由 ZCode 插件按 `.mcp.json` 拉起，不手跑。手动用法：

    python3 开发工具/MCP服务.py            # 走协议（stdio JSON-RPC，永不返回）
    python3 开发工具/MCP服务.py --自检      # 不走协议：协议三帧 + 工具表形状 + 拒绝样本 + 只读发现 + 冒烟

**当前有哪些工具、每个工具有哪些操作 —— 用 `tools/list` 与「操作留空」的只读发现调用现看**；
本入口不写死清单（写死即第二事实源、必漂）。**工具名必须 ASCII**：客户端把非 ASCII 截掉
（实测只活下来一个），理由见 `MCP服务/工具.py` 顶部那段；中文显示名放协议的 `title` 字段。

`--自检` 是**工具面的身份证**，跑 `MCP服务/自检样本.py::跑自检` —— 判据 ㊽
（`构建装配/一键验证/一键验证/判据_MCP自检.py`）跑它：退出码非 0 ⇒ 闸 0 当场红。

**本入口永不返回**（协议主循环），属「结构边界：永不返回」⇒ 不带壳，登记在
`构建装配/一键验证/入口白名单.json`（判据 ㉔）。依据：
`项目文档/决策记录/2026-09-27_构建段归环境步.md` §六 · `2026-09-27_MCP适配层.md`。
"""
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根 / "开发工具"))
sys.path.insert(0, str(仓根))

from MCP服务 import 工具表, 跑主循环, 自检样本  # noqa: E402


def 入口函数(argv=None):
    命令行参数 = list(sys.argv[1:] if argv is None else argv)
    if "--自检" in 命令行参数:
        return 自检样本.跑自检(仓根, 工具表)
    return 跑主循环(仓根, 工具表)


if __name__ == "__main__":
    sys.exit(入口函数())
