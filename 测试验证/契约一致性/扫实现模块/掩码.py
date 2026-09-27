# -*- coding: utf-8 -*-
"""掩码 —— 把注释与字符串/字符字面量换成等长空格（保偏移、保行号）。"""
from __future__ import annotations

import re

def _前面不是标识符(文本: str, 位: int) -> bool:
    if 位 == 0:
        return True
    c = 文本[位 - 1]
    return not (c.isalnum() or c == "_" or c == "：")


def 掩码(文本: str) -> str:
    """返回等长掩码串：注释 · 字符串 · 字符字面量都变空格（换行保留）。

    为什么必须掩：范围里的注释大量写着 `本表[能力号::…]` · `命令项(…)` ·
    `命令状态::错误` 这些**示例文本**；不掩就会把它们当成真实现抽出来（假绿）。
    """
    出 = list(文本)
    n = len(文本)
    i = 0

    def 抹(起, 止):
        for p in range(起, min(止, n)):
            if 出[p] != "\n":
                出[p] = " "

    while i < n:
        c = 文本[i]
        if c == "/" and i + 1 < n and 文本[i + 1] == "/":
            j = 文本.find("\n", i)
            抹(i, n if j < 0 else j)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and 文本[i + 1] == "*":
            深 = 1
            k = i + 2
            while k < n and 深:
                if 文本[k] == "/" and k + 1 < n and 文本[k + 1] == "*":
                    深 += 1
                    k += 2
                elif 文本[k] == "*" and k + 1 < n and 文本[k + 1] == "/":
                    深 -= 1
                    k += 2
                else:
                    k += 1
            抹(i, k)
            i = k
            continue
        m = re.match(r'(?:b|c)?r(#*)"', 文本[i:])
        if m and _前面不是标识符(文本, i):
            井 = m.group(1)
            起 = i + m.end()
            终 = 文本.find('"' + 井, 起)
            终 = n if 终 < 0 else 终 + len(井) + 1
            抹(i, 终)
            i = 终
            continue
        m = re.match(r'(?:b|c)?"', 文本[i:])
        if m and _前面不是标识符(文本, i):
            k = i + m.end()
            while k < n:
                if 文本[k] == "\\":
                    k += 2
                    continue
                if 文本[k] == '"':
                    k += 1
                    break
                if 文本[k] == "\n":
                    break
                k += 1
            抹(i, k)
            i = k
            continue
        if c == "'":
            m = re.match(r"'(?:\\.|[^\\'])'", 文本[i:])
            if m:
                抹(i, i + m.end())
                i += m.end()
                continue
        i += 1
    return "".join(出)
