#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把子代理回传的配参片段合并进 `冒烟参数.json` 的「按编号」层。

为什么要有它：配参是并行派活做的，每个子代理只写自身那组的片段；
合并只认片段里的键，冲突时后写的覆盖先写的（片段按编号分，实际不会撞）。
片段落点是运行数据根的**临时件**子目录（`配参片段_*.json`），不再自拼临时路径。

用法：python3 测试验证/合并配参片段.py
"""

import json
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包**之前**（见 构建装配/门禁/命令壳.py）

仓根 = Path(__file__).resolve().parents[1]
if str(仓根) not in sys.path:
    sys.path.insert(0, str(仓根))

from 构建装配.门禁 import 自门禁  # noqa: E402
from 开发工具.运行数据根 import 解析当前环境, 确保子目录  # noqa: E402

配置路径 = 仓根 / '测试验证/冒烟参数.json'
片段目录 = 确保子目录(解析当前环境(), '临时件')


def 入口函数(argv=None):
    """合并全部片段，打一条读数；一条片段都没找到退 1（没有可合的东西就是没干活）。"""
    配置 = json.loads(配置路径.read_text(encoding='utf-8'))
    按号 = 配置.setdefault('按编号', {})

    片段们 = sorted(片段目录.glob('配参片段_*.json'))
    片段们 = [片段件 for 片段件 in 片段们 if '未通' not in 片段件.name]
    if not 片段们:
        print('没找到配参片段（%s/配参片段_*.json）' % 片段目录)
        return 1

    for 片段 in 片段们:
        try:
            片段数据 = json.loads(片段.read_text(encoding='utf-8'))
        except Exception as 异常:
            print('  %s 读不动：%s' % (片段.name, 异常))
            continue
        if not isinstance(片段数据, dict):
            print('  %s 格式不对，跳过' % 片段.name)
            continue
        for 编号, 入参表 in 片段数据.items():
            if not isinstance(入参表, dict) or not 入参表:
                continue  # 空字典不许覆盖已有配置
            按号[str(编号)] = 入参表

    配置路径.write_text(json.dumps(配置, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('合并 %d 个片段，按编号层共 %d 条参数配置' % (len(片段们), len(按号)))

    未通片段 = sorted(片段目录.glob('配参片段_*_未通.json'))
    if 未通片段:
        未通总数 = 0
        for 未通件 in 未通片段:
            try:
                未通总数 += len(json.loads(未通件.read_text(encoding='utf-8')))
            except Exception:
                pass
        print('另有 %d 条仍未配通（片段在 %s/配参片段_*_未通.json）' % (未通总数, 片段目录))
    return 0


if __name__ == '__main__':
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                   修法="片段多时别扫全目录重读：已合并过的片段挪走或按戳筛，只读新增件"))
