#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 服务 —— 本仓的开发工具按 MCP 协议暴露（stdio）。

一般由 ZCode 插件按 `.mcp.json` 拉起，不手跑。手动用法：

    python3 开发工具/MCP服务.py            # 走协议（stdio JSON-RPC，永不返回）
    python3 开发工具/MCP服务.py --自检      # 不走协议：自造三帧验协议层与工具表

三个工具（详见 `开发工具/MCP服务/工具.py`）：`v1_门禁`（一键门禁）· `v1_符号`（代码地图
预建索引）· `v1_替换`（**符号级**批量替换，默认 dry-run，写盘过认领机制的所有权闸）。

**本入口永不返回**（协议主循环），属「结构边界：永不返回」⇒ 不带壳，登记在
`构建装配/一键验证/入口白名单.json`（判据 ㉔）。依据：
`项目文档/决策记录/2026-09-27_构建段归环境步.md` §六 · `2026-09-27_MCP适配层.md`。
"""
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根 / "开发工具"))

from MCP服务 import 工具表, 派, 服务  # noqa: E402


def main(argv=None):
    参 = list(sys.argv[1:] if argv is None else argv)
    if "--自检" in 参:
        # 协议层的身份证：自造三帧（initialize / tools/list / 一个不存在的方法），
        # 断言响应形状与工具表 —— 协议层坏了要当场看得出来，不许「连上了但什么也不回」。
        for 方法, 参数 in (("initialize", {"protocolVersion": "试"}),
                          ("tools/list", {}), ("没有这个方法", {})):
            结果, 错 = 派(方法, 参数, 仓根, 工具表)
            if 错:
                print("%s ⇒ 错误码 %d（%s）" % (方法, 错["code"], 错["message"]))
            else:
                print("%s ⇒ 键 %s" % (方法, sorted(结果)))
        名表 = sorted(工具表)
        期望 = sorted(["v1_门禁", "v1_符号", "v1_替换"])
        print("工具表：%s" % 名表)
        return 0 if 名表 == 期望 else 1
    return 服务(仓根, 工具表)


if __name__ == "__main__":
    sys.exit(main())
