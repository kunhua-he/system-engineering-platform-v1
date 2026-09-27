# -*- coding: utf-8 -*-
"""代码地图 · 建索引 —— 调 rust-analyzer 出 LSIF，落运行数据根的缓存。

**这是一次性冷构建，属环境步**（`项目文档/决策记录/2026-09-27_构建段归环境步.md` §四）：
它要加载整个 Cargo 工程，**照实报墙钟、不判顶**（实测 11.6 s）。查的时候才是判顶对象 ——
查只读文件，实测 0.4 s 级。

**环境依赖**：`rust-analyzer`（Rust 官方组件，`rustup component add rust-analyzer`）。
按 11.1「环境依赖 ≠ 底座能力」：本件是**开发工具**，底座不调它、判据面不依赖它 ⇒ 退法 =
`rustup component remove rust-analyzer` + 删缓存目录，其余一切照跑。
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 开发工具/：取 运行数据根
from 运行数据根 import 确保子目录, 解析当前  # noqa: E402

from .索引 import 索引路径, 缓存类, 缓存子目录  # noqa: E402


def 找工具() -> str:
    """rust-analyzer 在不在 PATH 上；不在 ⇒ 空串（调用方据此报结构化失败）。"""
    return shutil.which("rust-analyzer") or ""


def 建(仓根: Path, 工具: str) -> tuple:
    """跑一次全量索引 ⇒ `(退出码, 墙钟毫秒, 说明)`。索引落 `<运行数据根>/缓存/代码地图/`。"""
    出 = 确保子目录(解析当前(), 缓存类) / 缓存子目录
    出.mkdir(parents=True, exist_ok=True)
    路 = 索引路径()
    起 = time.monotonic()
    with 路.open("w", encoding="utf-8") as 文:
        码 = subprocess.call(
            [工具, "lsif", str(仓根), "--exclude-vendored-libraries"],
            stdout=文, stderr=subprocess.DEVNULL, cwd=str(仓根),
        )
    毫秒 = int((time.monotonic() - 起) * 1000)
    字节 = 路.stat().st_size if 路.is_file() else 0
    if 码 != 0:
        return 码, 毫秒, "rust-analyzer 退出码 %d ⇒ 索引不完整，已落盘 %d 字节（不当成可用）" % (码, 字节)
    return 0, 毫秒, "索引 %d 字节 ⇒ %s" % (字节, 路)


def 报缺工具() -> int:
    print("代码地图：找不到 `rust-analyzer`（环境依赖，不是底座能力）。")
    print("  装法：rustup component add rust-analyzer   （下载走 4780 代理：HTTPS_PROXY=http://127.0.0.1:4780）")
    print("  退法：rustup component remove rust-analyzer ＋ 删 <运行数据根>/缓存/代码地图/")
    print("  不装也行：本工具只服务于人读代码；底座与判据面都不依赖它。")
    return 2
