# -*- coding: utf-8 -*-
"""检查 —— 生成物指纹闸：重新生成到内存，与落盘件逐字节比对并报第一处不一致。"""

import hashlib
import os
import sys

from .路径形状 import 生成器相对路径
from .生成流程 import 生成, 落盘路径


def 找第一处不一致(新, 旧, 起点=0):
    """返回 (偏移, 新行, 旧行, 行号)；从 起点 之后完全一致则返回 None。"""
    公共 = min(len(新), len(旧))
    偏移 = None
    for 序 in range(起点, 公共):
        if 新[序] != 旧[序]:
            偏移 = 序
            break
    if 偏移 is None:
        if len(新) == len(旧):
            return None
        偏移 = 公共

    def 取行(字节流, 位置):
        头 = 字节流.rfind(b"\n", 0, 位置) + 1
        尾 = 字节流.find(b"\n", 位置)
        if 尾 < 0:
            尾 = len(字节流)
        return 字节流[头:尾].decode("utf-8", "replace"), 字节流[:位置].count(b"\n") + 1

    新位置 = min(偏移, max(len(新) - 1, 0))
    旧位置 = min(偏移, max(len(旧) - 1, 0))
    新行, 行号 = 取行(新, 新位置)
    旧行, _ = 取行(旧, 旧位置)
    return 偏移, 新行, 旧行, 行号


def 源指纹块范围(新):
    """产物里 源指纹 那一段的 [起, 止) 字节区间；找不到返回 None。

    源指纹必然先于正文变化（改了源，指纹就先变），所以只报「第一处」等于只报指纹行、
    说不出到底改了什么。故额外报「越过源指纹块后的第一处」。
    """
    起 = 新.find("// 源指纹：".encode("utf-8"))
    if 起 < 0:
        return None
    止 = 新.find("// 生成器：".encode("utf-8"), 起)
    if 止 < 0:
        return None
    return 起, 止


def 报提醒(提醒):
    """源数据自相矛盾 / 未定数之类、不该卡住生成的发现：走 stderr，不进产物（保确定性）。"""
    for 一条 in 提醒:
        print("提醒（不卡生成）：%s" % 一条, file=sys.stderr)


def 检查(根):
    新字节, 计数, 提醒 = 生成(根)
    报提醒(提醒)
    if not os.path.isfile(落盘路径(根)):
        print("生成物不存在：%s" % 根.落盘件)
        print("跑一次生成：python %s --声明根 %s" % (生成器相对路径, 根.根))
        return 1
    with open(落盘路径(根), "rb") as 句柄:
        旧字节 = 句柄.read()
    if 新字节 == 旧字节:
        print(
            "生成物新鲜：%s（%d 字节 · sha256 %s）"
            % (根.落盘件, len(新字节), hashlib.sha256(新字节).hexdigest())
        )
        return 0
    print("生成物不新鲜：%s" % 根.落盘件)
    print("  落盘 %d 字节 · 重新生成 %d 字节" % (len(旧字节), len(新字节)))

    处 = 找第一处不一致(新字节, 旧字节)
    偏移, 新行, 旧行, 行号 = 处
    print("  第一处不一致：字节偏移 %d（第 %d 行）" % (偏移, 行号))
    print("    落盘　　：%s" % 旧行)
    print("    重新生成：%s" % 新行)

    范围 = 源指纹块范围(新字节)
    if 范围 is not None and 范围[0] <= 偏移 < 范围[1]:
        再 = 找第一处不一致(新字节, 旧字节, 范围[1])
        if 再 is not None:
            再偏移, 再新行, 再旧行, 再行号 = 再
            print("  （上面那处落在源指纹块里，说明源被改过。越过指纹块后的第一处不一致：）")
            print("  正文第一处：字节偏移 %d（第 %d 行）" % (再偏移, 再行号))
            print("    落盘　　：%s" % 再旧行)
            print("    重新生成：%s" % 再新行)
        else:
            print("  （差异只在源指纹块里：源的内容变了但正文没变——例如改了 JSON 的键序或空白。）")

    print("  处置：python %s --声明根 %s" % (生成器相对路径, 根.根))
    return 1
