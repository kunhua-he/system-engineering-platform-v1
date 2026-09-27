# -*- coding: utf-8 -*-
"""仓根与账本落点 —— 向上找 `rust-toolchain.toml` 定仓根。

★ 基准锚在**拆前入口所在目录**（= 包的上一级）：`repo_root` 从那里向上找，找不到时
退回它的上一级 —— 与拆前「脚本的上两级」逐字同义，故账本默认落点不因拆件而变。
"""

import os

from .常量 import LEDGER_BASENAME

包目录 = os.path.dirname(os.path.abspath(__file__))          # …/开发工具/认领机制/认领机制
脚本目录 = os.path.dirname(包目录)                            # …/开发工具/认领机制（拆前入口所在目录）


def repo_root():
    """向上找 rust-toolchain.toml 定仓根；找不到就退回脚本的上两级。"""
    目录 = 脚本目录
    while True:
        if os.path.isfile(os.path.join(目录, "rust-toolchain.toml")):
            return 目录
        up = os.path.dirname(目录)
        if up == 目录:
            return os.path.dirname(脚本目录)
        目录 = up


ROOT = repo_root()
DEFAULT_LEDGER = os.path.join(ROOT, "开发工具", "认领机制", LEDGER_BASENAME)


def ledger_path():
    """账本落点。CLAIM_LEDGER 只给自检用（它要往临时账本里写）。"""
    return os.environ.get("CLAIM_LEDGER") or DEFAULT_LEDGER
