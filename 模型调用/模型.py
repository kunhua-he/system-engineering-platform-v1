"""一句话调用本机模型。

用法只有三行：

    import sys; sys.path.insert(0, "/Users/hekunhua/Documents/Agent/PHP/系统工程平台V1/模型调用")
    from 模型 import 对话
    print(对话("你好，用一句话介绍你自己"))

其它可选的：

    看图(图片路径, "图片里是什么")       → 视觉模型回答
    嵌入(文本列表)                      → 向量
    状态()                              → 当前跑着哪些模型

内部自动做完一整条链，调用方不需要知道有 2512 / 2514 / 2516 / 2501 / 2502 / 2503 这些能力：
拉起服务 → 等真就绪 → 申请推理许可 → 连接模型 → 提交任务 → 读结果 → 归还许可。
服务不释放，留给闲置超时自动退出内存。
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

底座 = "http://127.0.0.1:43110"
模型目录 = "/Users/hekunhua/Documents/AI模型"
文本模型 = 模型目录 + "/文本模型/Qwen3-8B-Q4_K_M.gguf"
看图模型 = 模型目录 + "/图片分析模型/Qwen3VL-8B-Instruct-Q4_K_M.gguf"
推理引擎 = "/opt/homebrew/bin/llama-server"
启动参数 = "-m {模型文件} --host 127.0.0.1 --port {端口} -c 8192 --no-webui"

_调用路径 = urllib.parse.quote("/接口/调用")


class 模型错误(Exception):
    """底座报错时抛这个，消息里带真正的错误名（不是「调用失败」四个字）。"""


def _调(编号, 参数=None, 超时=60):
    """调底座一个能力，返回它的「值」。失败抛 模型错误。"""
    体 = json.dumps({"编号": 编号, "命名值": 参数 or {}}, ensure_ascii=False).encode()
    请求 = urllib.request.Request(底座 + _调用路径, 体, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(请求, timeout=超时) as 响应:
            回执 = json.loads(响应.read())
    except urllib.error.HTTPError as 错:
        raise 模型错误("底座 HTTP %d：%s" % (错.code, 错.read().decode()[:200]))
    except urllib.error.URLError as 错:
        raise 模型错误("连不上底座 %s：%s" % (底座, 错.reason))
    if not 回执.get("成功"):
        错误 = 回执.get("错误", {})
        raise 模型错误("%s（码 %s）" % (错误.get("名称", "未知错误"), 错误.get("码")))
    值 = 回执.get("值")
    if isinstance(值, list) and 值 and isinstance(值[0], dict) and "值" in 值[0]:
        return 值[0]["值"]
    return 值


def _解(值):
    """底座有些回执是 JSON 字符串，统一转成 dict。"""
    if isinstance(值, str):
        try:
            return json.loads(值)
        except ValueError:
            return {"内容": 值}
    return 值 if isinstance(值, dict) else {}


def _纯(值):
    """把带类型标签的格子剥成裸值。复合对象逐字段递归剥。"""
    if isinstance(值, dict) and set(值) == {"类型标签", "值"}:
        return _纯(值["值"])
    if isinstance(值, dict):
        return {键: _纯(项) for 键, 项 in 值.items()}
    if isinstance(值, list):
        return [_纯(项) for 项 in 值]
    return 值


# 记着自己拉起过的服务：模型文件 → 服务句柄。
# 不复用就会每次对话都新起一个进程，几轮下来内存就爆了。
# 注意 `2507 资源快照` 里是**连接句柄**（字段 句柄/地址/模型），拿不到服务句柄，所以只能自查。
_服务缓存 = {}


def _服务还活着(句柄):
    """用 2514 探一下这个服务句柄还在不在、能不能用。"""
    try:
        状态 = _纯(_解(_调(2514, {"服务句柄": 句柄})))
    except 模型错误:
        return None
    return 状态 if 状态.get("状态") == "已载入" else None


def _确保服务(模型文件, 模型类型, 超时秒):
    """拿到一个已就绪的服务端口。已有的还活着就复用，没有就拉起再等。"""
    老句柄 = _服务缓存.get(模型文件)
    if 老句柄 is not None:
        状态 = _服务还活着(老句柄)
        if 状态:
            return 状态["监听端口"], 老句柄
        _服务缓存.pop(模型文件, None)

    句柄 = _调(2512, {
        "模型引用": 模型文件,
        "可执行文件": 推理引擎,
        "启动参数": 启动参数,
        "监听端口": 0,
        "就绪路径": "",
        "模型类型": 模型类型,
        "闲置超时秒": 900,
        "载入超时秒": 30,
    })
    截止 = time.time() + 超时秒
    while time.time() < 截止:
        状态 = _纯(_解(_调(2514, {"服务句柄": 句柄})))
        if 状态.get("状态") == "已载入":
            _服务缓存[模型文件] = 句柄
            return 状态["监听端口"], 句柄
        if 状态.get("状态") in ("载入失败", "已退出"):
            raise 模型错误("模型载入%s：%s" % (状态.get("状态"), 模型文件))
        time.sleep(0.3)
    raise 模型错误("等模型就绪超过 %d 秒，模型可能太大或内存不足" % 超时秒)


def _跑一次(模型文件, 模型类型, 消息列表, 系统提示词, 温度, 最大令牌数, 超时秒):
    端口, 服务句柄 = _确保服务(模型文件, 模型类型, 超时秒)
    许可 = None
    连接 = None
    任务 = None
    try:
        许可 = _调(2516, {"服务句柄": 服务句柄, "等待毫秒": 3000, "租约毫秒": 5000})
        连接 = _调(2501, {
            "模型": 模型文件,
            "服务器地址": "http://127.0.0.1:%d" % 端口,
            "接口密钥": "",
            "协议": "chat_completions",
            "静态请求头": {"类型标签": 101, "值": {}},
            "模型类型": 模型类型,
        })
        任务 = _调(2502, {
            "句柄": {"类型标签": 6, "值": 连接},
            "消息列表": {"类型标签": 100, "值": 消息列表},
            "系统提示词": 系统提示词,
            "温度": 温度,
            "最大令牌数": 最大令牌数,
            "工具": {"类型标签": 100, "值": []},
            "响应格式": {"类型标签": 101, "值": {}},
            "附加请求头": {"类型标签": 101, "值": {}},
        })
        截止 = time.time() + 超时秒
        while time.time() < 截止:
            结果 = _纯(_解(_调(2503, {"任务句柄": {"类型标签": 7, "值": 任务}})))
            if 结果.get("已完成"):
                if 结果.get("结束原因") not in (None, "stop", "length"):
                    raise 模型错误("生成中断：%s" % 结果.get("结束原因"))
                return 结果.get("内容", "")
            time.sleep(0.2)
        raise 模型错误("等生成结果超过 %d 秒" % 超时秒)
    finally:
        if 许可:
            try:
                _调(2517, {"许可句柄": 许可})
            except 模型错误:
                pass
        if 任务 is not None:
            try:
                _调(2505, {"任务句柄": {"类型标签": 7, "值": 任务}})
            except 模型错误:
                pass
        if 连接:
            try:
                _调(2506, {"句柄": {"类型标签": 6, "值": 连接}})
            except 模型错误:
                pass


def _文本消息(内容):
    return {"类型标签": 101, "值": {
        "role": {"类型标签": 4, "值": "user"},
        "content": {"类型标签": 4, "值": 内容},
    }}


def 对话(消息, 系统提示词="", 温度=0.7, 最大令牌数=2048, 超时秒=180):
    """一句话对话。消息可以是字符串，也可以是多轮 [{"role":"user","content":"..."}] 列表。"""
    if isinstance(消息, str):
        消息列表 = [_文本消息(消息)]
    else:
        消息列表 = [{"类型标签": 101, "值": {键: {"类型标签": 4, "值": 值} for 键, 值 in 条.items()}}
                  for 条 in 消息]
    return _跑一次(文本模型, "LLM文本模型", 消息列表, 系统提示词, 温度, 最大令牌数, 超时秒)


def 看图(图片路径, 问题="描述这张图", 超时秒=180):
    """让视觉模型看一张本地图片。"""
    import base64
    数据 = base64.b64encode(open(图片路径, "rb").read()).decode()
    消息列表 = [{"类型标签": 101, "值": {
        "role": {"类型标签": 4, "值": "user"},
        "content": {"类型标签": 100, "值": [
            {"类型标签": 101, "值": {"type": {"类型标签": 4, "值": "text"},
                                    "text": {"类型标签": 4, "值": 问题}}},
            {"类型标签": 101, "值": {"type": {"类型标签": 4, "值": "image_url"},
                                    "image_url": {"类型标签": 101, "值": {
                                        "url": {"类型标签": 4, "值": "data:image/jpeg;base64," + 数据}}}}},
        ]},
    }}]
    return _跑一次(看图模型, "VLM看图模型", 消息列表, "", 0.2, 1024, 超时秒)


def 状态():
    """当前跑着哪些模型。"""
    return _解(_调(2507))


if __name__ == "__main__":
    import sys
    print(对话(sys.argv[1] if len(sys.argv) > 1 else "你好，用一句话介绍你自己"))
