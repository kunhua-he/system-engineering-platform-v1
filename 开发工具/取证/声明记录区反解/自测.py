# -*- coding: utf-8 -*-
"""自测 —— 反向样本断言（判据可信性，零假绿）。"""

import os
import struct

from .公共 import (
    段类型_程序, 段体魔数, 头偏移_保留, 头偏移_补零, 头偏移_体长,
    头偏移_体魔数, 段数据头长度, 解析错误,
)
from .容器层 import 反解容器
from .段数据层 import 解段数据, 取声明记录区
from .记录层 import 走记录

# ── 自测：反向样本（判据可信性，零假绿）──────────────────────────────────────────

def 自测(样本="/tmp/易语言源码/lib/krnln/samples/第一个程序.e"):
    with open(样本, "rb") as fh:
        好 = fh.read()
    段 = 反解容器(好)
    段号, 段起, 段止, 头起 = [x for x in 段 if x[0] == 段类型_程序][0]
    r = 解段数据(好[段起:段止])
    区起 = r["声明记录区起点"]

    例 = [
        ("空文件", b""),
        ("只有魔数 8 字节", 好[:8]),
        ("段头截断到 20 字节", 好[:8 + 20]),
        ("截断到程序段数据中间", 好[:段起 + 100]),
        ("随机字节流", bytes(range(256)) * 8),
        ("魔数改坏", b"ZZ" + 好[2:]),
    ]
    # 段头级
    b = bytearray(好); b[8:10] = b"\x00\x00"
    例.append(("段头魔术甲改坏", bytes(b)))
    b = bytearray(好); b[10:12] = b"\x00\x00"
    例.append(("段头魔术乙改坏", bytes(b)))
    b = bytearray(好); b[8 + 11] = 0x99
    例.append(("段类型号越界 0x99", bytes(b)))
    b = bytearray(好); b[8 + 0x2A] = 0x03
    例.append(("段头尾标志改成 0x03（仅类型255合法）", bytes(b)))
    # 段数据级（段数据起 = 段起）
    b = bytearray(好); b[段起 + 头偏移_保留:段起 + 头偏移_保留 + 4] = (1).to_bytes(4, "little")
    例.append(("段数据头保留改成 1", bytes(b)))
    b = bytearray(好); b[段起 + 头偏移_补零 + 5] = 0x7F
    例.append(("段数据头补零区塞非零", bytes(b)))
    b = bytearray(好); b[段起 + 头偏移_体长:段起 + 头偏移_体长 + 4] = (r["体长"] + 1).to_bytes(4, "little")
    例.append(("体长字段 +1", bytes(b)))
    b = bytearray(好); b[段起 + 头偏移_体魔数:段起 + 头偏移_体魔数 + 4] = (段体魔数 ^ 1).to_bytes(4, "little")
    例.append(("段体魔数改坏", bytes(b)))
    # 支持库表级
    甲前缀位 = 段起 + 段数据头长度 + 8
    声明数位 = 甲前缀位 + 4 + 4 * len(r["数组甲"]) + 4 + 2 * len(r["数组乙"]) + 4 + 2 * len(r["数组丙"])
    b = bytearray(好); b[甲前缀位:甲前缀位 + 4] = (6).to_bytes(4, "little")
    例.append(("数组甲长度前缀改成 6（非 4 倍数）", bytes(b)))
    b = bytearray(好); b[甲前缀位:甲前缀位 + 4] = (0x00FFFFFC).to_bytes(4, "little")
    例.append(("数组甲长度前缀改成 0x00FFFFFC（越界）", bytes(b)))
    b = bytearray(好); b[声明数位:声明数位 + 2] = (0).to_bytes(2, "little")
    例.append(("支持库数 u16 改成 0（数组仍 1）", bytes(b)))
    引用位 = 声明数位 + 2
    b = bytearray(好); b[引用位:引用位 + 4] = (0x00FFFFFF).to_bytes(4, "little")
    例.append(("第一条引用串长改成 0x00FFFFFF（越界）", bytes(b)))
    # 声明记录区级：整区截断（把段数据尾部砍掉，体长随之不符）
    b = bytearray(好); del b[段止 - 40:段止]
    例.append(("声明记录区被砍 40 字节", bytes(b)))
    # 声明记录区全零（空程序）—— 这是**合法**输入，必须成功
    好零 = bytearray(好)
    好零[段起 + 区起:段止] = b"\x00" * (段止 - 段起 - 区起)
    合法例 = [("声明记录区整区清 0（空程序）", bytes(好零))]

    print("自测：喂 %d 个坏样本 + %d 个合法边界样本" % (len(例), len(合法例)))
    print("判据：坏样本**不许产出声明记录区**（报错 或 零条程序段）；合法样本必须过。")
    报错数 = 未产出数 = 假绿 = 失败 = 0
    for 名, 数据 in 例:
        try:
            区表 = 取声明记录区(数据)
        except 解析错误 as ex:
            print("  ✓ %-36s 报错：%s" % (名, ex))
            报错数 += 1
            continue
        except (struct.error, IndexError, ValueError, OverflowError, TypeError) as ex:
            print("  ✗ %-36s 抛了非解析错误（%s: %s）" % (名, type(ex).__name__, ex))
            失败 += 1
            continue
        if not 区表:
            print("  ✓ %-36s 未产出（0 条程序段 ⇒ 无声明记录区）" % 名)
            未产出数 += 1
        else:
            print("  ✗ %-36s 竟产出 %d 条声明记录区 —— 假绿" % (名, len(区表)))
            假绿 += 1
            失败 += 1
    for 名, 数据 in 合法例:
        try:
            区表 = 取声明记录区(数据)
            assert 区表 and len(区表[0][3]) > 0
            print("  ✓ %-36s 通过（区 %d 字节，头 4 字节 %s）"
                  % (名, len(区表[0][3]), 区表[0][3][:4].hex(" ")))
        except Exception as ex:
            print("  ✗ %-36s 合法样本反而失败：%s" % (名, ex))
            失败 += 1
    try:
        区表 = 取声明记录区(好)
        记录, 未解 = 走记录(区表[0][3])
        print("  ✓ 正向样本 %s：程序段 %d 个，声明记录区 %d 字节，可证记录 %d 条（未解 %d 字节）"
              % (os.path.basename(样本), len(区表), len(区表[0][3]), len(记录), 未解))
    except 解析错误 as ex:
        print("  ✗ 正向样本反而失败：%s" % ex)
        失败 += 1
    if 报错数 < 8:
        print("  ✗ 真正报错的坏样本只有 %d 个（要求 ≥ 8）" % 报错数)
        失败 += 1
    print("自测读数：坏样本 %d（报错 %d · 未产出 %d · 假绿 %d）· 失败合计 %d"
          % (len(例), 报错数, 未产出数, 假绿, 失败))
    print("自测结论：%s" % ("通过" if 失败 == 0 else "不通过"))
    return 1 if 失败 else 0
