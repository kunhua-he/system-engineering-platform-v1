# -*- coding: utf-8 -*-
"""正式长自测中的真实 HTTP 重载样本；短自检仍验证入口与协议。"""
from pathlib import Path


def 自检_HTTP自愈():
    import sys
    仓根 = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(仓根 / "开发工具"))
    from MCP服务.验证样本.服务协议.http自愈样本 import 重载样本
    try:
        return 重载样本(仓根)
    except Exception as 错误:
        return [("HTTP真实重载未完整完成", False, repr(错误))]
