# -*- coding: utf-8 -*-
"""前置链 —— 链式接口（连接→提交→读结果）的依赖解析。

链式接口单独调必然「句柄无效」，所以先把前置资源备好：模型服务复用已载入的那一个
（每轮都起新的会累积到端口/内存不够，后面整条链全报「服务无效」），进程任务先跑一步。
依赖规则全在 `冒烟参数.json` 的 `链式` 段，本件只照它跑。
"""

import json
import re

from .运行上下文 import 上下文, 已解前置
from .请求发送 import 发一次带值


def 找已载入服务():
    """先找平台上已经载入的模型服务复用（句柄号段 900001 起试 100 个）。"""
    for 服务号 in range(900001, 900101):
        判定, _, 返回值 = 发一次带值(2514, {'服务句柄': 服务号})
        if 判定 != '成功':
            continue
        if isinstance(返回值, str):
            try:
                返回值 = json.loads(返回值)
            except Exception:
                continue
        if isinstance(返回值, dict) and 返回值.get('状态') == '已载入' and 返回值.get('存活'):
            return 服务号
    return 0


def 服务还活着(服务号):
    判定, _, 返回值 = 发一次带值(2514, {'服务句柄': 服务号})
    if 判定 != '成功':
        return False
    if isinstance(返回值, str):
        try:
            返回值 = json.loads(返回值)
        except Exception:
            return False
    return isinstance(返回值, dict) and 返回值.get('状态') == '已载入' and bool(返回值.get('存活'))


def 前置准备(配置=None):
    """把整轮共用的服务句柄备好：能复用就复用，不能才真起一个再等它就绪。"""
    配置 = 配置 or {}
    全局配置 = 配置.get('全局') or {}
    复用号 = 找已载入服务()
    if 复用号:
        上下文['服务句柄'] = 复用号
        return
    判定, _, 返回值 = 发一次带值(2512, {
        '模型引用': 全局配置.get('模型引用', ''),
        '可执行文件': 全局配置.get('可执行文件', '/opt/homebrew/bin/llama-server'),
        '启动参数': 全局配置.get('启动参数', ''),
        '监听端口': 0, '就绪路径': '', '模型类型': 'LLM文本模型',
        '闲置超时秒': 900, '载入超时秒': 60,
    })
    if 判定 == '成功' and isinstance(返回值, int):
        上下文['服务句柄'] = 返回值
    for _ in range(20):
        就绪判定, _, 就绪标记 = 发一次带值(2515, {'服务句柄': 上下文['服务句柄'], '超时毫秒': 800})
        if 就绪标记 is True:
            break


def 取前置值(返回值, 链规则):
    """从上一个接口的返回值里取出要给下一个用的句柄。"""
    if isinstance(返回值, list) and len(返回值) == 1:
        返回值 = 返回值[0]
    if isinstance(返回值, dict) and set(返回值) == {'类型标签', '值'}:
        返回值 = 返回值['值']
    if 链规则.get('取法') == 'JSON字段':
        if isinstance(返回值, str):
            try:
                返回值 = json.loads(返回值)
            except Exception:
                return None
        if not isinstance(返回值, dict):
            return None
        字段值 = 返回值.get(链规则.get('字段'))
        if 字段值 is None:
            return None
        模板 = 链规则.get('模板')
        return 模板 % 字段值 if 模板 else 字段值
    if 链规则.get('取法') == '直取':
        return 返回值
    if 链规则.get('取法') == 'HTML属性':
        属性名 = 链规则.get('属性', 'data-hs-h')
        if not isinstance(返回值, str):
            return None
        命中 = re.search(re.escape(属性名) + '="(\\d+)"', 返回值)
        return int(命中.group(1)) if 命中 else None
    return 返回值


def 前置链(配置, 编号):
    """按 `配置['链式']` 声明的依赖先跑前置，把句柄解出来填进参数里。"""
    链规则 = (配置.get('链式') or {}).get(str(编号))
    if not 链规则:
        return None
    前置号 = 链规则.get('前置')
    if 前置号 == '服务句柄':
        服务号 = 上下文.get('服务句柄')
        if not 服务号 or not 服务还活着(服务号):
            服务号 = 找已载入服务()
            if not 服务号:
                return None
            上下文['服务句柄'] = 服务号
        return 服务号
    if 前置号 == '服务状态':
        服务号 = 上下文.get('服务句柄')
        if not 服务号:
            服务号 = 找已载入服务()
            if not 服务号:
                return None
            上下文['服务句柄'] = 服务号
        判定, _, 返回值 = 发一次带值(2514, {'服务句柄': 服务号})
        if 判定 != '成功':
            return None
        return 取前置值(返回值, 链规则)
    if 前置号 not in 已解前置:
        前置入参 = dict((配置.get('按编号') or {}).get(str(前置号)) or {})
        # 前置自身也可能要解链（比如 2501 要先拿服务端口），递归补上。
        前置链规则 = (配置.get('链式') or {}).get(str(前置号))
        if 前置链规则:
            前置值 = 前置链(配置, 前置号)
            if 前置值 is None:
                已解前置[前置号] = ('参数错', None)
                return None
            前置入参[前置链规则['填']] = 前置值
        else:
            # 没声明链但参数里还有未替换的模板，说明前置条件不满足。
            for 参数值 in 前置入参.values():
                if isinstance(参数值, str) and 参数值.startswith('{') and 参数值.endswith('}'):
                    已解前置[前置号] = ('参数错', None)
                    return None
        判定, _, 返回值 = 发一次带值(前置号, 前置入参)
        已解前置[前置号] = (判定, 返回值)
    判定, 返回值 = 已解前置[前置号]
    if 判定 != '成功':
        return None
    return 取前置值(返回值, 链规则)
