# -*- coding: utf-8 -*-
"""版本 —— 类型 16 VS_VERSIONINFO 解码（原 `界面反解.py::解版本`，纯搬家）。"""

import struct

from .形状 import 解析错误


def 解版本(b, 资源id):
    out = []

    def 走(起, 止, 层):
        o = 起
        while o + 6 <= 止:
            长, 值长, 型 = struct.unpack_from("<HHH", b, o)
            if 长 == 0:
                break
            if 长 < 6 or o + 长 > 止:
                raise 解析错误("版本资源 %s 的子块长度 %d 越界 @0x%x" % (资源id, 长, o))
            k = o + 6
            while True:
                if k + 2 > o + 长:
                    raise 解析错误("版本资源 %s 的键没有 NUL 结尾 @0x%x" % (资源id, o))
                if struct.unpack_from("<H", b, k)[0] == 0:
                    break
                k += 2
            键 = b[o + 6:k].decode("utf-16le")
            v = (k + 2 + 3) & ~3
            字节数 = 值长 * 2 if 型 == 1 else 值长
            if v + 字节数 > o + 长:
                raise 解析错误("版本资源 %s 的子块 %r 的值越界" % (资源id, 键))
            if 型 == 1:
                out.append((层, 键, b[v:v + 字节数].decode("utf-16le").rstrip("\0")))
            else:
                out.append((层, 键, "<%d 字节二进制> %s" % (值长, b[v:v + 字节数][:12].hex(" "))))
            走(v + 字节数, o + 长, 层 + 1)     # 型 0 的根块也有子块（StringFileInfo/VarFileInfo）
            o = (o + 长 + 3) & ~3
    走(0, len(b), 0)
    if not out:
        raise 解析错误("版本资源 %s 没解出任何键" % 资源id)
    return out
