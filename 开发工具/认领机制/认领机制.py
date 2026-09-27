#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认领机制 —— 路由入口（`开发规范.md` 第六节：入口 ≤120 行 · 只做三件事 · 零实现）。

    声明子模块 · 再导出公开面 · 零实现。

规格：`项目文档/设计文档/并行开发与工作区.md`「机制二：认领机制」。用法见 `--help`。
实现按关注点分在 `认领机制/` 下的子模块里，公开面由包入口再导出 ⇒ 本调用地址逐字不变。

★ 协作式：只挡得住愿意来认领的腿，挡不住什么逐条见 `说明.md`。
★ 零第三方依赖（只用标准库）。账本是 JSON 不是 sqlite：要能被 `git diff` 看出变化；
  写账走「临时文件 + os.replace」，认领走「flock 互斥 + 读改写」⇒ 原子性由内核锁保证。
★ 提交闸**默认只报不拦**：不设开关时越界也放行（退出码 0）；硬拦走 `--硬拦` 或
  `CLAIM_GATE=硬拦`（越界退 3、判不了退 2 fail-closed）。模式定义只在 `闸模式.py::gate_mode` 一处。

在仓库根执行（只用标准库）：

    python3 开发工具/认领机制/认领机制.py 认领 <腿标识> <路径> [<路径>...] [--租期秒 N]
    python3 开发工具/认领机制/认领机制.py 收工释放 <腿标识>
    python3 开发工具/认领机制/认领机制.py 查活跃 [--含过期]
    python3 开发工具/认领机制/认领机制.py 回收 (--腿 <腿标识> [--强制] | --全部过期)
    python3 开发工具/认领机制/认领机制.py 提交闸 [--腿 <腿标识>] [--硬拦]
    python3 开发工具/认领机制/认领机制.py --help

退出码：0 成功 · 2 用法/参数错 · 3 冲突或被拒 · 4 无此租约。
"""

import sys
from pathlib import Path

# 本件与同名包同目录 ⇒ 显式插一下路径：`from 认领机制 import ...` 装的是**同名包**
#（同名字文件夹优先于同名 `.py`），于是 `python 本件.py` 之外的装载方式
#（`spec_from_file_location` · `-c` 子进程）也能 import 到包。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from 认领机制 import (  # noqa: E402
    BOOL_FLAGS,
    DEFAULT_LEDGER,
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
    ROOT,
    TIME_FMT,
    Ledger,
    fmt_ts,
    gate_mode,
    git_staged_paths,
    git_toplevel,
    leg_from_branch,
    lease_status,
    ledger_path,
    main,
    norm_paths,
    now_ts,
    op_claim,
    op_gate,
    op_query,
    op_reclaim,
    op_release,
    parse_args,
    parse_ts,
    render_claim,
    render_gate,
    render_query,
    render_reclaim,
    render_release,
    repo_root,
    usage,
)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
