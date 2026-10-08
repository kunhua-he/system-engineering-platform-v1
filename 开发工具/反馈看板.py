#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反馈看板 —— 只读实时看板端口：债务按现行判词的关联目标分资料组。

用法：
    python3 开发工具/反馈看板.py [--端口 43131]   （永不返回，Ctrl-C 退）
    python3 开发工具/反馈看板.py 样本             （隔离夹具自测：增改删映射一致 / 读失败不报新鲜）

**只读**：库 `mode=ro`、一次刷新一条读事务；不写库、不建第二本账。
**唯一来源**：`<运行数据根>/数据库/开工账本.db` + `开发工具/信息核心/未完成.json`。
"""
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()
仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根))
sys.path.insert(0, str(仓根 / "开发工具"))

from 反馈看板 import 页面, 样本, 取数  # noqa: E402

用法文本 = """反馈看板 —— 只读实时看板

  python3 开发工具/反馈看板.py [--端口 N]   （永不返回，Ctrl-C 退）
  python3 开发工具/反馈看板.py 样本         （隔离夹具自测）
"""


def 入口函数(命令行参数: list) -> int:
    if 命令行参数 and 命令行参数[0] == "样本":
        return 样本.入口函数(命令行参数[1:], 仓根)
    监听端口 = 取数.默认端口
    if "--端口" in 命令行参数:
        监听端口 = int(命令行参数[命令行参数.index("--端口") + 1])
    页面.起服务(监听端口)  # 永不返回
    return 0


if __name__ == "__main__":
    from 构建装配.门禁 import 自门禁

    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="看板端口永不返回（那条不产生读数）；样本是毫秒级。"))
