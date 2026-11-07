# -*- coding: utf-8 -*-
"""按目标惰性创建前置，禁止扫描或借用其他轮次的资源。"""
import json
import time
from html.parser import HTMLParser
from pathlib import Path

from .运行上下文 import 上下文, 本轮资源
from .请求发送 import 发一次带值


class 属性解析器(HTMLParser):
    def __init__(自身, 属性名, 组件类型='', 属性筛选=None):
        super().__init__()
        自身.属性名 = 属性名
        自身.组件类型 = 组件类型
        自身.属性筛选 = 属性筛选 or {}
        自身.句柄 = None

    def handle_starttag(自身, 标签, 属性表):
        属性集 = dict(属性表)
        if any(属性集.get(属性键) != 属性值 for 属性键, 属性值 in 自身.属性筛选.items()):
            return
        if 自身.组件类型 and 自身.组件类型 not in 属性集.get('class', ''):
            return
        属性值 = 属性集.get(自身.属性名, '')
        if 自身.句柄 is None and 属性值.isdecimal():
            自身.句柄 = int(属性值)


def 取前置值(返回值, 链规则):
    while isinstance(返回值, list) and len(返回值) == 1:
        返回值 = 返回值[0]
    if isinstance(返回值, dict) and set(返回值) == {'类型标签', '值'}:
        返回值 = 返回值['值']
    取法 = 链规则.get('取法')
    if 取法 in ('JSON字段', 'HTML属性') and isinstance(返回值, str):
        try:
            返回值 = json.loads(返回值)
        except (ValueError, TypeError):
            pass
    if 取法 == 'JSON字段':
        字段值 = 返回值.get(链规则.get('字段')) if isinstance(返回值, dict) else None
        模板 = 链规则.get('模板')
        return 模板 % 字段值 if 模板 and 字段值 is not None else 字段值
    if 取法 == 'HTML属性':
        if isinstance(返回值, dict):
            返回值 = 返回值.get('片段', '')
        if not isinstance(返回值, str):
            return None
        解析器 = 属性解析器(链规则.get('属性', 'data-hs-h'), 链规则.get('组件类型', ''), 链规则.get('属性筛选'))
        解析器.feed(返回值)
        return 解析器.句柄
    return 返回值


def 记录调用(编号, 入参表):
    判定, 说明, 返回值 = 发一次带值(编号, 入参表)
    if 判定 != '成功':
        return 判定, 说明, 返回值
    释放表 = {2512: (2513, '服务句柄'), 2516: (2517, '许可句柄'),
              7001: (7006, '会话句柄'), 2502: (2505, '任务句柄'),
              2601: (2604, '任务句柄'), 2405: (2408, '任务句柄'), 2501: (2506, '句柄'),
              2508: (2506, '句柄'), 2510: (2506, '句柄'), 5401: (5404, '连接编号')}
    if 编号 in 释放表:
        释放号, 参数名 = 释放表[编号]
        句柄 = 取前置值(返回值, {})
        if 句柄 not in (None, False, ''):
            释放入参 = {参数名: 句柄}
            if 释放号 == 2513:
                释放入参['强制'] = False
            本轮资源.append((释放号, 释放入参))
    if 编号 == 4928:
        # 每个组件均有独立句柄，不能只释放根。
        片段 = 取前置值(返回值, {'取法': '直取'})
        if isinstance(片段, str):
            try:
                片段 = json.loads(片段)
            except ValueError:
                pass
        if isinstance(片段, dict):
            片段 = 片段.get('片段', '')
        import re
        for 句柄文本 in set(re.findall(r'data-hs-h=["\'](\d+)["\']', str(片段))):
            本轮资源.append((4931, {'组件句柄': int(句柄文本)}))
    for 释放记录 in list(本轮资源):
        if 编号 == 释放记录[0] and all(入参表.get(参数名) == 参数值 for 参数名, 参数值 in 释放记录[1].items()):
            if 返回值 is False:
                return '回收失败', '上游 %s：返回假，退出或归还未确认' % 编号, 返回值
            本轮资源.remove(释放记录)
    return 判定, 说明, 返回值


def 释放本轮资源(释放号表=None):
    失败表 = []
    for 释放号, 入参表 in reversed(本轮资源[:]):
        if 释放号表 is not None and 释放号 not in 释放号表:
            continue
        try:
            if 释放号 == 2505:
                发一次带值(2504, 入参表)
            判定, 说明, 返回值 = 发一次带值(释放号, 入参表)
            if 判定 != '成功' or 返回值 is False:
                失败表.append('%s 回收失败：%s %s' % (释放号, 判定, 说明))
            else:
                本轮资源.remove((释放号, 入参表))
        except Exception as 异常:
            失败表.append('%s 回收异常：%s' % (释放号, 异常))
    return 失败表


