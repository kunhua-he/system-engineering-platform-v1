"""模型调用 —— 底座一个能力（2519 一次对话）包三行用法。

    from 模型 import 对话
    print(对话("你好"))

整条链（复用或拉起 → 等就绪 → 申请许可 → 连接 → 提交 → 取结果 → 清理）都在底座里办完。
本文件只把参数拼成底座要的形状，不自己拼十几步请求 —— 否则同一件事就有两套做法。
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

网关 = "http://127.0.0.1:43110"
调用路径 = urllib.parse.quote("/接口/调用")

一次对话 = 2519      # 整条链，一个请求
取生成结果 = 2503    # 只在超过底座等待上限、回了任务句柄时才用
资源快照 = 2507      # 看现在跑着哪些模型

默认超时秒 = 180


class 模型错误(Exception):
    """底座明确报出来的失败，消息里是真错误名，不是「调用失败」四个字。"""


def _调(编号, 参数=None, 超时=默认超时秒):
    """打一次底座，返回剥干净的「值」。任何失败都翻译成 模型错误。"""
    体 = json.dumps({"编号": 编号, "命名值": 参数 or {}}, ensure_ascii=False).encode()
    请求 = urllib.request.Request(网关 + 调用路径, 体, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(请求, timeout=超时) as 响应:
            回执 = json.loads(响应.read())
    except urllib.error.HTTPError as 错:
        raise 模型错误("底座 HTTP %d：%s" % (错.code, 错.read().decode()[:300]))
    except urllib.error.URLError as 错:
        raise 模型错误("连不上底座 %s：%s" % (网关, 错.reason))
    if not 回执.get("成功"):
        错误 = 回执.get("错误", {})
        raise 模型错误("%s（码 %s）" % (错误.get("名称", "未知错误"), 错误.get("码")))
    值 = _纯(回执.get("值"))
    # 底座单个返回也套一层列表：[{类型标签:…, 值:…}] → 拆出来
    if isinstance(值, list) and len(值) == 1:
        值 = 值[0]
    return 值


def _纯(值):
    """剥掉底座信封上的 {类型标签, 值} 标签，剥到底。"""
    if isinstance(值, dict) and set(值) == {"类型标签", "值"}:
        return _纯(值["值"])
    if isinstance(值, dict):
        return {键: _纯(项) for 键, 项 in 值.items()}
    if isinstance(值, list):
        return [_纯(项) for 项 in 值]
    return 值


def _记消息(条):
    """一条消息 → 底座要的形状（每个字段各带标签）。"""
    if isinstance(条, str):
        条 = {"role": "user", "content": 条}
    return {"类型标签": 101, "值": {键: {"类型标签": 4, "值": 值} for 键, 值 in 条.items()}}


def _跑一次(模型类型, 消息列表, 系统提示词="", 温度=0.7, 最大令牌数=2048, 超时秒=默认超时秒):
    """一次对话。模型没起底座会拉起，起了就复用，默认模型不用传路径。"""
    回 = _调(一次对话, {
        "消息列表": {"类型标签": 100, "值": 消息列表},
        "系统提示词": 系统提示词,
        "温度": 温度,
        "最大令牌数": 最大令牌数,
        "模型类型": 模型类型,
        "模型引用": "",
        "等待毫秒": min(超时秒 * 1000, 110000),
    }, 超时=超时秒)

    if 回.get("已完成"):
        内容 = 回.get("内容") or ""
        return 内容 if isinstance(内容, str) else str(内容)

    # 超过底座等待上限没生成完：它回任务句柄，接着取
    任务 = 回.get("任务句柄") or 0
    if not 任务:
        raise 模型错误("没拿到内容也没拿到任务句柄：%s" % 回.get("说明", ""))

    截止 = time.time() + 超时秒
    while time.time() < 截止:
        结果 = _调(取生成结果, {"任务句柄": {"类型标签": 7, "值": 任务}}, 超时=超时秒)
        if 结果.get("已完成"):
            错误信息 = 结果.get("错误信息") or ""
            if 错误信息:
                raise 模型错误("生成失败：%s" % 错误信息)
            内容 = 结果.get("内容") or ""
            return 内容 if isinstance(内容, str) else str(内容)
        time.sleep(0.2)
    raise 模型错误("等生成结果超过 %d 秒" % 超时秒)


def 对话(消息, 系统提示词="", 温度=0.7, 最大令牌数=2048, 超时秒=默认超时秒):
    """一句话对话。消息可以是字符串，也可以是 [{"role":"user","content":"…"}] 多轮。"""
    if isinstance(消息, str):
        列表 = [_记消息(消息)]
    else:
        列表 = [_记消息(条) for 条 in 消息]
    return _跑一次("LLM文本模型", 列表, 系统提示词, 温度, 最大令牌数, 超时秒)


def 看图(图片路径, 问题="描述这张图", 超时秒=默认超时秒):
    """让视觉模型看一张本地图片。"""
    import base64

    with open(图片路径, "rb") as 文件:
        数据 = base64.b64encode(文件.read()).decode()
    消息 = {"类型标签": 101, "值": {
        "role": {"类型标签": 4, "值": "user"},
        "content": {"类型标签": 100, "值": [
            {"类型标签": 101, "值": {
                "type": {"类型标签": 4, "值": "text"},
                "text": {"类型标签": 4, "值": 问题}}},
            {"类型标签": 101, "值": {
                "type": {"类型标签": 4, "值": "image_url"},
                "image_url": {"类型标签": 101, "值": {
                    "url": {"类型标签": 4, "值": "data:image/jpeg;base64," + 数据}}}}},
        ]},
    }}
    return _跑一次("VLM看图模型", [消息], "", 0.2, 1024, 超时秒)


def 状态():
    """现在跑着哪些模型。"""
    return _调(资源快照)


if __name__ == "__main__":
    import sys
    print(对话(sys.argv[1] if len(sys.argv) > 1 else "你好，用一句话介绍你自己"))
