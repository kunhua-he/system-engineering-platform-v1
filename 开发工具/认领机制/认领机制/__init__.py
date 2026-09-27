# -*- coding: utf-8 -*-
"""认领机制包（入口：只做再导出，零实现）。

公开面（`说明.md` §二 表格）：
    账本格式与退出码 · 提交闸模式常量
    repo_root · ROOT · DEFAULT_LEDGER · ledger_path
    now_ts · fmt_ts · parse_ts · norm_paths · Ledger
    gate_mode · lease_status
    op_claim · op_release · op_reclaim · op_query
    git_toplevel · leg_from_branch · git_staged_paths · op_gate
    render_claim · render_query · render_release · render_reclaim · render_gate
    parse_args · usage · main
"""

from .常量 import (
    DEFAULT_TTL_SEC,
    EXIT_CONFLICT,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_USAGE,
    FORMAT_VERSION,
    GATE_BLOCK,
    GATE_BLOCK_ALIASES,
    GATE_WARN,
    LEDGER_BASENAME,
    LEG_CHARS,
    TIME_FMT,
)
from .仓根 import DEFAULT_LEDGER, ROOT, ledger_path, repo_root
from .时间 import fmt_ts, now_ts, parse_ts
from .路径 import norm_paths
from .账本 import Ledger
from .闸模式 import gate_mode
from .语义 import lease_status, op_claim, op_query, op_reclaim, op_release
from .提交闸 import git_staged_paths, git_toplevel, leg_from_branch, op_gate
from .渲染 import (
    render_claim,
    render_gate,
    render_query,
    render_reclaim,
    render_release,
)
from .命令行 import BOOL_FLAGS, main, parse_args, usage

__all__ = [
    "FORMAT_VERSION",
    "LEDGER_BASENAME",
    "DEFAULT_TTL_SEC",
    "TIME_FMT",
    "EXIT_OK",
    "EXIT_USAGE",
    "EXIT_CONFLICT",
    "EXIT_NOT_FOUND",
    "GATE_WARN",
    "GATE_BLOCK",
    "GATE_BLOCK_ALIASES",
    "LEG_CHARS",
    "repo_root",
    "ROOT",
    "DEFAULT_LEDGER",
    "ledger_path",
    "now_ts",
    "fmt_ts",
    "parse_ts",
    "norm_paths",
    "Ledger",
    "gate_mode",
    "lease_status",
    "op_claim",
    "op_release",
    "op_reclaim",
    "op_query",
    "git_toplevel",
    "leg_from_branch",
    "git_staged_paths",
    "op_gate",
    "render_claim",
    "render_query",
    "render_release",
    "render_reclaim",
    "render_gate",
    "BOOL_FLAGS",
    "parse_args",
    "usage",
    "main",
]
