# -*- coding: utf-8 -*-
"""压缩 —— 容器识别 + 熵/签名压缩判定（原 `界面反解.py::容器识别/压缩判定`，纯搬家）。"""

import math
import struct
from collections import Counter

from .格式名称表 import 压缩签名
from PE形状 import 解析错误


def 容器识别(数据字节):
    """先认容器再谈压缩：GIF/PNG/BMP/JPEG/ICONDIR 这类「已压缩内容」不是「被压缩的资源」。"""
    if 数据字节[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF 图像 %dx%d（%s）" % (struct.unpack_from("<H", 数据字节, 6)[0],
                                        struct.unpack_from("<H", 数据字节, 8)[0], 数据字节[:6].decode())
    if 数据字节[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG 图像"
    if 数据字节[:2] == b"BM":
        return "BMP 位图"
    if 数据字节[:3] == b"\xff\xd8\xff":
        return "JPEG 图像"
    if 数据字节[:2] == b"MZ":
        return "PE 映像（嵌套可执行）"
    if len(数据字节) >= 6:
        保留, 类型, 条目个数 = struct.unpack_from("<HHH", 数据字节, 0)
        if 保留 == 0 and 类型 in (1, 2) and 0 < 条目个数 <= 64 and 6 + 16 * 条目个数 <= len(数据字节):
            return "ICONDIR（type=%d · %d 条）" % (类型, 条目个数)
    return None


def 压缩判定(数据字节):
    if not 数据字节:
        raise 解析错误("空数据无法做压缩判定")
    全长 = len(数据字节)
    熵值 = -sum(频次 / 全长 * math.log2(频次 / 全长) for 频次 in Counter(数据字节).values())
    容器 = 容器识别(数据字节)
    头部 = [名称 for 签名, 名称 in 压缩签名 if 数据字节.startswith(签名)]
    中段 = [名称 for 签名, 名称 in 压缩签名 if not 数据字节.startswith(签名) and 数据字节.find(签名) >= 0]
    if 头部:
        判定 = "已压缩（头部签名命中 %s）" % "/".join(头部)
    elif 容器:
        判定 = "未压缩（容器：%s；高熵来自容器内部编码）" % 容器
    elif 熵值 < 7.0:
        判定 = "未压缩"
    else:
        判定 = "不判（熵 %.2f 高但无头部签名：不猜算法）" % 熵值
    return {"熵": 熵值, "容器": 容器, "中段命中": 中段, "头部命中": 头部, "判定": 判定}
