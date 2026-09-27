# -*- coding: utf-8 -*-
"""菜单 —— MENUHEADER + MENUITEMTEMPLATE 解码（原 `界面反解.py::解菜单`，纯搬家）。"""

import struct

from PE形状 import 解析错误


def 解菜单(模板字节, 资源id):
    if len(模板字节) < 4:
        raise 解析错误("菜单 %s 短于 MENUHEADER" % 资源id)
    版本, 头大小 = struct.unpack_from("<HH", 模板字节, 0)
    if 版本 != 0 or 头大小 != 0:
        raise 解析错误("菜单 %s 版本=%d 头大小=%d：非标准 MENU 模板（MENUEX 未取证，不猜）"
                    % (资源id, 版本, 头大小))
    游标, 深度, 一项 = 4, 0, []
    while 游标 < len(模板字节):
        if 游标 + 2 > len(模板字节):
            raise 解析错误("菜单 %s 在 0x%x 处截断（读选项）" % (资源id, 游标))
        选中 = struct.unpack_from("<H", 模板字节, 游标)[0]
        游标 += 2
        # 实测：本文件的 mtID 只在 MF_POPUP 项缺席（含 MF_END 项仍在）—— 见界面实测.md §二 2.2
        编号 = None
        if not (选中 & 0x10):
            if 游标 + 2 > len(模板字节):
                raise 解析错误("菜单 %s 在 0x%x 处截断（读 mtID）" % (资源id, 游标))
            编号 = struct.unpack_from("<H", 模板字节, 游标)[0]
            游标 += 2
        区间起点 = 游标
        while True:
            if 游标 + 2 > len(模板字节):
                raise 解析错误("菜单 %s 的文字没有 NUL 结尾（从 0x%x 起）" % (资源id, 区间起点))
            if struct.unpack_from("<H", 模板字节, 游标)[0] == 0:
                游标 += 2
                break
            游标 += 2
        文字 = 模板字节[区间起点:游标 - 2].decode("utf-16le")
        if any(ord(字符) < 0x20 and 字符 != "\t" for 字符 in 文字):
            raise 解析错误("菜单 %s 的文字含控制字符（%r）：对齐判错" % (资源id, 文字[:12]))
        一项.append({"层": 深度, "偏移": 区间起点, "选项": 选中, "编号": 编号, "文字": 文字})
        if 选中 & 0x10:
            深度 += 1
        elif 选中 & 0x80:
            深度 -= 1
            if 深度 < 0:
                raise 解析错误("菜单 %s 的 MF_END 下溢 @0x%x" % (资源id, 游标))
    if 游标 != len(模板字节):
        raise 解析错误("菜单 %s 消耗 %d != 声明 %d：模板边界不自洽" % (资源id, 游标, len(模板字节)))
    if 深度 != 0:
        raise 解析错误("菜单 %s 结束时层深 %d != 0：MF_END 与 MF_POPUP 不配对" % (资源id, 深度))
    if not 一项:
        raise 解析错误("菜单 %s 一项都没有" % 资源id)
    return 一项
