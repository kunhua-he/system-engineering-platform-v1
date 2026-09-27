# -*- coding: utf-8 -*-
"""对话框 —— DLGTEMPLATE / DLGTEMPLATEEX 与逐控件解码（原 `界面反解.py`
`_变量数组`/`解对话框`/`类名`/`文字显示`，纯搬家）。"""

import struct

from .常量 import 预定义控件类
from .形状 import 解析错误


def _变量数组(b, i, 资源id, 字段):
    """菜单/类/标题三个变长数组共用：0x0000 空、0xFFFF+序数、或 UTF-16 串。"""
    if i + 2 > len(b):
        raise 解析错误("对话框 %s 的 %s 数组越界 @0x%x" % (资源id, 字段, i))
    w = struct.unpack_from("<H", b, i)[0]
    if w == 0:
        return None, i + 2, "空"
    if w == 0xFFFF:
        if i + 4 > len(b):
            raise 解析错误("对话框 %s 的 %s 序数越界 @0x%x" % (资源id, 字段, i))
        return struct.unpack_from("<H", b, i + 2)[0], i + 4, "序数"
    起 = i
    while True:
        if i + 2 > len(b):
            raise 解析错误("对话框 %s 的 %s 串没有 NUL 结尾（从 0x%x 起）" % (资源id, 字段, 起))
        if struct.unpack_from("<H", b, i)[0] == 0:
            break
        i += 2
    return b[起:i].decode("utf-16le"), i + 2, "串"


def 解对话框(b, 资源id):
    if len(b) < 18:
        raise 解析错误("对话框 %s 短于 DLGTEMPLATE" % 资源id)
    扩展 = struct.unpack_from("<I", b, 0)[0] == 0xFFFF0001
    if 扩展:
        if len(b) < 26:
            raise 解析错误("对话框 %s 声明 DLGTEMPLATEEX 但短于 26 字节" % 资源id)
        _, 签名, 帮助id, 扩展样式, 样式, 控件数, x, y, cx, cy = struct.unpack_from("<HHIIIHhhhh", b, 0)
        if 签名 != 0xFFFF:
            raise 解析错误("对话框 %s 的 DLGTEMPLATEEX 签名 0x%x != 0xFFFF" % (资源id, 签名))
        i = 26
    else:
        样式, 扩展样式, 控件数, x, y, cx, cy = struct.unpack_from("<IIHhhhh", b, 0)
        帮助id = None
        i = 18
    菜单, i, _ = _变量数组(b, i, 资源id, "菜单")
    类, i, _ = _变量数组(b, i, 资源id, "类")
    标题, i, 标题形 = _变量数组(b, i, 资源id, "标题")
    字体 = None
    if 样式 & 0x40:
        if 扩展:
            if i + 6 > len(b):
                raise 解析错误("对话框 %s 的字体块越界" % 资源id)
            号, 粗细, 斜, 字符集 = struct.unpack_from("<HHBB", b, i)
            i += 6
            名, i, _ = _变量数组(b, i, 资源id, "字体名")
            字体 = {"号": 号, "粗细": 粗细, "斜体": 斜, "字符集": 字符集, "名": 名}
        else:
            if i + 2 > len(b):
                raise 解析错误("对话框 %s 的字号越界" % 资源id)
            号 = struct.unpack_from("<H", b, i)[0]
            i += 2
            名, i, _ = _变量数组(b, i, 资源id, "字体名")
            字体 = {"号": 号, "名": 名}
    控件 = []
    for n in range(控件数):
        i = (i + 3) & ~3
        if 扩展:
            if i + 24 > len(b):
                raise 解析错误("对话框 %s 第 %d 个控件头越界 @0x%x" % (资源id, n, i))
            头 = struct.unpack_from("<IIIhhhhI", b, i)
            帮助id2, 扩样, 样, x2, y2, cx2, cy2, id2 = 头
            i += 24
        else:
            if i + 18 > len(b):
                raise 解析错误("对话框 %s 第 %d 个控件头越界 @0x%x" % (资源id, n, i))
            样, 扩样, x2, y2, cx2, cy2, id2 = struct.unpack_from("<IIhhhhH", b, i)
            帮助id2 = None
            i += 18
        类2, i, 类形 = _变量数组(b, i, 资源id, "控件类")
        题2, i, 题形 = _变量数组(b, i, 资源id, "控件标题")
        if i + 2 > len(b):
            raise 解析错误("对话框 %s 第 %d 个控件的附加数据长度越界" % (资源id, n))
        附加 = struct.unpack_from("<H", b, i)[0]
        i += 2
        if i + 附加 > len(b):
            raise 解析错误("对话框 %s 第 %d 个控件的附加数据越界（%d 字节）" % (资源id, n, 附加))
        i += 附加
        if 附加 % 2:
            i += 1
        控件.append({"样式": 样, "扩展样式": 扩样, "帮助id": 帮助id2, "x": x2, "y": y2, "cx": cx2,
                     "cy": cy2, "id": id2, "类": 类2, "类形": 类形, "标题": 题2, "标题形": 题形,
                     "附加": 附加, "偏移": i})
    if i != len(b):
        raise 解析错误("对话框 %s 消耗 %d != 声明 %d：模板边界不自洽" % (资源id, i, len(b)))
    return {"扩展": 扩展, "帮助id": 帮助id, "样式": 样式, "扩展样式": 扩展样式, "控件数": 控件数,
            "x": x, "y": y, "cx": cx, "cy": cy, "菜单": 菜单, "类": 类, "标题": 标题,
            "标题形": 标题形, "字体": 字体, "控件": 控件}


def 类名(值, 形):
    if 形 == "空":
        return "（空）"
    if 形 == "序数":
        return "预定义#%d=%s" % (值, 预定义控件类.get(值, "未登记"))
    return str(值)


def 文字显示(值, 形):
    if 形 == "空":
        return ""
    if 形 == "序数":
        return "#%d（资源序数）" % 值
    return 值
