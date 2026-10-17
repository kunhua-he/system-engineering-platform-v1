#!/usr/bin/env python3
"""独立扩展锁文件生成；网络下载属于事先显式执行的环境准备。
# 生成物声明：{"生成器":"构建装配/形态装配/准备扩展依赖.py","边界":["扩展根目录/原子支持库"]}
"""
import sys
import time
from pathlib import Path
起始时刻=time.monotonic()
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 自门禁
from 构建装配.形态装配.准备扩展依赖 import 入口函数
if __name__=='__main__':
    sys.exit(自门禁(起始时刻,入口函数(sys.argv[1:]),尾巴余量毫秒=200,修法='先显式准备已锁定第三方引擎缓存，再生成扩展Cargo锁'))
