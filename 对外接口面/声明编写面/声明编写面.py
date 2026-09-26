#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声明编写面 —— `契约声明/` 的**唯一写入口**（`开发规范.md` A2 · `接口面形状.md` §四）。

在仓库根执行（只用 Python 标准库；请求与返回都是 JSON，形状见 `形状.md`）：

    python 对外接口面/声明编写面/声明编写面.py --请求 '{"类别":"通知号","编号":null,"正文":{…}}'
    python 对外接口面/声明编写面/声明编写面.py --请求 - < 请求.json      # `-` = 读标准输入
    python 对外接口面/声明编写面/声明编写面.py --分配 通知号             # 只算号，不落盘

校验一律**转调** `构建装配/一键验证/一键验证.py`（面里没有第二套校验）；
它跑不动时回 `成功:false` + `面故障`（「暂时转调不了 + 缺什么」）。
退出码：成功 0 · 否则 1。

本文件是**路由**：解析命令行 → 调包里的公开面 → 打印 JSON。零业务实现。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 声明编写面.编排 import 处理分配, 处理写入, 声明根默认  # noqa: E402

用法 = "python 对外接口面/声明编写面/声明编写面.py --请求 '<JSON>' | --分配 <类别>"


def 建解析器() -> argparse.ArgumentParser:
    解 = argparse.ArgumentParser(
        prog="声明编写面",
        description="声明编写面 —— 契约声明/ 的唯一写入口（校验转调 构建装配/一键验证/一键验证.py）",
        epilog=用法,
    )
    解.add_argument("--请求", metavar="JSON|-", help="写入请求体（JSON 文本；`-` = 读标准输入）")
    解.add_argument("--分配", metavar="类别", help="只算号不落盘：能力 · 类型 · 错误码 · 通知号")
    解.add_argument("--声明根", default=声明根默认, help="声明根（仓内相对路径，默认 %(default)s）")
    解.add_argument("--仓根", default=None, help="仓根（默认由本文件位置上溯三级）")
    return 解


def 读请求(文本: str):
    """→ (请求对象, 错说明)。"""
    if 文本 == "-":
        文本 = sys.stdin.read()
    try:
        请求 = json.loads(文本)
    except ValueError as 错:
        return None, "请求体不是合法 JSON：%s" % 错
    if not isinstance(请求, dict):
        return None, "请求体顶层必须是 JSON 对象（形状：{类别,编号,正文,确认}）"
    return 请求, ""


def 主(参数: list) -> int:
    解 = 建解析器()
    选项 = 解.parse_args(参数)
    if (选项.请求 is None) == (选项.分配 is None):
        print("用法：%s（--请求 与 --分配 二选一）" % 用法, file=sys.stderr)
        return 2
    仓根 = Path(选项.仓根).resolve() if 选项.仓根 else Path(__file__).resolve().parents[2]
    面根 = Path(__file__).resolve().parent

    if 选项.分配 is not None:
        响应, 码 = 处理分配(仓根, 选项.声明根, 选项.分配)
    else:
        请求, 错 = 读请求(选项.请求)
        if 错:
            响应, 码 = {"成功": False, "校验": [{"项": "请求形状", "缺什么": 错,
                                            "为什么不能自愈": "请求形状不合法（等价 HTTP 400）"}]}, 1
        else:
            响应, 码 = 处理写入(仓根, 选项.声明根, 面根, 请求)
    print(json.dumps(响应, ensure_ascii=False, indent=2))
    return 码


if __name__ == "__main__":
    sys.exit(主(sys.argv[1:]))
