#!/usr/bin/env python3
"""能力声明对齐入口；把 能力声明/*.json 按源码 const 表回灌。
# 生成物声明：{"生成器":"构建装配/形态装配/能力声明对齐.py","边界":["扩展根目录"]}
"""
import sys
import time
from pathlib import Path
起始时刻 = time.monotonic()
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 自门禁
from 构建装配.形态装配.能力声明对齐 import 入口函数
if __name__ == '__main__':
    sys.exit(自门禁(起始时刻,入口函数(sys.argv[1:]),尾巴余量毫秒=200,修法='对齐能力声明 json 与源码 const 表'))
