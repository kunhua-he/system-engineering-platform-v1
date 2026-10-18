# -*- coding: utf-8 -*-
"""反馈并发样本 —— 多进程并发批量提交：不同幂等键不丢、同键同文重放、同键异文拒。

**为什么单开一件**（判据 ⑲ 单件 ≤400 行）：并发这一档要真起子进程、真抢同一本库，
与 `反馈样本.py` 的正反/幂等/重启/迁移不是同一条关注点；各自一件，各自读得完。
"""

import json
import os
import subprocess
import sys

from 运行数据根.口径 import 覆盖变量名

并发脚本 = """
import json, sys
from pathlib import Path
仓根 = Path(sys.argv[1])
幂等键 = sys.argv[2]
sys.path.insert(0, str(仓根 / "开发工具"))
from MCP服务.反馈治理.反馈提交 import 提交反馈
退出码, 回执文本 = 提交反馈(仓根, "v1-900003", {"幂等键": 幂等键, "来源标识": "并发/报告.md",
    "报告指纹": "ab" * 16, "条目": [{"现象": "并发现象 " + 幂等键, "证据": "并发读数 " + 幂等键,
    "未测": "落点未定位"}]})
print(json.dumps({"退出码": 退出码, "回执文本": 回执文本}, ensure_ascii=False))
"""


def 并发提交(仓根, 环境, 幂等键表: list) -> list:
    """并发起一批 `提交反馈` 子进程 ⇒ `[(退出码, 回执读数字典或 None, 输出尾)]`（同序）。"""
    进程表 = [subprocess.Popen([sys.executable, "-B", "-c", 并发脚本, str(仓根), 幂等键],
                          env=环境, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
           for 幂等键 in 幂等键表]
    读数表 = []
    for 进程 in 进程表:
        输出, 错误 = 进程.communicate(timeout=5)
        try:
            读数 = json.loads(输出.strip())
        except (TypeError, ValueError):
            读数 = None
        读数表.append((进程.returncode, 读数, (错误 or "").strip()[-200:]))
    return 读数表


def 拆内层(读数):
    """子进程读数 ⇒ 内层回执字典（非 JSON / 形状不对 ⇒ 空字典）。"""
    if not isinstance(读数, dict):
        return {}
    内层文本 = 读数.get("回执文本")
    if not isinstance(内层文本, str):
        return {}
    try:
        内层读数 = json.loads(内层文本)
    except ValueError:
        return {}
    return 内层读数 if isinstance(内层读数, dict) else {}


def 并发样本(仓根, 临时根) -> list:
    """并发三档 ⇒ 样本表（`(说明, 通过)`）。"""
    from ...反馈治理 import 反馈账本 as 账本
    环境 = {**os.environ, 覆盖变量名: str(临时根)}
    样本表 = []

    异键读数 = 并发提交(仓根, 环境, ["并发键-1", "并发键-2", "并发键-3", "并发键-4"])
    新增表 = [拆内层(读数).get("新增条目") for _退出码, 读数, _尾 in 异键读数]
    样本表.append(("并发四进程（不同幂等键）全部退出码 0：%s"
              % [退出码 for 退出码, _读数, _尾 in 异键读数],
             all(退出码 == 0 for 退出码, _读数, _尾 in 异键读数)))
    样本表.append(("并发四进程各新增恰 1 条（不丢、不串）：%s" % (新增表,),
            新增表 == [1, 1, 1, 1]))
    连接 = 账本.连反馈库()
    try:
        落库数 = 连接.execute("select count(*) from 反馈条目 where 开工号 = ?",
                        ("v1-900003",)).fetchone()[0]
    finally:
        连接.close()
    样本表.append(("并发后库里该开工条目数 = 4（实际 %d）" % 落库数, 落库数 == 4))

    同键读数 = 并发提交(仓根, 环境, ["并发同键", "并发同键"])
    重放表 = [(退出码, bool(拆内层(读数).get("重放"))) for 退出码, 读数, _尾 in 同键读数]
    样本表.append(("并发同键同文：两条都退出码 0 且恰一条真写、一条重放：%s" % (重放表,),
            all(退出码 == 0 for 退出码, _重放 in 重放表)
            and sorted(重放 for _退出码, 重放 in 重放表) == [False, True]))
    return 样本表
