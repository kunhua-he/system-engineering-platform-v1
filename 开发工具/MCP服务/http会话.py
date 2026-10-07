# -*- coding: utf-8 -*-
"""HTTP 会话表 —— Streamable HTTP 的可选会话：新建 / 核对续期 / 删除 / 闲置回收。

MCP Streamable HTTP 里会话 id 是**可选项**（服务端 MAY 在 initialize 响应头 `Mcp-Session-Id`
给出）。给了就得：后续请求带它、服务端能核对、客户端可 DELETE 终止、闲置可回收（释放资源）。
本件只管这张表（线程安全 · 有界 · 闲置即回收），不碰 HTTP 与业务。

依据：MCP 规格 Streamable HTTP「Session Management」一节。
"""
import secrets
import threading
import time

from .服务常量 import 会话闲置分钟, 会话数量上限


class 会话表:
    """线程安全的有界会话表：`{会话编号: 最后触碰时刻}`。闲置超时或超量即回收。"""

    def __init__(self, 闲置分钟数=会话闲置分钟, 数量上限值=会话数量上限):
        self._锁 = threading.Lock()
        self._字典 = {}
        self._闲置分钟数 = 闲置分钟数
        self._数量上限值 = 数量上限值

    def 新建(self):
        """登记一个新会话 ⇒ 会话编号（可见 ASCII · 密码学随机）。顺带回收过期的。"""
        会话编号 = secrets.token_urlsafe(24)
        当前时刻 = time.monotonic()
        with self._锁:
            self._回收(当前时刻)
            self._字典[会话编号] = 当前时刻
        return 会话编号

    def 触碰(self, 会话编号):
        """核对并续期：在 ⇒ 更新时刻回真；未知 / 已回收 ⇒ 回假。"""
        当前时刻 = time.monotonic()
        with self._锁:
            if 会话编号 not in self._字典:
                return False
            self._字典[会话编号] = 当前时刻
            return True

    def 删除(self, 会话编号):
        """显式终止（DELETE）：删到回真；本就不在回假。"""
        with self._锁:
            return self._字典.pop(会话编号, None) is not None

    def _回收(self, 当前时刻):
        """闲置超时的清掉；仍超量就按登记时刻从旧到新裁到上限。调用方须已持锁。"""
        for 过期编号 in [编号 for 编号, 登记时刻 in self._字典.items()
                     if 当前时刻 - 登记时刻 > self._闲置分钟数 * 60]:
            del self._字典[过期编号]
        超出数量 = len(self._字典) - self._数量上限值 + 1
        if 超出数量 > 0:
            for 过期编号, 登记时刻 in sorted(self._字典.items(),
                                    key=lambda 会话条目: 会话条目[1])[:超出数量]:
                del self._字典[过期编号]
