# -*- coding: utf-8 -*-
"""采样取回 —— 对纯计算库现场发一次请求，把真返回当样例；失败只记账、不写进文档。

为什么失败不写进文档：文档里放错误样例，读的人会以为那是正常返回。
为什么超时是 5 秒：这是「允许**别的**命令跑多久」的容忍度，按命令级效率目标取
（决策记录 `2026-09-27_所有运行五秒硬顶.md` §一）；真撞超时该做的是提速，不是调大容忍度。
"""

import json
import urllib.request

from .基座常量 import 接口
from .样例编造 import 剥标签

# 直连开启器：一次建好，全量采样共用。
# 提速点就在这一行 —— 默认 opener 每发一次请求都要去问操作系统的代理配置（macOS 上是
# 一次子进程调用），而本命令只对 127.0.0.1 采样 ⇒ 一律直连，省掉每请求的代理解析，
# 也顺手保证这条路不许偷偷出网。
直连开启器 = urllib.request.build_opener(urllib.request.ProxyHandler({}))

采样失败 = []


def 采样(编号, 模板):
    """真发一次请求。失败就返回 None —— 文档里不放错误样例。"""
    请求体 = json.dumps({'编号': 编号, '命名值': 模板}, ensure_ascii=False).encode()
    try:
        请求 = urllib.request.Request(接口, 请求体, {'Content-Type': 'application/json'})
        with 直连开启器.open(请求, timeout=5) as 回包:
            回包数据 = json.loads(回包.read())
    except Exception as 异常:
        采样失败.append('%d %s' % (编号, type(异常).__name__))
        return None
    if not 回包数据.get('成功'):
        采样失败.append('%d %s' % (编号, (回包数据.get('错误') or {}).get('名称', '')))
        return None
    去掉标签 = 剥标签(回包数据.get('值'))
    if isinstance(去掉标签, list) and len(去掉标签) == 1:
        去掉标签 = 去掉标签[0]
    return 去掉标签
