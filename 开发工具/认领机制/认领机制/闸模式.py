# -*- coding: utf-8 -*-
"""闸模式 —— 提交闸「警告 / 硬拦」的**唯一**归一入口。"""

import os

from .常量 import GATE_BLOCK, GATE_BLOCK_ALIASES, GATE_WARN


def gate_mode(raw=None, forced=False):
    """→ (模式, 读到的原值, 认不认得)。认不得的值**退回警告**并回报「不认得」——
    拼错一个环境变量就静默变成硬拦，比不拦更坏。"""
    if forced:
        return GATE_BLOCK, "命令行 --硬拦", True
    raw = os.environ.get("CLAIM_GATE", "") if raw is None else raw
    if not raw.strip():
        return GATE_WARN, "（没设）", True
    取定值 = raw.strip()
    if 取定值 in GATE_BLOCK_ALIASES:
        return GATE_BLOCK, 取定值, True
    if 取定值 in (GATE_WARN, "warn", "警告"):
        return GATE_WARN, 取定值, True
    return GATE_WARN, 取定值, False
