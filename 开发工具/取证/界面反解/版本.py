# -*- coding: utf-8 -*-
"""版本 —— 类型 16 VS_VERSIONINFO 解码（原 `界面反解.py::解版本`，纯搬家）。"""

import struct

from .形状 import 解析错误


def 解版本(块字节, 资源id):
    out = []

    def 走(起, 止, 层):
        块起 = 起
        while 块起 + 6 <= 止:
            长, 值长, 型 = struct.unpack_from("<HHH", 块字节, 块起)
            if 长 == 0:
                break
            if 长 < 6 or 块起 + 长 > 止:
                raise 解析错误("版本资源 %s 的子块长度 %d 越界 @0x%x" % (资源id, 长, 块起))
            键末 = 块起 + 6
            while True:
                if 键末 + 2 > 块起 + 长:
                    raise 解析错误("版本资源 %s 的键没有 NUL 结尾 @0x%x" % (资源id, 块起))
                if struct.unpack_from("<H", 块字节, 键末)[0] == 0:
                    break
                键末 += 2
            键 = 块字节[块起 + 6:键末].decode("utf-16le")
            值起 = (键末 + 2 + 3) & ~3
            字节数 = 值长 * 2 if 型 == 1 else 值长
            if 值起 + 字节数 > 块起 + 长:
                raise 解析错误("版本资源 %s 的子块 %r 的值越界" % (资源id, 键))
            if 型 == 1:
                out.append((层, 键, 块字节[值起:值起 + 字节数].decode("utf-16le").rstrip("\0")))
            else:
                out.append((层, 键, "<%d 字节二进制> %s" % (值长, 块字节[值起:值起 + 字节数][:12].hex(" "))))
            走(值起 + 字节数, 块起 + 长, 层 + 1)     # 型 0 的根块也有子块（StringFileInfo/VarFileInfo）
            块起 = (块起 + 长 + 3) & ~3
    走(0, len(块字节), 0)
    if not out:
        raise 解析错误("版本资源 %s 没解出任何键" % 资源id)
    return out
