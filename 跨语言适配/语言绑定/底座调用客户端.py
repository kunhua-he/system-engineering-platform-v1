# -*- coding: utf-8 -*-
"""底座官方 Python 绑定：唯一的对外调用口是网关 HTTP 的 /接口/调用。

三件事由底座定，调用方不必知道：网关在哪、能力叫什么、参数该长什么样。

- **地址**：读底座自身的常量表（`契约声明/常量表.json` 的 `接口端口`，全平台常量的唯一定义处），
  可用环境变量 `V1_GATEWAY_PORT` 覆盖（与命令行界面同读这一个名）。
- **能力名**：可以给编号，也可以给名字（`渲染组件树` / `操作组件` / `解析XLSX`）。
  名字从网关 `/接口` 的能力清单拉一次并记住；重名的能力不给用名字，逼着写编号。
- **参数**：给裸值，类型标签由底座按形状推断；字段名就是契约里的名字。

底座本体是 Rust 编译的 cdylib，Python 不能 import 它；能 import 的是这一份官方绑定。
全项目只此一份，业务项目与演示都复用它，不各写一遍。
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

底座根目录 = Path(__file__).resolve().parents[2]
常量表位置 = 底座根目录 / "契约声明" / "常量表.json"
端口环境变量 = "V1_GATEWAY_PORT"
回环地址 = "127.0.0.1"
兜底端口 = 43110
调用入口路径 = "/接口/调用"
能力清单路径 = "/接口"

_网关地址缓存 = None
_能力名册缓存 = None


class 底座调用失败(RuntimeError):
    """底座明确失败，或连接 / 协议层不通。"""

    def __init__(对象自身, 说明文本, 失败编号=None):
        super().__init__(说明文本)
        对象自身.失败编号 = 失败编号


def 读取接口端口():
    """端口唯一来源是底座的常量表；环境变量可覆盖（部署侧改一处即可）。"""
    环境端口 = os.environ.get(端口环境变量)
    if 环境端口:
        return int(环境端口)
    try:
        常量条目表 = json.loads(常量表位置.read_text(encoding="utf-8")).get("常量") or []
    except (OSError, json.JSONDecodeError):
        return 兜底端口
    for 常量条目 in 常量条目表:
        if 常量条目.get("名") == "接口端口" and isinstance(常量条目.get("值"), int):
            return 常量条目["值"]
    return 兜底端口


def 解析网关地址():
    """网关地址由底座自身说，只在进程内算一次。"""
    global _网关地址缓存
    if _网关地址缓存 is None:
        _网关地址缓存 = f"http://{回环地址}:{读取接口端口()}"
    return _网关地址缓存


def 请求底座接口(接口路径, 请求正文=None, *, 网关地址=None, 等待秒数=30):
    """GET 取契约 / 清单，POST 调能力，回 JSON 对象；非 200 或连不上一律抛。"""
    完整地址 = (网关地址 or 解析网关地址()) + urllib.parse.quote(接口路径, safe="/")
    请求数据 = None
    if 请求正文 is not None:
        请求数据 = json.dumps(请求正文, ensure_ascii=False).encode("utf-8")
    请求对象 = urllib.request.Request(
        完整地址,
        data=请求数据,
        method="POST" if 请求数据 is not None else "GET",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(请求对象, timeout=等待秒数) as 响应对象:
            响应正文 = 响应对象.read().decode("utf-8")
    except urllib.error.HTTPError as 接口异常:
        错误正文 = 接口异常.read().decode("utf-8", "replace")
        raise 底座调用失败(
            f"底座接口 HTTP {接口异常.code}：{错误正文}", 接口异常.code
        ) from 接口异常
    except urllib.error.URLError as 连接异常:
        raise 底座调用失败(f"底座连不上：{连接异常.reason}") from 连接异常
    try:
        return json.loads(响应正文)
    except json.JSONDecodeError as 解析异常:
        raise 底座调用失败("底座未返回合法 JSON") from 解析异常


def 能力名册():
    """名字 → 编号；重名的能力从名册里剔掉，逼调用方写编号。只拉一次。"""
    global _能力名册缓存
    if _能力名册缓存 is None:
        名册 = {}
        重名集 = set()
        for 能力条目 in 请求底座接口(能力清单路径).get("能力") or []:
            能力名 = 能力条目.get("名称")
            能力号 = 能力条目.get("编号")
            if 能力名 in 名册:
                重名集.add(能力名)
            名册[能力名] = 能力号
        for 重名 in 重名集:
            名册.pop(重名, None)
        _能力名册缓存 = 名册
    return _能力名册缓存


def 解析能力编号(能力):
    """给编号就原样用；给名字查名册。两样都不成，直接报错不猜。"""
    if isinstance(能力, int):
        return 能力
    名册 = 能力名册()
    if 能力 not in 名册:
        raise 底座调用失败(f"能力名不可用（不存在或重名）：{能力}，请改用能力编号")
    return 名册[能力]


def 调用能力(能力, 命名参数表=None, *, 网关地址=None):
    """调一条能力，回解包后的值。能力可给编号或名字，参数给裸值。"""
    回执报文 = 请求底座接口(
        调用入口路径,
        {"编号": 解析能力编号(能力), "命名值": 命名参数表 or {}},
        网关地址=网关地址,
    )
    if 回执报文.get("成功") is not True:
        错误对象 = 回执报文.get("错误") or {}
        raise 底座调用失败(
            f"底座业务失败：码 {错误对象.get('码')} · {错误对象.get('名称')}",
            错误对象.get("码"),
        )
    返回数据 = 回执报文.get("值")
    if isinstance(返回数据, list) and 返回数据:
        返回数据 = 返回数据[0].get("值")  # 回执是「带类型标签的值列表」，剥一层
    if isinstance(返回数据, str):
        try:
            return json.loads(返回数据)  # 文本里是 JSON 就顺手解析
        except json.JSONDecodeError:
            return 返回数据
    return 返回数据
