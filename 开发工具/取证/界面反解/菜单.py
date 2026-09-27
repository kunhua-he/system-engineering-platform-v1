# -*- coding: utf-8 -*-
"""菜单 —— MENUHEADER + MENUITEMTEMPLATE 解码（原 `界面反解.py::解菜单`，纯搬家）。"""

import struct

from .形状 import 解析错误


def 解菜单(b, 资源id):
    if len(b) < 4:
        raise 解析错误("菜单 %s 短于 MENUHEADER" % 资源id)
    版本, 头大小 = struct.unpack_from("<HH", b, 0)
    if 版本 != 0 or 头大小 != 0:
        raise 解析错误("菜单 %s 版本=%d 头大小=%d：非标准 MENU 模板（MENUEX 未取证，不猜）"
                    % (资源id, 版本, 头大小))
    i, 深度, 项 = 4, 0, []
    while i < len(b):
        if i + 2 > len(b):
            raise 解析错误("菜单 %s 在 0x%x 处截断（读选项）" % (资源id, i))
        选 = struct.unpack_from("<H", b, i)[0]
        i += 2
        # 实测：本文件的 mtID 只在 MF_POPUP 项缺席（含 MF_END 项仍在）—— 见界面实测.md §二 2.2
        编号 = None
        if not (选 & 0x10):
            if i + 2 > len(b):
                raise 解析错误("菜单 %s 在 0x%x 处截断（读 mtID）" % (资源id, i))
            编号 = struct.unpack_from("<H", b, i)[0]
            i += 2
        起 = i
        while True:
            if i + 2 > len(b):
                raise 解析错误("菜单 %s 的文字没有 NUL 结尾（从 0x%x 起）" % (资源id, 起))
            if struct.unpack_from("<H", b, i)[0] == 0:
                i += 2
                break
            i += 2
        文字 = b[起:i - 2].decode("utf-16le")
        if any(ord(c) < 0x20 and c != "\t" for c in 文字):
            raise 解析错误("菜单 %s 的文字含控制字符（%r）：对齐判错" % (资源id, 文字[:12]))
        项.append({"层": 深度, "偏移": 起, "选项": 选, "编号": 编号, "文字": 文字})
        if 选 & 0x10:
            深度 += 1
        elif 选 & 0x80:
            深度 -= 1
            if 深度 < 0:
                raise 解析错误("菜单 %s 的 MF_END 下溢 @0x%x" % (资源id, i))
    if i != len(b):
        raise 解析错误("菜单 %s 消耗 %d != 声明 %d：模板边界不自洽" % (资源id, i, len(b)))
    if 深度 != 0:
        raise 解析错误("菜单 %s 结束时层深 %d != 0：MF_END 与 MF_POPUP 不配对" % (资源id, 深度))
    if not 项:
        raise 解析错误("菜单 %s 一项都没有" % 资源id)
    return 项
