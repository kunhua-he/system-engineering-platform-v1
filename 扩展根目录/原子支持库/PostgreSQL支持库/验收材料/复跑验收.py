"""隔离HTTP验收入口；实现与入口分离。"""
import argparse
import json
import time
from HTTP实证 import 执行验收

if __name__ == '__main__':
    起始时刻 = time.monotonic()
    参数解析 = argparse.ArgumentParser()
    参数解析.add_argument('--仓根', required=True)
    参数解析.add_argument('--缓存根', required=True)
    参数解析.add_argument('--网关路径', required=True)
    参数解析.add_argument('--启动预算毫秒', required=True, type=int)
    命令参数 = 参数解析.parse_args()
    print(json.dumps(执行验收(命令参数.仓根, 命令参数.缓存根, 命令参数.网关路径, 命令参数.启动预算毫秒), ensure_ascii=False))
    print('验收墙钟毫秒=%s' % round((time.monotonic() - 起始时刻) * 1000))
