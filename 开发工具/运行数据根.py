#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行数据根 —— **Python 侧唯一入口**（Rust crate `运行内核/运行数据根/` 的镜像）。

用法：
    python3 开发工具/运行数据根.py                 # 一致性检查：Python 镜像 vs Rust 那份
    python3 开发工具/运行数据根.py --反向样本       # 逐项改坏副本，验证判据抓得住
    python3 开发工具/运行数据根.py --python <路径>  # 换一份被检查的 Python 源（默认 = 口径.py）

判据与口径全在 `运行数据根/` 包里（入口零实现，照开发规范.md 第六节「主文件是路由」）：
  · `运行数据根/口径.py` —— 常量与解析（覆盖变量 · 默认目录名 · 四类子目录 · 三个平台基）。
  · `运行数据根/一致性判据.py` —— 逐项比对 + 反向样本。
依据：`项目文档/决策记录/2026-09-27_运行数据根.md` §二/§三。

**五秒硬顶（壳自量自门禁）**：入口在**导入业务包之前**起表，跑完按完整壳墙钟判顶 ——
见 `构建装配/门禁/`。反向样本：`V1_CMD_SLOW_MS=5200 python3 开发工具/运行数据根.py` 必红。
"""
import sys
import tempfile
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/命令壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

from 运行数据根 import 一致性判据  # noqa: E402


def 入口函数(argv=None):
    命令行参数 = list(sys.argv[1:] if argv is None else argv)
    python路 = 一致性判据.镜像源
    if "--python" in 命令行参数:
        python路 = Path(命令行参数[命令行参数.index("--python") + 1])
    解析路 = 一致性判据.真源解析路径
    if "--rust" in 命令行参数:
        解析路 = Path(命令行参数[命令行参数.index("--rust") + 1])
    子目录路 = 一致性判据.真源子目录路径
    if "--rust子目录" in 命令行参数:
        子目录路 = Path(命令行参数[命令行参数.index("--rust子目录") + 1])
    if "--反向样本" in 命令行参数:
        with tempfile.TemporaryDirectory(prefix="运行数据根反向样本-") as 临时目录:
            return 一致性判据.跑反向样本(Path(临时目录))
    return 一致性判据.跑一遍(解析路, 子目录路, python路)


if __name__ == "__main__":
    sys.exit(
        自门禁(
            起始时刻, 入口函数(), 尾巴余量毫秒=200,
            修法="本命令比两份源文本 —— 树长大它自身会超顶。修法是只读被比的那几件"
                 "（不扫全仓），别砍判据面。",
        )
    )
