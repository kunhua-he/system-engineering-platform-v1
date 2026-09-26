#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声明记录区反解 —— 只读字节解析 `.e` / `.ec` 段数据里的「声明记录区」。

**一句话为什么**：1103 的输出形状不许凭空立（`项目文档/决策记录/2026-09-27_1103输出形状与注册表来源.md`
裁决一：「先取证、后立形状」），本脚本就是那次取证；逐条读数与十六进制见
`项目文档/设计文档/声明记录区实测.md`。

**只读字节**：全脚本没有 `dlopen` / `ctypes` / `subprocess`；语料目录只读、不改 mtime。
形状来源是既有冻结件，本脚本**不另造形状**：
  · 容器层：`src/容器/形状.rs`（魔数 `CNWTEPRG` · 段头 44B · 段类型号 1..15/255）
  · 段数据层：`src/记录流/形状.rs`（段数据头 56B · 段体魔数 `0x030BEF3F` · 支持库表）

    python3 开发工具/取证/声明记录区反解.py                 # 默认样本，出报告
    python3 开发工具/取证/声明记录区反解.py --样本 <path>
    python3 开发工具/取证/声明记录区反解.py --转储           # 加十六进制转储
    python3 开发工具/取证/声明记录区反解.py --全部           # 全语料计数（唯一硬读数）
    python3 开发工具/取证/声明记录区反解.py --自测           # 反向样本断言（必跑）

**判据分层（不许混）**：
  · 「可证记录」= 在本字节流里能自证的一条记录（长度字段自洽 + 载荷自洽），工具**只证它在哪**；
  · 「不判」= 分区边界 / 记录头字段语义 / 令牌语义 —— 盘面无自描述，工具一律标 `不判`，绝不猜。
