# -*- coding: utf-8 -*-
"""常量 —— 账本格式版本 · 退出码 · 提交闸模式 · 腿标识字符集。

★ 提交闸**模式的定义只此一处**（`闸模式.py::gate_mode` 归一）：命令行与环境变量都经过它。
"""

FORMAT_VERSION = 1
LEDGER_BASENAME = "账本.json"
DEFAULT_TTL_SEC = 1800.0          # 默认租期 30 分钟
TIME_FMT = "%Y-%m-%d %H:%M:%S%z"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_NOT_FOUND = 4

# ── 提交闸的模式 ──────────────────────────────────────────────────────────────
# ★ **默认警告**：只报不拦。理由（说明.md §六 第 2 条）：现在没人在用认领机制
#   （账本实测为空）⇒ 硬拦会挡住**所有**提交，把闸门变成「谁都不能提交」。
#   硬拦是**显式开关**：命令行 `--硬拦`，或环境变量 `CLAIM_GATE=硬拦`（别名 block/1/true）。
#   模式的定义只此一处 —— 命令行与环境变量都得经过 gate_mode() 归一。
GATE_WARN = "警告"
GATE_BLOCK = "硬拦"
GATE_BLOCK_ALIASES = ("硬拦", "block", "1", "true", "on", "yes")

LEG_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
