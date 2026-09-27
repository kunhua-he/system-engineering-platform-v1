# -*- coding: utf-8 -*-
"""压缩 —— 容器识别 + 熵/签名压缩判定（原 `界面反解.py::容器识别/压缩判定`，纯搬家）。"""

import math
import struct
from collections import Counter

from .常量 import 压缩签名
from .形状 import 解析错误


def 容器识别(b):
    """先认容器再谈压缩：GIF/PNG/BMP/JPEG/ICONDIR 这类「已压缩内容」不是「被压缩的资源」。"""
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF 图像 %dx%d（%s）" % (struct.unpack_from("<H", b, 6)[0],
                                        struct.unpack_from("<H", b, 8)[0], b[:6].decode())
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG 图像"
    if b[:2] == b"BM":
        return "BMP 位图"
    if b[:3] == b"\xff\xd8\xff":
        return "JPEG 图像"
    if b[:2] == b"MZ":
        return "PE 映像（嵌套可执行）"
    if len(b) >= 6:
        保留, 型, 数 = struct.unpack_from("<HHH", b, 0)
        if 保留 == 0 and 型 in (1, 2) and 0 < 数 <= 64 and 6 + 16 * 数 <= len(b):
            return "ICONDIR（type=%d · %d 条）" % (型, 数)
    return None


def 压缩判定(b):
    if not b:
        raise 解析错误("空数据无法做压缩判定")
    n = len(b)
    熵 = -sum(v / n * math.log2(v / n) for v in Counter(b).values())
    容器 = 容器识别(b)
    头部 = [名 for 签, 名 in 压缩签名 if b.startswith(签)]
    中段 = [名 for 签, 名 in 压缩签名 if not b.startswith(签) and b.find(签) >= 0]
    if 头部:
        判定 = "已压缩（头部签名命中 %s）" % "/".join(头部)
    elif 容器:
        判定 = "未压缩（容器：%s；高熵来自容器内部编码）" % 容器
    elif 熵 < 7.0:
        判定 = "未压缩"
    else:
        判定 = "不判（熵 %.2f 高但无头部签名：不猜算法）" % 熵
    return {"熵": 熵, "容器": 容器, "中段命中": 中段, "头部命中": 头部, "判定": 判定}