"""

import argparse
import glob
import os
import struct
import sys

# ── 容器层常量（源出 src/容器/形状.rs，逐字照抄）────────────────────────────────
魔数 = b"CNWTEPRG"
段头长度 = 44
段头魔术甲 = b"\x19\x73"          # u16 0x7319
段头魔术乙 = b"\x11\x15"          # u16 0x1511
段类型白名单 = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 255)
段类型_无名七 = 7
段类型_程序加固 = 255
段类型_程序 = 3

# ── 段数据层常量（源出 src/记录流/形状.rs，逐字照抄）────────────────────────────
段数据头长度 = 56
段体魔数 = 0x030BEF3F
头偏移_段序号, 头偏移_保留, 头偏移_校验值, 头偏移_体长 = 0x00, 0x04, 0x08, 0x0C
头偏移_补零, 头偏移_补零长度 = 0x10, 40
头偏移_体甲, 头偏移_体魔数 = 0x38, 0x3C
引用分隔符 = 0x0D

# ── 声明记录区里**已实测可证**的记录形态常量（证据见 声明记录区实测.md）────────────
串长上限 = 1024                  # 串记录候选的串长上限（超过即不认，避免把随机字节当串）
语句操作码甲 = 0x37              # `37 1A` / `37 18`：实测的语句字节码首字节
语句操作码乙 = (0x1A, 0x18)
DLL令牌类别 = 0x45               # DLL 命令参数令牌的类别字节（实测 554/554）
数据类型掩码 = 0x8000            # SDT_* 编码的高 16 位（sdk/cpp/elib/lib2.h DATA_TYPE）


class 解析错误(Exception):
    """字节不支持某种解读时抛这个 —— 绝不返回编出来的字段（fail-closed）。"""


# ── 容器层 ────────────────────────────────────────────────────────────────────

def 是段头(d, pos):
    """段头结构是否成立。判据与 `src/容器/反解定义.rs::是段头起点` 一致。"""
    if pos + 段头长度 > len(d):
        return False
    h = d[pos:pos + 段头长度]
    if h[0:2] != 段头魔术甲 or h[2:4] != 段头魔术乙:
        return False
    if h[8:10] != 段头魔术甲 or h[10] != 0x00:
        return False
    号 = h[11]
    if 号 not in 段类型白名单:
        return False
    尾 = h[0x27:0x2C]
    if 号 == 段类型_无名七:
        return 尾 == b"\x00\x00\x00\x00\x00"
    if 号 == 段类型_程序加固:
        return 尾 == b"\x19\x73\x00\x03\x00"
    return 尾 == b"\x19\x73\x00\x00\x00"


def 找下一段头(d, 起点):
    for p in range(起点, len(d) - 段头长度 + 1):
        if 是段头(d, p):
            return p
    return None


def 反解容器(d):
    """容器字节 → [(段类型, 段数据起点, 段数据止, 段头起点)]。段边界靠扫描（本格式无段长字段）。"""
    if len(d) < len(魔数) or d[:len(魔数)] != 魔数:
        raise 解析错误("无 CNWTEPRG 魔数，不是易程序容器")
    pos, 段 = len(魔数), []
    while pos < len(d):
        if len(d) - pos < 段头长度:
            raise 解析错误("段头截断 @0x%x（剩 %d 字节）" % (pos, len(d) - pos))
        if not 是段头(d, pos):
            raise 解析错误("段头标记/类型号不符 @0x%x" % pos)
        号 = d[pos + 11]
        下一 = 找下一段头(d, pos + 段头长度)
        尾 = 下一 if 下一 is not None else len(d)
        段.append((号, pos + 段头长度, 尾, pos))
        if 下一 is None:
            break
        pos = 下一
    return 段


# ── 段数据层 ──────────────────────────────────────────────────────────────────

def 解段数据(b):
    """段数据字节 → 头字段 + 支持库表 + 声明记录区起点。逐条 fail-closed。"""
    if len(b) < 段数据头长度:
        raise 解析错误("段数据头截断 { 需要: %d, 实有: %d }" % (段数据头长度, len(b)))
    段序号, 保留, 校验值, 体长 = struct.unpack_from("<IIII", b, 0)
    if 保留 != 0:
        raise 解析错误("段数据头保留非零 { 位置: %d, 实取: %d }" % (头偏移_保留, 保留))
    if b[头偏移_补零:头偏移_补零 + 头偏移_补零长度] != b"\x00" * 头偏移_补零长度:
        raise 解析错误("段数据头补零非零")
    if 体长 != len(b) - 段数据头长度:
        raise 解析错误("体长不符 { 头内: %d, 实有: %d }" % (体长, len(b) - 段数据头长度))
    体甲, 魔 = struct.unpack_from("<II", b, 头偏移_体甲)
    if 魔 != 段体魔数:
        raise 解析错误("段体魔数不符 { 实取: 0x%08x }" % 魔)

    p = 段数据头长度 + 8

    def 读长度前缀(p, 第几, 元素宽):
        if p + 4 > len(b):
            raise 解析错误("数组越界 { 第几: %d }" % 第几)
        前缀 = struct.unpack_from("<I", b, p)[0]
        p += 4
        if 前缀 % 元素宽 != 0:
            raise 解析错误("数组长度前缀非整元素 { 第几: %d, 前缀: %d, 元素宽: %d }"
                        % (第几, 前缀, 元素宽))
        if 前缀 > len(b) - p:
            raise 解析错误("数组越界 { 第几: %d, 前缀: %d, 剩余: %d }" % (第几, 前缀, len(b) - p))
        return 前缀, p

    甲长, p = 读长度前缀(p, 1, 4)
    数组甲 = list(struct.unpack_from("<%dI" % (甲长 // 4), b, p)) if 甲长 else []
    p += 甲长
    乙长, p = 读长度前缀(p, 2, 2)
    数组乙 = list(struct.unpack_from("<%dH" % (乙长 // 2), b, p)) if 乙长 else []
    p += 乙长
    丙长, p = 读长度前缀(p, 3, 2)
    数组丙 = list(struct.unpack_from("<%dH" % (丙长 // 2), b, p)) if 丙长 else []
    p += 丙长
    if p + 2 > len(b):
        raise 解析错误("数组越界 { 第几: 4 }")
    声明数 = struct.unpack_from("<H", b, p)[0]
    p += 2
    if 声明数 != len(数组甲) or len(数组乙) != len(数组甲) or len(数组丙) != len(数组甲):
        raise 解析错误("支持库数不符 { 数组元素数: %d, 声明数: %d }" % (len(数组甲), 声明数))
    引用表 = []
    for 序 in range(声明数):
        if p + 4 > len(b):
            raise 解析错误("支持库引用越界 { 第几条: %d }" % 序)
        串长 = struct.unpack_from("<I", b, p)[0]
        p += 4
        if 串长 > len(b) - p:
            raise 解析错误("支持库引用越界 { 第几条: %d, 串长: %d, 剩余: %d }"
                        % (序, 串长, len(b) - p))
        引用表.append(b[p:p + 串长])
        p += 串长
    return {
        "段序号": 段序号, "保留": 保留, "校验值": 校验值, "体长": 体长,
        "体甲": 体甲, "数组甲": 数组甲, "数组乙": 数组乙, "数组丙": 数组丙,
        "引用表": 引用表, "声明记录区起点": p,
    }


def 取声明记录区(容器字节):
    """容器字节 → [(段类型, 段数据起点, 声明记录区起点(绝对), 声明记录区) ]。"""
    出 = []
    for 号, 起, 止, _头 in 反解容器(容器字节):
        if 号 != 段类型_程序:
            continue
        b = 容器字节[起:止]
        r = 解段数据(b)
        区起 = r["声明记录区起点"]
        出.append((号, 起, 起 + 区起, b[区起:], r))
    return 出


# ── 记录级反解（**只证一条记录在不在**，不证分区边界）────────────────────────────

def 合法GBK(bs):
    """全字节可解 GBK、无 NUL、无控制字符（含 0x7F..0xA0 区）。"""
    if not bs or b"\x00" in bs:
        return False
    try:
        串 = bs.decode("gbk")
    except Exception:
        return False
    for c in 串:
        o = ord(c)
        if o < 0x20 or 0x7F <= o <= 0xA0:
            return False
    return True


def 试串记录(q, i):
    """`u32 串长` + `串长` 字节 GBK + `00`。返回 (记录, 下一位置) 或 None。"""
    if i + 5 > len(q):
        return None
    L = struct.unpack_from("<I", q, i)[0]
    if not (1 <= L <= 串长上限):
        return None
    if i + 4 + L + 1 > len(q) or q[i + 4 + L] != 0x00:
        return None
    if not 合法GBK(q[i + 4:i + 4 + L]):
        return None
    return {"种类": "串记录", "起": i, "止": i + 4 + L + 1, "串长": L,
            "串": q[i + 4:i + 4 + L].decode("gbk")}, i + 4 + L + 1


def 试语句字节码(q, i):
    """`37 1A`/`37 18` + `u32 长度`（**含尾 NUL**）+ 文本。返回 (记录, 下一位置) 或 None。"""
    if i + 7 > len(q) or q[i] != 语句操作码甲 or q[i + 1] not in 语句操作码乙:
        return None
    L = struct.unpack_from("<I", q, i + 2)[0]
    if not (1 <= L <= 1 << 20) or i + 6 + L > len(q):
        return None
    if q[i + 6 + L - 1] != 0x00:
        return None
    if not 合法GBK(q[i + 6:i + 6 + L - 1]):
        return None
    return {"种类": "语句字节码", "起": i, "止": i + 6 + L, "长度": L,
            "文本": q[i + 6:i + 6 + L - 1].decode("gbk")}, i + 6 + L


def 试DLL命令记录(q, i):
    """`u32 L1`+使用名 + `u32 L2`+库名 + `u32 L3`+命令名 + `u32 参数个数` + `u32 保留`
    + 参数个数 × `<u16 号> <u8 甲> <u8 0x45>`。返回 (记录, 下一位置) 或 None。"""
    p, 名表 = i, []
    for _ in ("使用名", "库名", "命令名"):
        if p + 4 > len(q):
            return None
        L = struct.unpack_from("<I", q, p)[0]
        if not (1 <= L <= 256) or p + 4 + L > len(q) or not 合法GBK(q[p + 4:p + 4 + L]):
            return None
        名表.append(q[p + 4:p + 4 + L].decode("gbk"))
        p += 4 + L
    if p + 8 > len(q):
        return None
    N, 保留 = struct.unpack_from("<II", q, p)
    if not (0 <= N <= 64) or p + 8 + N * 4 > len(q):
        return None
    if 保留 > 0xFFFF:                      # 既有件 8 个实测点全 ≤ 0xFF；>0xFFFF 判为误切（fail-closed）
        return None
    参 = q[p + 8:p + 8 + N * 4]
    if any(参[t + 3] != DLL令牌类别 for t in range(0, len(参), 4)):
        return None
    出 = {"种类": "DLL命令记录", "起": i, "止": p + 8 + N * 4, "参数个数": N, "保留": 保留,
          "使用名": 名表[0], "库名": 名表[1], "命令名": 名表[2],
          "号": [struct.unpack_from("<H", 参, t)[0] for t in range(0, len(参), 4)],
          "甲": sorted(set(参[t + 2] for t in range(0, len(参), 4)))}
    return 出, p + 8 + N * 4


def 试数据类型码(q, i):
    """`u32` 且高 16 位 == 0x8000（`sdk/cpp/elib/lib2.h` 的 DATA_TYPE 编码）。"""
    if i + 4 > len(q):
        return None
    v = struct.unpack_from("<I", q, i)[0]
    if v >> 16 != 数据类型掩码:
        return None
    return {"种类": "数据类型码", "起": i, "止": i + 4, "值": v}, i + 4


试法 = (试DLL命令记录, 试语句字节码, 试数据类型码, 试串记录)


def 走记录(q, 起点=0, 止=None):
    """从 `起点` 贪心走：每处依次试四种可证记录形态，命中即收，否则前进 1 字节（记「未解字节」）。

    **只证「某处是一条 X 记录」**；不证分区边界、不证记录头字段语义（那些标 `不判`）。
    """
    止 = len(q) if 止 is None else 止
    i, 记录, 未解 = 起点, [], 0
    while i < 止:
        for 法 in 试法:
            r = 法(q, i)
            if r is not None:
                记录.append(r[0])
                未解 += 0
                i = r[1]
                break
        else:
            未解 += 1
            i += 1
    return 记录, 未解


# ── 出报告 ────────────────────────────────────────────────────────────────────

def 十六进制(q, 基=0, 宽=16, 上限=None):
    n = len(q) if 上限 is None else min(len(q), 上限)
    行 = []
    for i in range(0, n, 宽):
        c = q[i:i + 宽]
        try:
            t = c.decode("gbk")
        except Exception:
            t = ""
        t = "".join(ch if 32 <= ord(ch) < 127 or ord(ch) > 0x2000 else "." for ch in t)
        行.append("%04x  %-*s  %s" % (基 + i, 宽 * 3 - 1, c.hex(" "), t))
    return "\n".join(行)


def 出报告(路径, 转储=False):
    with open(路径, "rb") as fh:
        数据 = fh.read()
    段 = 反解容器(数据)
    print("样本 %s（%d 字节）｜ 段记录 %d 条 ｜ 段类型序列 %s"
          % (路径, len(数据), len(段), [x[0] for x in 段]))
    命中 = [x for x in 段 if x[0] == 段类型_程序]
    if not 命中:
        print("  本文件没有类型 3「程序段」，声明记录区不存在")
        return 0
    for _, 段起, 段止, 头起 in 命中:
        b = 数据[段起:段止]
        r = 解段数据(b)
        区起 = r["声明记录区起点"]
        q = b[区起:]
        print("-" * 78)
        print("① 段头 @0x%x ｜ 段数据 @0x%x..0x%x（%d 字节）" % (头起, 段起, 段止, len(b)))
        print("② 段数据头：段序号=%d 保留=%d 校验值=0x%08x 体长=%d（= 段数据长−56）体甲=0x%08x"
              % (r["段序号"], r["保留"], r["校验值"], r["体长"], r["体甲"]))
        print("   体长校验：%d == %d ⇒ %s" % (r["体长"], len(b) - 段数据头长度,
              "命中" if r["体长"] == len(b) - 段数据头长度 else "不符"))
        print("③ 段体魔数 0x%08x ⇒ %s" % (段体魔数, "命中" if struct.unpack_from("<I", b, 头偏移_体魔数)[0] == 段体魔数 else "不符"))
        print("④ 支持库表：数组甲 %s · 数组乙 %s · 数组丙 %s · 支持库数 %d"
              % (r["数组甲"], r["数组乙"], r["数组丙"], len(r["引用表"])))
        for x in r["引用表"]:
            print("     引用：" + repr(x[:96]))
        print("⑤ **声明记录区**：段数据内偏移 0x%x（= %d）→ 文件偏移 0x%x；长度 %d 字节（占段数据 %.2f%%）"
              % (区起, 区起, 段起 + 区起, len(q), 100.0 * len(q) / len(b)))
        print("   边界判据：起点 = 段数据头(56) + 段体头(8) + 支持库表(三数组+u16+N 条引用)；"
              "止点 = 段数据头.体长 + 56")
        print("   头 4 字节 = %s ⇒ %s" % (q[:4].hex(" "), "恒 0（本脚本 1456/1456 实测）" if q[:4] == b"\x00\x00\x00\x00" else "非 0（不合本脚本的边界判据）"))
        记录, 未解 = 走记录(q)
        计 = {}
        for x in 记录:
            计[x["种类"]] = 计.get(x["种类"], 0) + 1
        print("⑥ 可证记录（只证「某处是一条 X 记录」，不证分区）：")
        for k in ("DLL命令记录", "语句字节码", "数据类型码", "串记录"):
            if 计.get(k):
                print("     %-12s %d 条" % (k, 计[k]))
        print("   未解字节 %d / %d（%.2f%%）—— 分区边界与记录头字段语义**不判**"
              % (未解, len(q), 100.0 * 未解 / max(1, len(q))))
        for x in 记录[:24]:
            if x["种类"] == "串记录":
                print("     [0x%04x] 串记录 长%3d %r" % (x["起"], x["串长"], x["串"]))
            elif x["种类"] == "语句字节码":
                print("     [0x%04x] 语句字节码 长%3d %r" % (x["起"], x["长度"], x["文本"]))
            elif x["种类"] == "DLL命令记录":
                print("     [0x%04x] DLL命令 %r.%r → 使用名 %r 参数%d 甲%s 号%s"
                      % (x["起"], x["库名"], x["命令名"], x["使用名"],
                         x["参数个数"], x["甲"], x["号"]))
            else:
                print("     [0x%04x] 数据类型码 0x%08x" % (x["起"], x["值"]))
        if 转储:
            print("⑦ 十六进制转储（声明记录区，前 512 字节）：")
            print(十六进制(q, 上限=512))
    return 0


def 扫全部(目录):
    """全语料读数 —— 本腿的**唯一硬读数**。"""
    文件 = sorted(set(glob.glob(os.path.join(目录, "**", "*.e"), recursive=True)
                    + glob.glob(os.path.join(目录, "**", "*.ec"), recursive=True)
                    + glob.glob(os.path.join(目录, "**", "*.E"), recursive=True)
                    + glob.glob(os.path.join(目录, "**", "*.EC"), recursive=True)))
    段数 = 首4零 = 全零 = 0
    区长 = []
    计 = {}
    未解总 = 字节总 = 0
    坏 = []
    for p in 文件:
        try:
            with open(p, "rb") as fh:
                d = fh.read()
            区表 = 取声明记录区(d)
        except 解析错误 as ex:
            坏.append((p, str(ex)))
            continue
        for _, _, _, q, _ in 区表:
            段数 += 1
            区长.append(len(q))
            if len(q) >= 4 and q[:4] == b"\x00\x00\x00\x00":
                首4零 += 1
            if not any(q):
                全零 += 1
            记录, 未解 = 走记录(q)
            for x in 记录:
                计[x["种类"]] = 计.get(x["种类"], 0) + 1
            未解总 += 未解
            字节总 += len(q)
    区长.sort()
    print("=" * 78)
    print("全语料 %s：文件 %d · 程序段 %d · 解析失败 %d" % (目录, len(文件), 段数, len(坏)))
    if 坏:
        for p, e in 坏[:5]:
            print("   失败样例 %s：%s" % (p, e))
    print("声明记录区长度：min %d · 中位 %d · max %d" % (区长[0], 区长[len(区长) // 2], 区长[-1]))
    print("头 4 字节恒 0：%d / %d" % (首4零, 段数))
    print("整区全零（空程序）：%d / %d" % (全零, 段数))
    for k in ("串记录", "语句字节码", "DLL命令记录", "数据类型码"):
        print("可证记录 %-12s %d 条" % (k, 计.get(k, 0)))
    print("可证记录覆盖字节 %d / %d（%.2f%%）；其余 %d 字节（%.2f%%）**不判**"
          % (字节总 - 未解总, 字节总, 100.0 * (字节总 - 未解总) / 字节总,
             未解总, 100.0 * 未解总 / 字节总))
    return 0


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


def main():
    ap = argparse.ArgumentParser(description="声明记录区静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/lib/krnln/samples/第一个程序.e")
    ap.add_argument("--目录", default="/tmp/易语言源码")
    ap.add_argument("--全部", action="store_true")
    ap.add_argument("--自测", action="store_true")
    ap.add_argument("--转储", action="store_true")
    a = ap.parse_args()
    if a.自测:
        return 自测(a.样本)
    if a.全部:
        return 扫全部(a.目录)
    return 出报告(a.样本, a.转储)


if __name__ == "__main__":
    sys.exit(main())
