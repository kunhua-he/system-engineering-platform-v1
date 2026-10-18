# -*- coding: utf-8 -*-
"""正式自测调度三件主仓保护全部隔离正反样本。"""
from pathlib import Path


def 自检_保全主目录():
    from ..共享夹具.自测闭包 import 跑自测闭包
    仓根 = Path(__file__).resolve().parents[4]
    脚本 = "from 开发工具.MCP服务.验证样本.集成管理.保全主目录样本 import 跑样本; raise SystemExit(跑样本())"
    退出码, 说明 = 跑自测闭包(脚本, 仓根)
    return [("主仓三件保护完整隔离样本", 退出码 == 0, "退出码 %d\n%s" % (退出码, 说明))]
