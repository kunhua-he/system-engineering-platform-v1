#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查案例形状 —— 案例期望的**判据形状**检查器（`测试验证/案例/形状.md` §十）。

上级：`测试验证/案例/形状.md` §十（三条形状：载体 = 返回值槽 · 标准输出/退出码是旁路 ·
纯确定性必须写关键值断言）· 依据裁决 `项目文档/决策记录/2026-09-27_待裁九项按老仓设计哲学裁决.md`
裁决 8。口径与判法全写在 `形状检查/模块说明.py` 的文件头；本件是**路由**：
声明子模块 · 再导出公开面 · **零实现**（`开发规范.md` 第六节）。

怎么跑（在仓库根）：

    python3 测试验证/查案例形状.py            # 查案例根下每份 期望.json 的三条形状
    python3 测试验证/查案例形状.py --自测      # 反向样本（内存里造坏期望 ⇒ 必须报红）
    python3 测试验证/查案例形状.py --样本      # 落盘的正向 + 反向样本（真案例）
    python3 测试验证/查案例形状.py --案例根 <目录>   # 换案例根

退出码：0 = 无违反无未判（且自测/样本全过）；1 = 有违反或有未判；2 = 工具错误（案例目录坏了）。
"""

import sys
import time
from pathlib import Path

起 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 形状检查 import 案例根, 查根, 自测, 样本  # noqa: E402

__all__ = ["案例根", "查根", "自测", "样本"]


def main(参数: list) -> int:
    """命令行入口：分发到 `形状检查` 的公开面。阈值与注入只从 `构建装配/门禁/` 取。"""
    if "--自测" in 参数:
        return 自测()
    if "--样本" in 参数:
        return 样本()
    根 = 案例根
    if "--案例根" in 参数:
        序 = 参数.index("--案例根")
        if 序 + 1 < len(参数):
            根 = Path(参数[序 + 1]).resolve()
    return 查根(根)


if __name__ == "__main__":
    sys.exit(自门禁(起, main(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="本件只读案例目录里的 JSON（毫秒级）；慢了先查案例根是不是被换成大目录"))
