# -*- coding: utf-8 -*-
"""自测 —— 反向样本断言，一个都不许「假绿」（原 `界面反解.py::自测`，纯搬家）。"""

import os
import struct

from .反解 import 反解界面, 反解数据
from PE形状 import PE, 解析错误
from .资源树 import 走资源树


def 跑自测(样本="/tmp/易语言源码/e.exe"):
    合格样本 = open(样本, "rb").read()
    坏样本表 = [("空文件", b""), ("只有 DOS 头 0x40", 合格样本[:0x40]), ("截断到 PE 头中间", 合格样本[:0x104]),
          ("无 MZ 签名", b"ZZ" + 合格样本[2:]), ("整份砍掉后半", 合格样本[:len(合格样本) // 2]),
          ("随机字节流", bytes(range(256)) * 8)]
    try:
        pe = PE(合格样本)
        pe.要资源目录()
        叶子 = 走资源树(pe)
        定位 = {}
        for 叶项 in 叶子:
            定位.setdefault((叶项["类型"], 叶项["id"]), 叶项)
        def 改一处(数据, 处, 待处理值):
            样本字节 = bytearray(数据)
            样本字节[处:处 + len(待处理值)] = 待处理值
            return bytes(样本字节)
        PE头偏移 = pe.PE头偏移
        坏样本表.append(("可选头长度改 0", 改一处(合格样本, PE头偏移 + 20, b"\0\0")))
        坏样本表.append(("节数改 0xFFFF", 改一处(合格样本, PE头偏移 + 6, b"\xff\xff")))
        坏样本表.append(("资源目录 RVA 指到文件外", 改一处(合格样本, PE头偏移 + 24 + 96 + 16, (0x700000).to_bytes(4, "little"))))
        坏样本表.append(("资源目录根项数改 0xFFFF", 改一处(合格样本, pe.转偏移(pe.资源目录[0]) + 14, b"\xff\xff")))
        坏样本表.append(("资源目录项指到 .rsrc 外", 改一处(合格样本, pe.转偏移(pe.资源目录[0]) + 16 + 4, (0x00000100).to_bytes(4, "little"))))
        元素 = 定位[(4, 127)]
        菜单偏移 = 元素["数据偏移"]
        坏样本表.append(("菜单版本号改成 1（MENUEX，本解不支持）", 改一处(合格样本, 菜单偏移, b"\x01\x00")))
        坏样本表.append(("菜单末项文字去掉 NUL", 改一处(合格样本, 菜单偏移 + 元素["大小"] - 2, b"\x41\x00")))
        坏样本表.append(("菜单资源声明长度砍半", 改一处(合格样本, 元素["数据项偏移"] + 4, (元素["大小"] // 2).to_bytes(4, "little"))))
        dl = 定位[(5, 303)]
        d0 = dl["数据偏移"]
        坏样本表.append(("对话框控件数改成 9999", 改一处(合格样本, d0 + 8, (9999).to_bytes(2, "little"))))
        坏样本表.append(("对话框资源声明长度砍掉 4 字节", 改一处(合格样本, dl["数据项偏移"] + 4, (dl["大小"] - 4).to_bytes(4, "little"))))
        字节串 = 定位[(6, 2049)]
        坏样本表.append(("字符串块首条长度改成 0xFFFF", 改一处(合格样本, 字节串["数据偏移"], b"\xff\xff")))
        加速键叶 = 定位[(9, 30997)]
        坏样本表.append(("加速键长度改成 25（非 8 倍数）", 改一处(合格样本, 加速键叶["数据项偏移"] + 4, (25).to_bytes(4, "little"))))
        图标叶 = 定位[(14, 126)]
        坏样本表.append(("图标组条数改成 9", 改一处(合格样本, 图标叶["数据偏移"] + 4, (9).to_bytes(2, "little"))))
        版本叶 = 定位[(16, 1)]
        坏样本表.append(("版本资源首块长度改成 1", 改一处(合格样本, 版本叶["数据偏移"], b"\x01\x00")))
    except 解析错误 as ex:
        print("警告：好样本自身就解不动（%s），反向样本只跑通用那批" % ex)

    print("自测：喂 %d 个坏样本，断言「报错且不产出任何字段」" % len(坏样本表))
    失败 = 0
    for 名称, 数据 in 坏样本表:
        try:
            读数 = 反解数据(数据, 名称)
            项数合计 = sum(len(表值) for 表值 in 读数["菜单"].values()) + sum(len(表值[1]["控件"]) for 表值 in 读数["对话框"].values())
            print("  ✗ %-34s 竟然解析成功（解出菜单/控件 %d 项）—— 假绿" % (名称, 项数合计))
            失败 += 1
        except 解析错误 as ex:
            print("  ✓ %-34s 报错：%s" % (名称, str(ex)[:60]))
        except (struct.error, IndexError, ValueError, OverflowError, TypeError, UnicodeDecodeError) as ex:
            print("  ✗ %-34s 抛了非解析错误（%s: %s）" % (名称, type(ex).__name__, str(ex)[:40]))
            失败 += 1
    try:
        读数 = 反解界面(样本)
        print("  ✓ 正向样本 %s 解析成功（菜单 %d 项 · 对话框 %d 个 · 控件 %d 个 · 字符串 %d 条）"
              % (os.path.basename(样本), sum(len(表值[1]) for 表值 in 读数["菜单"].values()), len(读数["对话框"]),
                 sum(len(表值[1]["控件"]) for 表值 in 读数["对话框"].values()),
                 sum(1 for 表值 in 读数["字符串"].values() for 串条 in 表值[1] if 串条)))
    except 解析错误 as ex:
        print("  ✗ 正向样本反而失败：%s" % ex)
        失败 += 1
    print("自测结论：%s（坏样本 %d 个 · 失败 %d）" % ("通过" if 失败 == 0 else "不通过", len(坏样本表), 失败))
    return 1 if 失败 else 0
