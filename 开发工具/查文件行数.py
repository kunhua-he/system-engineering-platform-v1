#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查文件行数 —— `项目文档/开发规范/开发规范.md` 第六节「硬数」的机器判据。

用法：
    python3 开发工具/查文件行数.py                  # 扫全仓，报读数
    python3 开发工具/查文件行数.py --仓根 <路径>     # 换仓根（默认 = 本文件所在仓）
    python3 开发工具/查文件行数.py --自测            # 反向样本：造超限文件，断言抓得住

判据（逐条对应第六节「硬数（可机器数，不是感觉）」）：
  ① 单个源文件 ≤ 400 行（含注释与空行；Rust 与 Python 同一条）
  ② 入口文件 ≤ 120 行
  ③ 入口文件零实现：Rust `lib.rs`/`main.rs`/`mod.rs` 只许 `mod` + `pub use`；
     Python `__init__.py` 零实现；Python 入口脚本只许一个入口函数

**本工具只报读数。** 把哪一条接进 `构建装配/一键验证/一键验证.py` 是收口那一步的事。
实现全在 `查文件行数/核心.py`（入口零实现，照第六节「主文件是路由」）。
"""
import argparse
import os
import sys

from 查文件行数 import 核心


def main(argv=None):
    析 = argparse.ArgumentParser(description="开发规范.md 第六节硬数的机器判据")
    析.add_argument("--仓根", default=None, help="默认 = 本文件所在仓")
    析.add_argument("--自测", action="store_true", help="反向样本自测")
    参数 = 析.parse_args(argv)
    if 参数.自测:
        return 核心.自测()
    return 核心.跑(参数.仓根 or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


if __name__ == "__main__":
    sys.exit(main())
