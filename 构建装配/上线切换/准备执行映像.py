#!/usr/bin/env python3
"""发布准备入口；不启动业务能力，不切换流量。"""
import sys
import time
起始时刻=time.monotonic()
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 自门禁
from 构建装配.上线切换.准备执行映像 import 入口函数
if __name__=='__main__':
    sys.exit(自门禁(起始时刻,入口函数(sys.argv[1:]),尾巴余量毫秒=200,修法='宿主映像准备与调用分段计时，保留真实日志和环境准备耗时'))
