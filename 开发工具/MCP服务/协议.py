# -*- coding: utf-8 -*-
"""MCP 协议层 —— **stdio 上的 JSON-RPC 2.0**（一行一个 JSON，标准库手写，零第三方依赖）。

MCP 的 stdio 传输就是换行分隔的 JSON-RPC：不需要 SDK。本件只实现 MCP 服务端要的四件事 ——
`initialize` · `tools/list` · `tools/call` · `ping`，其余方法一律回「方法不存在」，
**不许静默成功**（静默成功 = 假绿）。

**两类「每轮注入」的字段**（改它们 = 改模型每轮看到的东西）：

  · `serverInfo.title` —— 中文显示名（`name` 必须 ASCII，见 `工具.py` 顶部那段）。
  · `instructions` —— 服务提示词。它是**逐轮固定**的 ⇒ 上游能命中缓存；
    但它**不占工具面那点额度**，所以「读文件用内置工具」这类口径写在这里，不塞进工具描述。
  · `tools/call` 结果的 `服务提示`（**仅当本帧用的是旧码**）—— **独立字段**，**不拼进 `content`**
    （拼进去会破坏 content 里的纯 JSON 信封 ⇒ 结构化解析当场坏）；同时给 `structuredContent`（对象形）。

依据：`项目文档/决策记录/2026-09-27_开工账本与四道闸.md`。
"""

import json
import os
import select
import sys

from . import 自愈预检
from .参数规范 import 结构化
from .服务指纹 import 算服务指纹, 过期提示行, 过期提示一次

协议版本 = "2024-11-05"
服务名 = "v1-devkit"
服务显示名 = "V1 开发工具"
服务版本 = "0.4.0"

# 初始化前方法集：客户端在 `initialize` 完成前就能发的方法（`initialize` 本身 + 新版探测
# `server/discover`）。它们**豁免** HTTP 面的 `MCP-Protocol-Version` 门（初始化前客户端还
# 不知道服务端版本，拦它会把整条新客户端连接判死）；其余方法按官方规则拦不支持的版本头。
# 唯一读者 = `传输_http.py` 的版本门。
初始化前方法集 = ("initialize", "server/discover")

# 自愈重启的停等秒：空闲时每这么久醒一次比对服务指纹（阻塞 `readline` 察觉不到「空闲期改的件」）。
# 0.2 秒 = 「改完件后下一次调用」就落到新码上；一次比对约 0.7 毫秒 ⇒ 开销可忽略。
停等秒 = 0.2
_提示指纹 = None

服务提示词 = """本仓（系统工程平台V1） 开发所使用提效的开发工具。
在你做任意事情之前，先看看 mcp 的工具是否能使用。
当前有哪些工具、每个工具有哪些操作 —— 一律用 tools/list 与「操作留空」的只读发现调用现看，别记旧清单。
每个工具同形三字段：开工ID（可选，给了就在该开工的工作树里操作）· 操作（操作名，留空=返回操作目录）· 参数（具名参数对象）。
读文件用内置的 Read 与 Grep（它们不受限制）；查符号建议用 v1_symbol —— 它分得清定义与引用，Read 只是文本。
改文件只能走 v1_edit（Edit / Write 会被钩子拦）。
独立只读调用可同消息并发提交（如十个查询）；服务可能串行处理，不保证同时运行。
先开工后写、同件写、释放与合并按依赖顺序执行；v1_edit 改动表可一批多件。
提交放行仍须全量闸0、判据自测与案例。"""


def _写响应报文(输出, 报文号, 查询读数=None, 错误=None):
    """写一条响应。`错误` 非空 ⇒ JSON-RPC 错误对象（协议级失败，不是工具失败）。"""
    响应报文 = {"jsonrpc": "2.0", "id": 报文号}
    if 错误 is not None:
        响应报文["error"] = 错误
    else:
        响应报文["result"] = 查询读数
    输出.write(json.dumps(响应报文, ensure_ascii=False) + "\n")
    输出.flush()


def _过期行(传输):
    """本帧所用的「服务代码过期」提示行（空串 = 不过期）。

    stdio 面：自愈预检被拒的事实 + 过期提示（服务随即自愈重启，`跑主循环` 拿它当闸）；
    HTTP 面：报告等待空闲安全点；失败事实由传输服务对象追加。
    """
    global _提示指纹
    if 传输 == "http":
        return ""
    过期行 = 自愈预检.拒绝提示行() or 过期提示行()
    当前指纹 = 算服务指纹()
    if not 过期行 or _提示指纹 == (传输, 当前指纹):
        return ""
    _提示指纹 = (传输, 当前指纹)
    return 过期行


