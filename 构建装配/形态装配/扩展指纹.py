#!/usr/bin/env python3
"""全扩展指纹入口；只处理归本生成器所有的快照。
# 生成物声明：{"生成器":"构建装配/形态装配/扩展指纹.py","边界":["扩展根目录"]}
"""
import sys
import time
from pathlib import Path
起始时刻 = time.monotonic()
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 自门禁
from 构建装配.形态装配.扩展指纹 import 入口函数
if __name__ == '__main__':
    sys.exit(自门禁(起始时刻,入口函数(sys.argv[1:]),尾巴余量毫秒=200,修法='检查快照与当前扩展声明及源码'))
