"""命令 —— 四条子命令 · 命令表 · 命令行主流程与退出码。"""

import json
import sys
import urllib.error

from .常量 import 默认端口, 用法文本, 路径_声明, 路径_能力, 路径_根, 路径_调用
from .参数 import 取端口, 用法错误
from .显示 import 印应答, 印失败, 印调用成功
from .请求体 import 拼值
from .连接 import 发请求, 报连不上

# 本次真正用的端口（入口函数 里定下来）。**只为把报错话说准**：连不上时要说清是哪个端口连不上，
# 报默认值会指错方向（端口可能是 --端口 或环境变量给的）。
当前端口 = 默认端口


def 命令清单(端口: int, 显示: bool) -> int:
    状态, 应答体 = 发请求(端口, "GET", 路径_根, None, 显示)
    return 印应答(状态, 应答体)


def 命令契约(端口: int, 命令行参数: list, 显示: bool) -> int:
    if len(命令行参数) != 1:
        raise 用法错误("契约 要一个编号：契约 <编号>")
    状态, 应答体 = 发请求(端口, "GET", 路径_能力 + 命令行参数[0], None, 显示)
    return 印应答(状态, 应答体)


def 命令调用(端口: int, 命令行参数: list, 显示: bool) -> int:
    if len(命令行参数) < 1:
        raise 用法错误("调用 要一个编号：调用 <编号> <值…>")
    编号文, 值参数 = 命令行参数[0], 命令行参数[1:]
    编号 = int(编号文)  # 只做「是不是十进制数」的搬运，不查它存不存在（那是后端的判）
    应答体 = {"编号": 编号, "值": [拼值(值参数项) for 值参数项 in 值参数]}
    体文本 = json.dumps(应答体, ensure_ascii=False)
    状态, 造应答 = 发请求(端口, "POST", 路径_调用, 体文本, 显示)
    try:
        解析后 = json.loads(造应答)
    except ValueError:
        print("HTTP {} —— 应答不是合法 JSON，原样贴出：".format(状态))
        print(造应答)
        return 3
    if 解析后.get("成功") is True:
        return 印调用成功(状态, 解析后)
    return 印失败("HTTP {}".format(状态), 解析后)


def 命令声明(端口: int, 命令行参数: list, 显示: bool) -> int:
    if len(命令行参数) != 1:
        raise 用法错误("声明 要一个文件：声明 <文件>")
    # **原样转发**：不解析、不校验（面校验是后端的事，前端校验就是第二条腿）。
    with open(命令行参数[0], "rb") as 文件:
        体文本 = 文件.read().decode("utf-8")
    状态, 应答体 = 发请求(端口, "POST", 路径_声明, 体文本, 显示)
    return 印应答(状态, 应答体)


命令表 = {
    "清单": lambda 端口, 命令行参数, 显示: 命令清单(端口, 显示),
    "契约": 命令契约,
    "调用": 命令调用,
    "声明": 命令声明,
}


def 入口函数(命令行参数: list) -> int:
    global 当前端口
    命令行参数 = list(命令行参数)
    显示 = "--显示请求" in 命令行参数
    命令行参数 = [命令行参数项 for 命令行参数项 in 命令行参数 if 命令行参数项 != "--显示请求"]
    if not 命令行参数 or 命令行参数[0] in ("--帮助", "-h", "--help", "帮助"):
        print(用法文本, end="")
        return 0
    命令 = 命令行参数[0]
    if 命令 not in 命令表:
        raise 用法错误("不认识这条命令：{}（只认 清单 / 契约 / 调用 / 声明）".format(命令))
    端口, 剩余参数 = 取端口(命令行参数[1:])
    当前端口 = 端口
    return 命令表[命令](端口, 剩余参数, 显示)


def 跑命令行(命令行参数: list) -> None:
    """命令行主流程 —— 与拆分前入口的 `__main__` 块逐字同义（含退出码）。"""
    try:
        sys.exit(入口函数(命令行参数))
    except 用法错误 as 错误:
        print("用法错误：{}".format(错误), file=sys.stderr)
        print("（本地参数写错，不是后端的判断）", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as 错误:
        print("文件读不到：{}".format(错误), file=sys.stderr)
        sys.exit(2)
    except urllib.error.URLError as 错误:
        # 报的是**本次真正用的那个端口**（可能是 --端口 或环境变量给的），不报默认值。
        sys.exit(报连不上(当前端口, 错误.reason if hasattr(错误, "reason") else 错误))
    except ValueError as 错误:
        print("用法错误：{}（编号与端口必须是十进制数）".format(错误), file=sys.stderr)
        sys.exit(2)