def 派发(协议方法, 命令行参数, 仓根, 工具表, 传输="stdio"):
    """把一个请求派到 MCP 的四个方法上 ⇒ `(结果, 错误)`。

    `传输` 只分流**服务代码过期**那一行的措辞（见 `_过期行`）—— 业务派发两种传输**逐字共用**
    同一份工具表 / 同一份统一信封，不因换传输而绕授权。
    """
    if 协议方法 == "initialize":
        # MCP 口径：回**服务端支持**的版本 —— 不原样回显客户端请求的版本（原样回显 = 声称支持所有版本）。
        return {
            "protocolVersion": 协议版本,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": 服务名, "title": 服务显示名, "version": 服务版本},
            "instructions": 服务提示词,
        }, None
    if 协议方法 == "ping":
        return {}, None
    if 协议方法 == "tools/list":
        # 工具表每条 = `(实现, 标题, 说明, 模式)` —— 标题是**中文显示名**，说明是给模型的原文。
        return {"tools": [
            {"name": 名称, "title": 标题, "description": 说明, "inputSchema": 模式}
            for 名称, (_实现, 标题, 说明, 模式) in 工具表.items()
        ]}, None
    if 协议方法 == "tools/call":
        名称 = 命令行参数.get("name")
        if 名称 not in 工具表:
            return None, {"code": -32602, "message": "没有这个工具：%r" % (名称,)}
        实参 = 命令行参数.get("arguments")
        if 实参 is None:
            实参 = {}
        if not isinstance(实参, dict):
            return None, {"code": -32602,
                          "message": "arguments 必须是对象，收到：%s" % type(实参).__name__}
        实现 = 工具表[名称][0]
        操作名 = str(实参.get("操作") or "")
        开工号 = str(实参.get("开工ID") or "")
        try:
            退出码, 输出文本 = 实现(实参, 仓根)
        except Exception as 异常:
            from .诊断记录 import 记诊断, 取定位
            记诊断(名称, 操作名, 开工号, type(异常).__name__, 定位=取定位(异常))
            raise
        结果值 = {"content": [{"type": "text", "text": 输出文本}], "isError": 退出码 != 0}
        过期行 = _过期行(传输)
        if 过期行 and 名称 != "v1_context":
            结果值["服务提示"] = [过期行]
        # ★ 底层回执是 JSON 信封 ⇒ 另给 `structuredContent`（官方字段，对象形）——
        #   调用方直接拿对象，不必「先剥文本再解字符串」两层解码。
        内层读数 = 结构化(输出文本)
        if 内层读数 is not None:
            结果值["structuredContent"] = 内层读数
        return 结果值, None
    return None, {"code": -32601, "message": "方法不存在：%r" % (协议方法,)}


def _重启参数():
    """自愈重启的 argv：**原样重放本进程的启动参数**（含 `-B` / `-u` 等解释器标志）。

    为什么不用 `[sys.executable] + sys.argv`：那样会**丢掉启动时的解释器标志** —— 实测：客户端
    以 `python3 -B -u` 拉起服务，`-B` 一丢，`dont_write_bytecode` 翻假 ⇒ 自愈后每次 import
    都在仓里写 `__pycache__`（污染仓）。`sys.orig_argv`（Python ≥3.10）保真原样。它不可用时
    才退回旧口径（保命：宁可少几个标志，也不让服务起不来）。
    """
    参数表 = list(getattr(sys, "orig_argv", None) or [])
    if not 参数表:
        参数表 = [sys.executable] + sys.argv
    return 参数表


