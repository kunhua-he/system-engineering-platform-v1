# -*- coding: utf-8 -*-
"""对话框 —— DLGTEMPLATE / DLGTEMPLATEEX 与逐控件解码（原 `界面反解.py`
`_变量数组`/`解对话框`/`类名`/`文字显示`，纯搬家）。"""

import struct

from .常量 import 预定义控件类
from PE形状 import 解析错误


def _变量数组(模板字节, 游标, 资源id, 字段):
    """菜单/类/标题三个变长数组共用：0x0000 空、0xFFFF+序数、或 UTF-16 串。"""
    if 游标 + 2 > len(模板字节):
        raise 解析错误("对话框 %s 的 %s 数组越界 @0x%x" % (资源id, 字段, 游标))
    变量宽 = struct.unpack_from("<H", 模板字节, 游标)[0]
    if 变量宽 == 0:
        return None, 游标 + 2, "空"
    if 变量宽 == 0xFFFF:
        if 游标 + 4 > len(模板字节):
            raise 解析错误("对话框 %s 的 %s 序数越界 @0x%x" % (资源id, 字段, 游标))
        return struct.unpack_from("<H", 模板字节, 游标 + 2)[0], 游标 + 4, "序数"
    起 = 游标
    while True:
        if 游标 + 2 > len(模板字节):
            raise 解析错误("对话框 %s 的 %s 串没有 NUL 结尾（从 0x%x 起）" % (资源id, 字段, 起))
        if struct.unpack_from("<H", 模板字节, 游标)[0] == 0:
            break
        游标 += 2
    return 模板字节[起:游标].decode("utf-16le"), 游标 + 2, "串"


def 解对话框(模板字节, 资源id):
    if len(模板字节) < 18:
        raise 解析错误("对话框 %s 短于 DLGTEMPLATE" % 资源id)
    扩展 = struct.unpack_from("<I", 模板字节, 0)[0] == 0xFFFF0001
    if 扩展:
        if len(模板字节) < 26:
            raise 解析错误("对话框 %s 声明 DLGTEMPLATEEX 但短于 26 字节" % 资源id)
        _, 签名, 帮助id, 扩展样式, 样式, 控件数, 左, 顶, cx, cy = struct.unpack_from("<HHIIIHhhhh", 模板字节, 0)
        if 签名 != 0xFFFF:
            raise 解析错误("对话框 %s 的 DLGTEMPLATEEX 签名 0x%x != 0xFFFF" % (资源id, 签名))
        游标 = 26
    else:
        样式, 扩展样式, 控件数, 左, 顶, cx, cy = struct.unpack_from("<IIHhhhh", 模板字节, 0)
        帮助id = None
        游标 = 18
    菜单, 游标, _ = _变量数组(模板字节, 游标, 资源id, "菜单")
    类, 游标, _ = _变量数组(模板字节, 游标, 资源id, "类")
    标题, 游标, 标题形 = _变量数组(模板字节, 游标, 资源id, "标题")
    字体 = None
    if 样式 & 0x40:
        if 扩展:
            if 游标 + 6 > len(模板字节):
                raise 解析错误("对话框 %s 的字体块越界" % 资源id)
            号, 粗细, 斜, 字符集 = struct.unpack_from("<HHBB", 模板字节, 游标)
            游标 += 6
            名, 游标, _ = _变量数组(模板字节, 游标, 资源id, "字体名")
            字体 = {"号": 号, "粗细": 粗细, "斜体": 斜, "字符集": 字符集, "名": 名}
        else:
            if 游标 + 2 > len(模板字节):
                raise 解析错误("对话框 %s 的字号越界" % 资源id)
            号 = struct.unpack_from("<H", 模板字节, 游标)[0]
            游标 += 2
            名, 游标, _ = _变量数组(模板字节, 游标, 资源id, "字体名")
            字体 = {"号": 号, "名": 名}
    控件 = []
    for 控件序 in range(控件数):
        游标 = (游标 + 3) & ~3
        if 扩展:
            if 游标 + 24 > len(模板字节):
                raise 解析错误("对话框 %s 第 %d 个控件头越界 @0x%x" % (资源id, 控件序, 游标))
            头 = struct.unpack_from("<IIIhhhhI", 模板字节, 游标)
            帮助id2, 扩样, 样, x2, y2, cx2, cy2, id2 = 头
            游标 += 24
        else:
            if 游标 + 18 > len(模板字节):
                raise 解析错误("对话框 %s 第 %d 个控件头越界 @0x%x" % (资源id, 控件序, 游标))
            样, 扩样, x2, y2, cx2, cy2, id2 = struct.unpack_from("<IIhhhhH", 模板字节, 游标)
            帮助id2 = None
            游标 += 18
        类2, 游标, 类形 = _变量数组(模板字节, 游标, 资源id, "控件类")
        题2, 游标, 题形 = _变量数组(模板字节, 游标, 资源id, "控件标题")
        if 游标 + 2 > len(模板字节):
            raise 解析错误("对话框 %s 第 %d 个控件的附加数据长度越界" % (资源id, 控件序))
        附加 = struct.unpack_from("<H", 模板字节, 游标)[0]
        游标 += 2
        if 游标 + 附加 > len(模板字节):
            raise 解析错误("对话框 %s 第 %d 个控件的附加数据越界（%d 字节）" % (资源id, 控件序, 附加))
        游标 += 附加
        if 附加 % 2:
            游标 += 1
        控件.append({"样式": 样, "扩展样式": 扩样, "帮助id": 帮助id2, "x": x2, "y": y2, "cx": cx2,
                     "cy": cy2, "id": id2, "类": 类2, "类形": 类形, "标题": 题2, "标题形": 题形,
                     "附加": 附加, "偏移": 游标})
    if 游标 != len(模板字节):
        raise 解析错误("对话框 %s 消耗 %d != 声明 %d：模板边界不自洽" % (资源id, 游标, len(模板字节)))
    return {"扩展": 扩展, "帮助id": 帮助id, "样式": 样式, "扩展样式": 扩展样式, "控件数": 控件数,
            "x": 左, "y": 顶, "cx": cx, "cy": cy, "菜单": 菜单, "类": 类, "标题": 标题,
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
