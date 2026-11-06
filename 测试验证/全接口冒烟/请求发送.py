# -*- coding: utf-8 -*-
"""请求发送 —— 一次 `POST /接口/调用` 的两种回执形状（要不要带值）。

判据三档：成功 / 参数错（到了业务层，链路通）/ 协议错（HTTP 400，文档与实现对不上）。
单次超时按五秒上限量：冒烟不该靠长等 —— 跑不完的接口是接口慢，不是探测要等更久。
"""

import json
import urllib.error
import urllib.parse
import urllib.request

接口地址 = 'http://127.0.0.1:43110' + urllib.parse.quote('/接口/调用')

# 一次请求的上限（秒）。整轮要发两百多次，单次一等就是几十秒 ⇒ 只留五秒。
单次超时秒 = 5


def 取请求体(编号, 入参表):
    return json.dumps({'编号': 编号, '命名值': 入参表}, ensure_ascii=False).encode()


def 发一次带值(编号, 入参表):
    """同 发一次，但把成功时的值也带回来（前置准备要读句柄/端口）。"""
    报文体 = 取请求体(编号, 入参表)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(接口地址, 报文体, {'Content-Type': 'application/json'}),
                timeout=单次超时秒) as 响应:
            回执数据 = json.loads(响应.read())
        if not 回执数据.get('成功'):
            return '参数错', (回执数据.get('错误') or {}).get('名称', ''), None
        返回值 = 回执数据.get('值')
        if isinstance(返回值, list) and len(返回值) == 1:
            返回值 = 返回值[0]
        if isinstance(返回值, dict) and set(返回值) == {'类型标签', '值'}:
            返回值 = 返回值['值']
        return '成功', '', 返回值
    except Exception as 异常:
        return '连不上', type(异常).__name__, None


def 发一次(编号, 入参表):
    """只回 (判定, 说明)；协议错与「文件已存在」这类非缺陷都要分得开。"""
    报文体 = 取请求体(编号, 入参表)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(接口地址, 报文体, {'Content-Type': 'application/json'}),
                timeout=单次超时秒) as 响应:
            回执数据 = json.loads(响应.read())
        错误名 = (回执数据.get('错误') or {}).get('名称', '')
        if 错误名 == '文件已存在':
            错误名 = '文件已存在（输出路径撞名，非缺陷）'
        return '成功' if 回执数据.get('成功') else '参数错', 错误名
    except urllib.error.HTTPError as 异常:
        错误正文 = 异常.read().decode()
        try:
            协议错说 = json.loads(错误正文).get('协议错误', '')
        except Exception:
            协议错说 = 错误正文[:120]
        return '协议错', 协议错说[:160]
    except Exception as 异常:
        return '连不上', type(异常).__name__