def 跑主循环(仓根, 工具表, 输入流=None, 输出=None):
    """跑 stdio 主循环（**永不返回** —— 它是「结构边界：永不返回」，见 入口白名单.json）。

    ★ 自愈重启（2026-10-05）：每轮回「读下一帧之前」比对服务指纹，过期就 `os.execv` 重放自身
    —— 同一对 stdio 管道，客户端察觉不到，改了 `MCP服务/**` 不必再重启 ZCode。三处必须：
      · **逐行读，且 exec 只在「手上没有已读入的字节」时发生**：真服务走 `os.read` + 自带的行缓冲
        —— `readline()` 会把后续帧**预读进 Python 缓冲**（实测：连写两帧，第二帧落在缓冲里），
        那样 exec 会丢帧、`select` 也看不见它而**挂住**；注入的内存流（测试 / `--自检`）走
        `readline()`。读到 EOF 照旧 `return 0`。
      · **绝不在「已读进请求、还没回响应」时 exec**：顺序是「回完 → 回到循环顶 → 检查 → exec」。
      · **空闲期与「帧刚到」两处都查**：空闲靠 `select` 停等唤醒；帧已到但**尚未读入**时再查一次
        —— 过期就 exec（帧留在管道里，新进程照读）⇒ 改完件后的**下一帧就是新码**。
    自愈只对**真服务**（真 stdio）生效：注入的内存流（测试 / `--自检`）不 exec；exec 失败兜住
    （`兜底`）⇒ 不再重试、继续用旧码，绝不让失败把进程带走。
    """
    输入流 = 输入流 or sys.stdin
    输出 = 输出 or sys.stdout
    可自愈 = 输入流 is sys.stdin
    兜底 = False
    缓冲 = b""
    while True:
        if 可自愈 and not 兜底 and not 缓冲:
            过期行 = 过期提示行()
            if 过期行:
                # ★ 有界预检：新码真起得来才 exec —— 起不来就留着旧码。坏代码 exec = 新进程
                #   import 即崩 = stdio 连接断 = 四个工具全消失（实测 pid 4487）。同一坏指纹只预检一次。
                当前指纹 = 算服务指纹()
                放行重启, 拒绝原因, 首记坏版 = 自愈预检.判定重启(当前指纹)
                if 首记坏版:
                    print(自愈预检.拒绝记录(拒绝原因), file=sys.stderr)
                    sys.stderr.flush()
                if 放行重启 and 算服务指纹() != 当前指纹:
                    continue               # 预检与 exec 之间又变了 ⇒ 回顶重判（不 exec）
                if 放行重启:
                    # 当前帧的响应已在回循环顶之前写完并 flush；再兜底 flush 一次，
                    # 保证「写成功回执」不被 exec 截断。
                    输出.flush()
                    sys.stderr.flush()
                    print("★ 服务代码已变且预检通过 ⇒ 自愈重启（同一 stdio 管道，下一帧即新码）",
                          file=sys.stderr)
                    sys.stderr.flush()
                    try:
                        os.execv(sys.executable, _重启参数())
                    except OSError as 错误:
                        print("★ 自愈重启失败：%s ⇒ 继续用旧码" % (错误,), file=sys.stderr)
                        sys.stderr.flush()
                        兜底 = True
                        continue           # 不再重试 ⇒ 回顶正常读帧（旧码）
            if not select.select([输入流], [], [], 停等秒)[0]:
                continue                   # 空闲超时 ⇒ 回顶再比一次指纹
            if 过期提示行() and not 自愈预检.拒绝提示行():
                continue                   # 帧已到但**未读**且可自愈 ⇒ 回顶 exec（帧留在管道，不丢）
        if 可自愈:
            while b"\n" not in 缓冲:
                字节 = os.read(输入流.fileno(), 65536)
                if not 字节:
                    if not 缓冲:
                        return 0           # EOF
                    源码行, 缓冲 = 缓冲.decode("utf-8"), b""
                    break                  # 末行无换行符，照旧当一帧
                缓冲 += 字节
            else:
                源码行, 缓冲 = 缓冲.split(b"\n", 1)
                源码行 = 源码行.decode("utf-8")
        else:
            源码行 = 输入流.readline()
            if 源码行 == "":
                return 0                   # EOF
        if not 源码行.strip():
            continue
        try:
            请求 = json.loads(源码行)
        except ValueError:
            continue                       # 解不了的帧直接丢（不编一个假响应）
        # ★ 边界帧必须回**结构化错误**，绝不抛出循环：MCP 是长驻进程，一帧畸形输入 = 进程死 =
        #   四个工具从模型侧全部消失，直到重启 ZCode。依据：库 `规则` 安全边界-1（fail-closed）。
        if not isinstance(请求, dict):
            _写响应报文(输出, None, None,
                      {"code": -32700,
                       "message": "请求必须是 JSON 对象，收到：%s" % type(请求).__name__})
            continue
        错误码 = 请求.get("id")
        if 错误码 is None:
            continue                       # 通知：不回应
        命令行参数 = 请求.get("params")
        if 命令行参数 is None:
            命令行参数 = {}
        if not isinstance(命令行参数, dict):
            _写响应报文(输出, 错误码, None,
                      {"code": -32602, "message": "params 必须是对象，收到：%s" % type(命令行参数).__name__})
            continue
        try:
            查询读数, 错误 = 派发(请求.get("method"), 命令行参数, 仓根, 工具表)
        except Exception:                  # 实现层任何异常都不许抛出循环
            查询读数, 错误 = None, {"code": -32603, "message": "内部错误：%s" % (sys.exc_info()[1],)}
        _写响应报文(输出, 错误码, 查询读数, 错误)
    return 0
