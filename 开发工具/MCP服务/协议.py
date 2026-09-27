# -*- coding: utf-8 -*-
"""MCP 协议层 —— **stdio 上的 JSON-RPC 2.0**（一行一个 JSON，标准库手写，零第三方依赖）。

MCP 的 stdio 传输就是换行分隔的 JSON-RPC：不需要 SDK。本件只实现 MCP 服务端要的四件事 ——
`initialize` · `tools/list` · `tools/call` · `ping`，其余方法一律回「方法不存在」，
**不许静默成功**（静默成功 = 假绿）。

**服务级两处字段是「每轮注入」的**（改它们 = 改模型每轮看到的东西）：

  · `serverInfo.title` —— 中文显示名（`name` 必须 ASCII，见 `工具.py` 顶部那段）。
  · `instructions` —— 服务提示词。它是**逐轮固定**的 ⇒ 上游能命中缓存；
    但它**不占工具面那点额度**，所以「读文件用内置工具」这类口径写在这里，不塞进工具描述。

依据：`项目文档/决策记录/2026-09-27_开工账本与四道闸.md`。
"""

import json
import sys

协议版本 = "2024-11-05"
服务名 = "v1-devkit"
服务显示名 = "V1 开发工具"
服务版本 = "0.2.0"

服务提示词 = """本仓（系统工程平台V1） 开发所使用提效的开发工具。
在你做任意事情之前，先看看 mcp 的工具是否能使用。
当前有4 个工具。
1. v1_task：开始工作，需运行这个获取开工ID；用于记录工作内容以及方便后续查询记录。
2. v1_symbol：代码地图，可以搜索本仓的代码，加快探索时间。
3. v1_edit：代码修改器，目的是能稳固快速修改代码，可单独或批量修改文件。
4. v1_gate：一键门禁，当你全部任务结束后，可以运行这个看看是否有报错

读文件用内置的 Read 与 Grep（它们不受限制）；查符号建议用 v1_symbol —— 它分得清定义与引用，Read 只是文本。
改文件只能走 v1_edit（Edit / Write 会被钩子拦）。"""


def _回(输出, 码, 结果=None, 错=None):
    """写一条响应。`错` 非空 ⇒ JSON-RPC 错误对象（协议级失败，不是工具失败）。"""
    信 = {"jsonrpc": "2.0", "id": 码}
    if 错 is not None:
        信["error"] = 错
    else:
        信["result"] = 结果
    输出.write(json.dumps(信, ensure_ascii=False) + "\n")
    输出.flush()


def 派(方法, 参数, 仓根, 工具表):
    """把一个请求派到 MCP 的四个方法上 ⇒ `(结果, 错误)`。"""
    if 方法 == "initialize":
        求 = 参数.get("protocolVersion")
        return {
            "protocolVersion": 求 or 协议版本,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": 服务名, "title": 服务显示名, "version": 服务版本},
            "instructions": 服务提示词,
        }, None
    if 方法 == "ping":
        return {}, None
    if 方法 == "tools/list":
        # 工具表每条 = `(实现, 标题, 说明, 模式)` —— 标题是**中文显示名**，说明是给模型的原文。
        return {"tools": [
            {"name": 名, "title": 标题, "description": 说明, "inputSchema": 模式}
            for 名, (_实现, 标题, 说明, 模式) in 工具表.items()
        ]}, None
    if 方法 == "tools/call":
        名 = 参数.get("name")
        if 名 not in 工具表:
            return None, {"code": -32602, "message": "没有这个工具：%r" % (名,)}
        实现 = 工具表[名][0]
        码, 出 = 实现(参数.get("arguments") or {}, 仓根)
        return {"content": [{"type": "text", "text": 出}], "isError": 码 != 0}, None
    return None, {"code": -32601, "message": "方法不存在：%r" % (方法,)}


def 服务(仓根, 工具表, 输入=None, 输出=None):
    """跑 stdio 主循环（**永不返回** —— 它是「结构边界：永不返回」，见 入口白名单.json）。"""
    输入 = 输入 or sys.stdin
    输出 = 输出 or sys.stdout
    for 行 in 输入:
        if not 行.strip():
            continue
        try:
            请求 = json.loads(行)
        except ValueError:
            continue                       # 解不了的帧直接丢（不编一个假响应）
        码 = 请求.get("id")
        if 码 is None:
            continue                       # 通知：不回应
        结果, 错 = 派(请求.get("method"), 请求.get("params") or {}, 仓根, 工具表)
        _回(输出, 码, 结果, 错)
    return 0
