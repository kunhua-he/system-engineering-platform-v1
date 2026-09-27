# -*- coding: utf-8 -*-
"""命令行面 —— 参数解析与请求体读取（`声明编写面.py` 只做路由，这两件事搬到这里）。"""
from __future__ import annotations

import argparse
import json
import sys

from .编排 import 声明根默认

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
