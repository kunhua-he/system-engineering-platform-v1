#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声明编写面 —— `契约声明/` 的**唯一写入口**（`开发规范.md` A2 · `接口面形状.md` §四）。

在仓库根执行（只用 Python 标准库；请求与返回都是 JSON，形状见 `形状.md`）：

    python 对外接口面/声明编写面/声明编写面.py --请求 '{"类别":"通知号","编号":null,"正文":{…}}'
    python 对外接口面/声明编写面/声明编写面.py --请求 - < 请求.json      # `-` = 读标准输入
    python 对外接口面/声明编写面/声明编写面.py --分配 通知号             # 只算号，不落盘

校验一律**转调** `构建装配/一键验证/一键验证.py`（面里没有第二套校验）；
它跑不动时回 `成功:false` + `面故障`（「暂时转调不了 + 缺什么」）。
退出码：成功 0 · 否则 1。

本文件是**路由**：解析命令行 → 调包里的公开面 → 打印 JSON。零业务实现。
"""

import json
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/壳.py）

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 声明编写面 import 建解析器, 处理分配, 处理写入, 读请求, 用法文本  # noqa: E402


def 入口函数(命令行参数: list) -> int:
    解析器 = 建解析器()
    选项 = 解析器.parse_args(命令行参数)
    if (选项.请求 is None) == (选项.分配 is None):
        print("用法：%s（--请求 与 --分配 二选一）" % 用法文本, file=sys.stderr)
        return 2
    仓根 = Path(选项.仓根).resolve() if 选项.仓根 else Path(__file__).resolve().parents[2]
    面根 = Path(__file__).resolve().parent

    if 选项.分配 is not None:
        响应, 退出码 = 处理分配(仓根, 选项.声明根, 选项.分配)
    else:
        请求, 错误 = 读请求(选项.请求)
        if 错误:
            响应, 退出码 = {"成功": False, "校验": [{"项": "请求形状", "缺什么": 错误,
                                            "为什么不能自愈": "请求形状不合法（等价 HTTP 400）"}]}, 1
        else:
            响应, 退出码 = 处理写入(仓根, 选项.声明根, 面根, 请求)
    print(json.dumps(响应, ensure_ascii=False, indent=2))
    return 退出码


if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="本面转调闸1 校验；若闸1 变慢，先修闸1（裁决 §三.3）"))
