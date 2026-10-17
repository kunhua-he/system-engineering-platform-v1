"""发布准备参数；错误必须带具体节点。"""
import argparse
import json
import sys
from .核心 import 准备执行映像

def 入口函数(参数表):
    解析器=argparse.ArgumentParser(description='用生产启动入口准备宿主只读执行映像；模块进程仍按需启动。')
    解析器.add_argument('--仓根',required=True)
    解析器.add_argument('--代码缓存根',required=True)
    解析器.add_argument('--日志路径',required=True)
    参数项=解析器.parse_args(参数表)
    try:回执=准备执行映像(参数项.仓根,参数项.代码缓存根,参数项.日志路径)
    except (OSError,RuntimeError) as 失败原因:
        print('执行映像准备失败：'+str(失败原因),file=sys.stderr);return 1
    print(json.dumps(回执,ensure_ascii=False));return 0