def 前置准备(配置=None, 模型类型=None):
    """无模型目标不调用；缺显式类型配置或真实权重时明确未覆盖。"""
    if 模型类型 is None:
        return None
    配置 = 配置 or {}
    服务表 = 上下文.setdefault('本轮服务', {})
    if 模型类型 in 服务表:
        return 服务表[模型类型]
    模型配置 = (配置.get('模型准备') or {}).get(模型类型)
    if not 模型配置 or 模型配置.get('模型类型') != 模型类型:
        raise RuntimeError('2512 未覆盖：缺少 %s 的显式模型准备' % 模型类型)
    if not Path(模型配置.get('模型引用', '')).is_file():
        raise RuntimeError('2512 未覆盖：%s 权重不存在：%s' % (模型类型, 模型配置.get('模型引用')))
    判定, 说明, 服务号 = 记录调用(2512, dict(模型配置))
    if 判定 != '成功' or type(服务号) is not int or 服务号 <= 0:
        raise RuntimeError('上游 2512：%s %s' % (判定, 说明))
    等待期限秒 = 模型配置.get('载入超时秒', 60)
    if type(等待期限秒) is not int or 等待期限秒 <= 0:
        raise RuntimeError('2512 未覆盖：载入超时秒须为正整数')
    截止时刻 = time.monotonic() + 等待期限秒
    while True:
        判定, 说明, 状态内容 = 记录调用(2514, {'服务句柄': 服务号})
        if 判定 != '成功':
            raise RuntimeError('上游 2514：%s %s' % (判定, 说明))
        if isinstance(状态内容, str):
            状态内容 = json.loads(状态内容)
        if not isinstance(状态内容, dict) or 状态内容.get('模型类型') != 模型类型:
            raise RuntimeError('上游 2514：状态形状或模型类型不符')
        if 状态内容.get('存活') is not True or 状态内容.get('状态') in ('已退出', '载入失败'):
            raise RuntimeError('上游 2514：服务未就绪：%s' % 状态内容.get('状态'))
        if 状态内容.get('状态') == '已载入':
            break
        剩余等待秒 = 截止时刻 - time.monotonic()
        if 剩余等待秒 <= 0:
            raise RuntimeError('上游 2514：%s 在 %s 秒内未确认就绪' % (模型类型, 等待期限秒))
        time.sleep(min(0.05, 剩余等待秒))
    服务表[模型类型] = 服务号
    上下文['服务句柄'] = 服务号
    return 服务号


def 前置链(配置, 编号, 访问链=None):
    链规则 = (配置.get('链式') or {}).get(str(编号))
    if not 链规则:
        return None
    访问链 = set(访问链 or ())
    if 编号 in 访问链:
        raise RuntimeError('上游 %s：依赖环' % 编号)
    访问链.add(编号)
    前置号 = 链规则.get('前置')
    模型类型 = 链规则.get('模型类型', 'LLM文本模型')
    if 前置号 in ('服务句柄', '服务状态'):
        服务号 = 前置准备(配置, 模型类型)
        if 前置号 == '服务句柄':
            return 服务号
        判定, 说明, 返回值 = 记录调用(2514, {'服务句柄': 服务号})
        状态内容 = json.loads(返回值) if isinstance(返回值, str) else 返回值
        if 判定 == '成功' and isinstance(状态内容, dict) and 状态内容.get('模型类型') != 模型类型:
            raise RuntimeError('上游 2514：模型类型不符，期望 ' + 模型类型)
    else:
        前置入参 = dict((配置.get('按编号') or {}).get(str(前置号)) or {})
        前置链规则 = (配置.get('链式') or {}).get(str(前置号))
        if 前置链规则:
            前置入参[前置链规则['填']] = 前置链(配置, 前置号, 访问链)
        # 不缓存有副作用结果；每次申请许可或会话都获得新句柄。
        判定, 说明, 返回值 = 记录调用(前置号, 前置入参)
    if 判定 != '成功':
        raise RuntimeError('上游 %s：%s %s' % (前置号, 判定, 说明))
    if 前置号 == 7001 and 编号 in (7003, 7004, 7005):
        页面入参 = dict((配置.get('按编号') or {}).get('7002') or {})
        页面入参['会话句柄'] = 返回值
        页面判定, 页面说明, _ = 记录调用(7002, 页面入参)
        if 页面判定 != '成功':
            raise RuntimeError('上游 7002：%s %s' % (页面判定, 页面说明))
    前置值 = 取前置值(返回值, 链规则)
    if 前置值 is None:
        raise RuntimeError('上游 %s：返回缺少 %s' % (前置号, 链规则.get('字段', 链规则.get('属性', '值'))))
    return 前置值
