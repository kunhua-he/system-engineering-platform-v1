# -*- coding: utf-8 -*-
"""打一次底座并剥干净返回值 —— 任何失败都翻译成 `模型错误`。

只做两件事：发那一个 `POST /接口/调用`，把回执剥到底。**不猜业务**：
成不成由回执的 `成功` 位说了算，错误名照抄底座给的那一个。
"""
import json
import urllib.error
import urllib.request

from .底座地址 import 网关, 调用路径, 默认超时秒


class 模型错误(Exception):
    """底座明确报出来的失败，消息里是真错误名，不是「调用失败」四个字。"""


def 打到底座(编号, 参数=None, 超时=默认超时秒):
    """打一次底座，返回剥干净的「值」。任何失败都翻译成 模型错误。"""
    请求体 = json.dumps({"编号": 编号, "命名值": 参数 or {}}, ensure_ascii=False).encode()
    请求 = urllib.request.Request(网关 + 调用路径, 请求体, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(请求, timeout=超时) as 响应:
            回执 = json.loads(响应.read())
    except urllib.error.HTTPError as 异常:
        raise 模型错误("底座 HTTP %d：%s" % (异常.code, 异常.read().decode()[:300]))
    except urllib.error.URLError as 异常:
        raise 模型错误("连不上底座 %s：%s" % (网关, 异常.reason))
    if not 回执.get("成功"):
        错误项 = 回执.get("错误", {})
        raise 模型错误("%s（码 %s）" % (错误项.get("名称", "未知错误"), 错误项.get("码")))
    剥后值 = 剥信封(回执.get("值"))
    # 底座单个返回也套一层列表：[{类型标签:…, 值:…}] → 拆出来
    if isinstance(剥后值, list) and len(剥后值) == 1:
        剥后值 = 剥后值[0]
    return 剥后值


def 剥信封(候选值):
    """剥掉底座信封上的 {类型标签, 值} 标签，剥到底。"""
    if isinstance(候选值, dict) and set(候选值) == {"类型标签", "值"}:
        return 剥信封(候选值["值"])
    if isinstance(候选值, dict):
        return {键名: 剥信封(子项) for 键名, 子项 in 候选值.items()}
    if isinstance(候选值, list):
        return [剥信封(子项) for 子项 in 候选值]
    return 候选值
