#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成资源声明 —— 读 `<声明根>/资源声明/*.json`，生成 `<声明根>/src/资源声明.rs`。

    python3 构建装配/形态装配/生成资源声明.py --声明根 <目录>           # 生成并落盘
    python3 构建装配/形态装配/生成资源声明.py --声明根 <目录> --检查     # 只比对，不落盘
    python3 构建装配/形态装配/生成资源声明.py --帮助                     # 用法全文

**这是「JSON → 资源声明」那条生成链的落点**：`跨语言适配/资源网关口/` 不解析 JSON
（零第三方依赖），运行期收的是**进程内的 `资源声明`**；「读 JSON 声明文件、翻成进程内声明」
那一步归**声明侧**的生成物动作，就落在本节点（`构建装配/形态装配/` —— 「声明 → 生成物」的节点，
与 `生成声明.py` 出的 `声明数据.rs` / `接缝.rs` 并列）。为什么落这里、形状怎么定，
见 `生成声明/资源声明.py` 文件头。

三档退出码（与 `生成声明.py` 同一条口径）：**0 一致 · 1 不新鲜（只从 `--检查` 来）· 2 生成失败**
（fail-closed，产物未动）。只用 Python 标准库，确定性：源按文件名升序，产物不含时间戳 / 绝对路径。

本文件是**路由**（`开发规范.md` 第六节）：只做三件事 —— 起表 · 声明子模块 · 调包里的 `主资源声明`。
"""

import os
import sys
import time

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # 仓根
from 构建装配.门禁 import 自门禁  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from 生成声明 import 主资源声明  # noqa: E402

if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 主资源声明(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="本件只读 <根>/资源声明/*.json 再渲染；重活（源多了）就分片或缓存"))
