# -*- coding: utf-8 -*-
"""检查 —— 生成物指纹闸：重新生成到内存，与落盘件逐字节比对并报第一处不一致。"""

import os
import sys

from .路径形状 import 生成器相对路径, 仓根
from .生成流程 import 生成声明, 落盘件表


def 找第一处不一致(新内容, 旧, 起点=0):
    """返回 (偏移, 新行, 旧行, 行号)；从 起点 之后完全一致则返回 None。"""
    公共 = min(len(新内容), len(旧))
    偏移 = None
    for 序号 in range(起点, 公共):
        if 新内容[序号] != 旧[序号]:
            偏移 = 序号
            break
    if 偏移 is None:
        if len(新内容) == len(旧):
            return None
        偏移 = 公共

    def 取行(字节流, 位置):
        头部 = 字节流.rfind(b"\n", 0, 位置) + 1
        尾部 = 字节流.find(b"\n", 位置)
        if 尾部 < 0:
            尾部 = len(字节流)
        return 字节流[头部:尾部].decode("utf-8", "replace"), 字节流[:位置].count(b"\n") + 1

    新位置 = min(偏移, max(len(新内容) - 1, 0))
    旧位置 = min(偏移, max(len(旧) - 1, 0))
    新行, 行号 = 取行(新内容, 新位置)
    旧行, _ = 取行(旧, 旧位置)
    return 偏移, 新行, 旧行, 行号


def 源指纹块范围(新内容):
    """产物里 源指纹 那一段的 [起, 止) 字节区间；找不到返回 None。

    源指纹必然先于正文变化（改了源，指纹就先变），所以只报「第一处」等于只报指纹行、
    说不出到底改了什么。故额外报「越过源指纹块后的第一处」。
    """
    区间起点 = 新内容.find("// 源指纹：".encode("utf-8"))
    if 区间起点 < 0:
        return None
    区间终点 = 新内容.find("// 生成器：".encode("utf-8"), 区间起点)
    if 区间终点 < 0:
        return None
    return 区间起点, 区间终点


def 报提醒(提醒):
    """源数据自相矛盾 / 未定数之类、不该卡住生成的发现：走 stderr，不进产物（保确定性）。"""
    for 一条 in 提醒:
        print("提醒（不卡生成）：%s" % 一条, file=sys.stderr)


def 陈旧件(根目录, 应有):
    """盘上在、生成物**不再出**的生成物子件（陈旧件 = 也是不新鲜，须报，不许静默留）。

    认法：顶层 `src/*数据.rs`（生成物命名的固定后缀；路由件与全部子件都以「数据.rs」结尾）
    里不在 `应有` 的。`lib.rs` / `接缝.rs` / `资源声明.rs` 不以「数据.rs」结尾 ⇒ 不误伤。
    """
    目录 = os.path.join(仓根, os.path.dirname(根目录.落盘件))
    if not os.path.isdir(目录):
        return []
    应有集 = set(应有)
    输出缓冲 = []
    for 名称 in sorted(os.listdir(目录)):
        if not 名称.endswith("数据.rs"):
            continue
        相对 = os.path.join(os.path.dirname(根目录.落盘件), 名称).replace(os.sep, "/")
        if 相对 not in 应有集:
            输出缓冲.append(相对)
    return 输出缓冲


def 检查声明(根目录):
    新件, 计数, 提醒 = 生成声明(根目录)
    报提醒(提醒)
    应有 = 落盘件表(根目录)
    缺失文件 = [相对 for 相对 in 应有 if not os.path.isfile(os.path.join(仓根, 相对))]
    if 缺失文件:
        print("生成物不存在：%s" % " · ".join(缺失文件))
        print("跑一次生成：python %s --声明根 %s" % (生成器相对路径, 根目录.根))
        return 1
    不一致 = []
    for 相对 in 应有:
        新字节 = 新件[相对]
        with open(os.path.join(仓根, 相对), "rb") as 句柄:
            旧字节 = 句柄.read()
        if 新字节 != 旧字节:
            不一致.append((相对, 新字节, 旧字节))
    孤儿 = 陈旧件(根目录, 应有)
    if not 不一致 and not 孤儿:
        总字节 = sum(len(新件[相对]) for 相对 in 应有)
        print(
            "生成物新鲜：%d 件（路由件 %s · 共 %d 字节）"
            % (len(应有), 根目录.落盘件, 总字节)
        )
        return 0
    print("生成物不新鲜：%d 件不一致 · %d 件陈旧" % (len(不一致), len(孤儿)))
    for 相对, 新字节, 旧字节 in 不一致:
        print("  ── %s（落盘 %d 字节 · 重新生成 %d 字节）" % (相对, len(旧字节), len(新字节)))
        差异位置 = 找第一处不一致(新字节, 旧字节)
        偏移, 新行, 旧行, 行号 = 差异位置
        print("    第一处不一致：字节偏移 %d（第 %d 行）" % (偏移, 行号))
        print("      落盘　　：%s" % 旧行)
        print("      重新生成：%s" % 新行)
        范围 = 源指纹块范围(新字节)
        if 范围 is not None and 范围[0] <= 偏移 < 范围[1]:
            正文差异 = 找第一处不一致(新字节, 旧字节, 范围[1])
            if 正文差异 is not None:
                再偏移, 再新行, 再旧行, 再行号 = 正文差异
                print("    （上面那处落在源指纹块里，说明源被改过。越过指纹块后的第一处不一致：）")
                print("    正文第一处：字节偏移 %d（第 %d 行）" % (再偏移, 再行号))
                print("      落盘　　：%s" % 再旧行)
                print("      重新生成：%s" % 再新行)
            else:
                print("    （差异只在源指纹块里：源的内容变了但正文没变——例如改了 JSON 的键序或空白。）")
    for 相对 in 孤儿:
        print("  ── 陈旧件：%s（生成物不再出它 —— 拆分/改名后的残留，应删）" % 相对)
    print("  处置：python %s --声明根 %s" % (生成器相对路径, 根目录.根))
    return 1
