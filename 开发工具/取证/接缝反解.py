#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接缝反解 —— 纯静态字节解析易语言支持库(.fne)的 `GetNewInf` 接缝。

**只读字节，不加载、不注入、不执行**：只做 PE 头 / 导出表 / 数据段偏移解析，
全脚本没有 dlopen / ctypes / subprocess 触碰语料的路径；语料目录只读。
反解对象：`GetNewInf` 返回的静态「库信息」结构（LIB_INFO）及它指向的
字符串表 · 命令表 · 参数表 · 类型表 · 常量表。

    python3 开发工具/取证/接缝反解.py            # 默认 lib/shellEx.fne
    python3 开发工具/取证/接缝反解.py --样本 <path>
    python3 开发工具/取证/接缝反解.py --全部     # 全目录「计数自洽性」
    python3 开发工具/取证/接缝反解.py --自测     # 反向样本断言（必跑）

字段名与语义的对照物是 `sdk/cpp/elib/lib2.h`，**证据一律是被解析文件自己的字节**。
"""

import argparse, glob, os, struct, sys

库格式号 = 0x01312D65          # =20000101，LIB_INFO 第一个 DWORD
导出名 = b"GetNewInf"          # 实测全部 .fne 都导出此名
库信息大小 = 0x90
命令项大小, 参数项大小, 常量项大小, 类型项大小 = 0x24, 0x18, 0x20, 0x38

# 结构定义：偏移 · 宽度 · 名称 · 类别(u32/i32/u16/i16/f64/ptr/str)
库信息字段 = [
    (0x00, 4, "m_dwLibFormatVer", "u32"), (0x04, 4, "m_szGuid", "str"), (0x08, 4, "m_nMajorVersion", "i32"),
    (0x0C, 4, "m_nMinorVersion", "i32"), (0x10, 4, "m_nBuildNumber", "i32"), (0x14, 4, "m_nRqSysMajorVer", "i32"),
    (0x18, 4, "m_nRqSysMinorVer", "i32"), (0x1C, 4, "m_nRqSysKrnlLibMajorVer", "i32"), (0x20, 4, "m_nRqSysKrnlLibMinorVer", "i32"),
    (0x24, 4, "m_szName", "str"), (0x28, 4, "m_nLanguage", "i32"), (0x2C, 4, "m_szExplain", "str"),
    (0x30, 4, "m_dwState", "u32"), (0x34, 4, "m_szAuthor", "str"), (0x38, 4, "m_szZipCode", "str"),
    (0x3C, 4, "m_szAddress", "str"), (0x40, 4, "m_szPhoto", "str"), (0x44, 4, "m_szFax", "str"),
    (0x48, 4, "m_szEmail", "str"), (0x4C, 4, "m_szHomePage", "str"), (0x50, 4, "m_szOther", "str"),
    (0x54, 4, "m_nDataTypeCount", "u32"), (0x58, 4, "m_pDataType", "ptr"), (0x5C, 4, "m_nCategoryCount", "u32"),
    (0x60, 4, "m_szzCategory", "ptr"), (0x64, 4, "m_nCmdCount", "u32"), (0x68, 4, "m_pBeginCmdInfo", "ptr"),
    (0x6C, 4, "m_pCmdsFunc", "ptr"), (0x70, 4, "m_pfnRunAddInFn", "ptr"), (0x74, 4, "m_szzAddInFnInfo", "ptr"),
    (0x78, 4, "m_pfnNotify", "ptr"), (0x7C, 4, "m_pfnSuperTemplate", "ptr"), (0x80, 4, "m_szzSuperTemplateInfo", "ptr"),
    (0x84, 4, "m_nLibConstCount", "u32"), (0x88, 4, "m_pLibConst", "ptr"), (0x8C, 4, "m_szzDependFiles", "ptr"),
]
命令字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szEgName", "str"), (0x08, 4, "m_szExplain", "str"),
    (0x0C, 2, "m_shtCategory", "i16"), (0x0E, 2, "m_wState", "u16"), (0x10, 4, "m_dtRetValType", "u32"),
    (0x14, 2, "m_wReserved", "u16"), (0x16, 2, "m_shtUserLevel", "i16"), (0x18, 2, "m_shtBitmapIndex", "i16"),
    (0x1A, 2, "m_shtBitmapCount", "i16"), (0x1C, 4, "m_nArgCount", "u32"), (0x20, 4, "m_pBeginArgInfo", "ptr"),
]
参数字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szExplain", "str"), (0x08, 2, "m_shtBitmapIndex", "i16"),
    (0x0A, 2, "m_shtBitmapCount", "i16"), (0x0C, 4, "m_dtType", "u32"), (0x10, 4, "m_nDefault", "i32"),
    (0x14, 4, "m_dwState", "u32"),
]
常量字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szEGName", "str"), (0x08, 4, "m_szExplain", "str"),
    (0x0C, 2, "m_shtReserved", "i16"), (0x0E, 2, "m_shtType", "i16"), (0x10, 4, "m_szText", "str"),
    (0x18, 8, "m_dbValue", "f64")]        # 自然对齐：DOUBLE 落在 8 的倍数上
类型字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szEgName", "str"), (0x08, 4, "m_szExplain", "str"),
    (0x0C, 4, "m_nCmdCount", "u32"), (0x10, 4, "m_pnCmdsIndex", "ptr"), (0x14, 4, "m_dwState", "u32"),
    (0x18, 4, "m_dwUnitBmpID", "u32"), (0x1C, 4, "m_nEventCount", "u32"), (0x20, 4, "m_pEventBegin", "ptr"),
    (0x24, 4, "m_nPropertyCount", "u32"), (0x28, 4, "m_pPropertyBegin", "ptr"), (0x2C, 4, "m_pfnGetInterface", "ptr"),
    (0x30, 4, "m_nElementCount", "u32"), (0x34, 4, "m_pElementBegin", "ptr")]
命令状态位 = {2: "隐含", 3: "错误", 4: "发布禁用", 5: "可追加参数", 6: "返回数组", 7: "对象拷贝", 8: "对象释放", 9: "对象构造"}
库状态位 = {2: "无运行代码", 3: "无编辑信息", 5: "数据库库", 7: "实为LIB_INFO2", 8: "IDE插件"}
数值格式 = {"u32": "<I", "i32": "<i", "u16": "<H", "i16": "<h", "f64": "<d"}

class 解析错误(Exception):
    """字节不支持某种解读时抛这个 —— 绝不返回编出来的字段。"""

class PE:
    """只读 PE32 解析器。任何越界都抛 解析错误，不做「尽量猜」。"""

    def __init__(self, 数据, 路径="<内存>"):
        self.路径, self.d = 路径, 数据
        if len(数据) < 0x40:
            raise 解析错误("文件短于 64 字节，DOS 头都不完整")
        if 数据[:2] != b"MZ":
            raise 解析错误("无 MZ 签名，不是 PE 文件")
        self.e = struct.unpack_from("<I", 数据, 0x3C)[0]
        if self.e + 24 > len(数据) or 数据[self.e:self.e + 4] != b"PE\0\0":
            raise 解析错误("e_lfanew(0x%x) 越界或处无 PE\\0\\0 签名" % self.e)
        self.机器, self.节数, _, _, _, self.可选头长, _ = struct.unpack_from("<HHIIIHH", 数据, self.e + 4)
        if self.可选头长 == 0 or self.e + 24 + self.可选头长 > len(数据):
            raise 解析错误("可选头长度 %d 为 0 或越界（只剩 %d）"
                        % (self.可选头长, len(数据) - self.e - 24))
        self.魔数 = struct.unpack_from("<H", 数据, self.e + 24)[0]
        if self.魔数 != 0x10B:
            raise 解析错误("魔数 0x%x 不是 PE32。64 位 LIB_INFO 布局未取证，拒绝猜" % self.魔数)
        self.基址 = struct.unpack_from("<I", 数据, self.e + 24 + 28)[0]
        self.节 = []
        for i in range(self.节数):
            b = self.e + 24 + self.可选头长 + i * 40
            if b + 40 > len(数据):
                raise 解析错误("节表第 %d 项越界" % i)
            名 = 数据[b:b + 8].rstrip(b"\0").decode("latin1")
            虚长, 虚址, 原长, 原址 = struct.unpack_from("<IIII", 数据, b + 8)
            if 原址 + 原长 > len(数据):
                raise 解析错误("节 %s 原始数据越界（%d+%d > %d）" % (名, 原址, 原长, len(数据)))
            self.节.append((名, 虚址, 虚长, 原址, 原长))
        if not self.节:
            raise 解析错误("节数为 0")

    def 转偏移(self, rva):
        for 名, 虚址, 虚长, 原址, 原长 in self.节:
            if 虚址 <= rva < 虚址 + max(虚长, 原长):
                o = 原址 + (rva - 虚址)
                if o >= len(self.d):
                    raise 解析错误("RVA 0x%x 映到文件外 0x%x" % (rva, o))
                return o
        raise 解析错误("RVA 0x%x 不在任何节里" % rva)

    def 取址(self, 绝对址):
        """把结构里存的指针（绝对地址）折成 RVA；0 → None。"""
        if 绝对址 == 0:
            return None
        if self.基址 <= 绝对址 < self.基址 + 0x40000000:
            return 绝对址 - self.基址
        if 绝对址 < len(self.d):
            return 绝对址
        raise 解析错误("指针 0x%x 既不在镜像里也不像 RVA" % 绝对址)

    def 读u32(self, 偏移):
        if 偏移 + 4 > len(self.d):
            raise 解析错误("读 u32 越界 @0x%x" % 偏移)
        return struct.unpack_from("<I", self.d, 偏移)[0]

    def 读串(self, 绝对址):
        rva = self.取址(绝对址)
        if rva is None:
            return None
        o = self.转偏移(rva)
        尾 = self.d.find(b"\0", o)
        if 尾 < 0:
            raise 解析错误("0x%x 处的字符串没有 NUL 结尾" % 绝对址)
        return self.d[o:尾].decode("gbk", "replace")

    def 导出(self):
        目录 = struct.unpack_from("<II", self.d, self.e + 24 + 96)
        if 目录[0] == 0:
            raise 解析错误("无导出目录（本库不是支持库？）")
        o = self.转偏移(目录[0])
        if o + 40 > len(self.d):
            raise 解析错误("导出目录越界")
        _, _, _, _, _, 基序, 函数数, 名字数, 函数表, 名字表, 序号表 = struct.unpack_from(
            "<IIHHIIIIIII", self.d, o)
        if 函数数 == 0:
            raise 解析错误("导出函数数为 0")
        函数 = struct.unpack_from("<%dI" % 函数数, self.d, self.转偏移(函数表))
        结果 = []
        for i in range(名字数):
            s = self.转偏移(self.读u32(self.转偏移(名字表) + 4 * i))
            idx = struct.unpack_from("<H", self.d, self.转偏移(序号表) + 2 * i)[0]
            if idx >= 函数数:
                raise 解析错误("名字序号 %d 超出函数数 %d" % (idx, 函数数))
            结果.append((self.d[s:self.d.find(b"\0", s)], 基序 + idx, 函数[idx]))
        return 结果

def 解接缝(pe):
    """返回 (序号, 导出RVA, 机器码前8字节, 结构RVA, 形式串)。判不出形式就抛错。"""
    命中 = [x for x in pe.导出() if x[0] == 导出名]
    if not 命中:
        raise 解析错误("导出表里没有 %s" % 导出名.decode())
    _, 序号, 当前 = 命中[0]
    导出rva = 当前
    码 = pe.d[pe.转偏移(当前):pe.转偏移(当前) + 16]
    形式 = []
    for _ in range(4):                       # 最多跟 4 层 thunk
        if 码[0] in (0xE8, 0xE9) and (码[0] != 0xE8 or 码[5] == 0xC3):
            目标 = 当前 + 5 + struct.unpack_from("<i", 码, 1)[0]
            形式.append(("call" if 码[0] == 0xE8 else "jmp") + " 0x%x" % 目标)
            当前 = 目标
            码 = pe.d[pe.转偏移(当前):pe.转偏移(当前) + 16]
        else:
            break
    if 码[0] == 0xB8 and 码[5] == 0xC3:                       # mov eax, imm32 ; ret
        址 = struct.unpack_from("<I", 码, 1)[0]
        形式.append("mov eax, 0x%08x; ret" % 址)
    elif 码[:2] == b"\x8d\x05":                              # lea eax, [abs32]
        址 = struct.unpack_from("<I", 码, 2)[0]
        形式.append("lea eax, [0x%08x]" % 址)
    elif 码[0] == 0xA1:   # mov eax,[abs32]：取内存槽里的指针，不是返回静态结构首址
        raise 解析错误("形式非「返回静态结构首址」：%s · mov eax,[0x%08x]"
                    % (" · ".join(形式), struct.unpack_from("<I", 码, 1)[0]))
    else:
        raise 解析错误("无法判定返回值形式，机器码前 8 字节：%s（不猜）" % 码[:8].hex(" "))
    结构rva = pe.取址(址)
    if 结构rva is None:
        raise 解析错误("返回值 0x%x 为 NULL" % 址)
    return 序号, 导出rva, 码[:8], 结构rva, " · ".join(形式)

def 读字段(pe, 基偏移, 表):
    """返回 [(偏移, 宽, 名, 类, 值, 可读串)]。"""
    out = []
    for 偏移, 宽, 名, 类 in 表:
        p = 基偏移 + 偏移
        if p + 宽 > len(pe.d):
            raise 解析错误("字段 %s @+0x%x 越界" % (名, 偏移))
        if 类 in 数值格式:
            值 = struct.unpack_from(数值格式[类], pe.d, p)[0]
            读 = "%r" % 值 if 类 == "f64" else "%d" % 值
        else:                                                # ptr / str
            值 = pe.读u32(p); 读 = "0x%08x" % 值
            if 类 == "str" and 值:
                读 += " → %r" % pe.读串(值)     # 指向不合法即抛错：fail-closed，不编串
        out.append((偏移, 宽, 名, 类, 值, 读))
    return out

def 解表(pe, 数, 表址, 项大小, 字段表):
    if 数 <= 0:
        return []
    if not 表址:
        raise 解析错误("声明有 %d 项但表指针为 0 —— 不自洽，不编表" % 数)
    基 = pe.转偏移(pe.取址(表址))
    项 = []
    for i in range(数):
        o = 基 + i * 项大小
        if o + 项大小 > len(pe.d):
            raise 解析错误("表项第 %d 项越界（表 @RVA 0x%x）" % (i, pe.取址(表址)))
        项.append((i, o, {f[2]: (f[4], f[5]) for f in 读字段(pe, o, 字段表)}))
    return 项

def 探物理槽数(pe, d):
    """物理槽数**只是观察**，不参与解码。仅在「两指针都在 · 函数表在命令表之后 ·
    间距是 36 的整数倍」三条同时成立时才有定义；否则 None（未判），绝不硬凑。"""
    if not d["m_nCmdCount"] and not d["m_pBeginCmdInfo"]:
        return 0, []
    if not (d["m_pCmdsFunc"] and d["m_pBeginCmdInfo"]):
        return None, []
    起, 止 = pe.取址(d["m_pBeginCmdInfo"]), pe.取址(d["m_pCmdsFunc"])
    if 止 <= 起 or (止 - 起) % 命令项大小:
        return None, []
    槽数 = (止 - 起) // 命令项大小
    多 = []
    for i in range(d["m_nCmdCount"], min(槽数, d["m_nCmdCount"] + 16)):
        try:
            f = {x[2]: (x[4], x[5]) for x in 读字段(pe, pe.转偏移(起 + i * 命令项大小), 命令字段)}
            多.append((i, f["m_szName"][0], f["m_szName"][1]))
        except 解析错误:
            多.append((i, 0, "<解不出命令项>"))
    return 槽数, 多

def 计数判定(r):
    """齐 / 不齐 / 不适用。**不齐必须有证据**：表外那一槽得真解出一个命令名指针。"""
    n, (槽数, 多) = r["字典"]["m_nCmdCount"], r["物理槽"]
    if 槽数 is None:
        return "不适用"
    if 槽数 == n:
        return "齐"
    return "不齐" if (多 and 多[0][1]) else "不适用（间距不是表扩展）"

def 反解(路径):
    with open(路径, "rb") as fh:
        数据 = fh.read()
    pe = PE(数据, 路径)
    序号, 导出rva, 机器码, 结构rva, 形式 = 解接缝(pe)
    so = pe.转偏移(结构rva)
    if so + 库信息大小 > len(pe.d):
        raise 解析错误("结构 @RVA 0x%x 越界（需 %d 字节）" % (结构rva, 库信息大小))
    字段 = 读字段(pe, so, 库信息字段)
    d = {f[2]: f[4] for f in 字段}
    if d["m_dwLibFormatVer"] != 库格式号:
        raise 解析错误("格式号 0x%08x != 0x%08x —— 这不是易语言支持库的 LIB_INFO，拒绝解读"
                    % (d["m_dwLibFormatVer"], 库格式号))
    命令 = 解表(pe, d["m_nCmdCount"], d["m_pBeginCmdInfo"], 命令项大小, 命令字段)
    函数 = []
    if d["m_pCmdsFunc"] and d["m_nCmdCount"]:
        fo = pe.转偏移(pe.取址(d["m_pCmdsFunc"]))
        函数 = list(struct.unpack_from("<%dI" % d["m_nCmdCount"], pe.d, fo))
    return {"路径": 路径, "字节数": len(数据), "pe": pe, "序号": 序号, "导出rva": 导出rva, "机器码": 机器码,
            "形式": 形式, "结构rva": 结构rva, "字段": 字段, "字典": d, "命令": 命令, "函数": 函数,
            "物理槽": 探物理槽数(pe, d)}

def 出报告(r):
    d, pe = r["字典"], r["pe"]
    基 = pe.转偏移(r["结构rva"])
    print("=" * 78 + "\n样本 %s（%d 字节）｜ 机器 0x%04x · %d 节 · 魔数 0x%x(PE32) · ImageBase 0x%08x"
          % (r["路径"], r["字节数"], pe.机器, pe.节数, pe.魔数, pe.基址))
    print("  节：" + " ".join("%s[rva %x vsz %x raw %x]" % (a, b, c, e) for a, b, c, e, _ in pe.节))
    print("① 导出 %s：序号 %d · RVA 0x%x · 前 8 字节 %s ｜ 返回值形式：%s"
          % (导出名.decode(), r["序号"], r["导出rva"], r["机器码"].hex(" "), r["形式"]))
    print("   静态结构 RVA 0x%x（文件偏移 0x%x）；原始字节：" % (r["结构rva"], 基))
    print("     " + pe.d[基:基 + 库信息大小].hex(" "))
    print("② LIB_INFO 逐字段（偏移 · 宽 · 名 · 值 · 可读）：")
    for 偏移, 宽, 名, 类, 值, 读 in r["字段"]:
        print("   +0x%02x %2d  %-24s 0x%08x  %s" % (偏移, 宽, 名, 值 & 0xFFFFFFFF, 读))
    print("   m_dwState=0x%08x → %s" % (d["m_dwState"], " · ".join(
        v for k, v in 库状态位.items() if d["m_dwState"] & (1 << k)) or "（0，无位）"))
    print("③ 字符串表（结构里的 str 类指针指向的串）：")
    for 偏移, 宽, 名, 类, 值, 读 in r["字段"]:
        if 类 == "str" and 值:
            print("   +0x%02x  %-22s 0x%08x  %s" % (偏移, 名, 值, 读.split("→", 1)[-1].strip()))
    if d["m_nCategoryCount"]:
        o, 类 = pe.转偏移(pe.取址(d["m_szzCategory"])), []
        for _ in range(d["m_nCategoryCount"]):
            尾 = pe.d.find(b"\0", o); 类.append(pe.d[o:尾].decode("gbk", "replace")); o = 尾 + 1
        print("   类别表（m_nCategoryCount=%d）：%s" % (d["m_nCategoryCount"], 类))
    print("④ 命令表：表项 %d 字节 · 声明数 m_nCmdCount=%d · 物理槽数(观察，非解码依据)=%s"
          % (命令项大小, d["m_nCmdCount"], r["物理槽"][0]))
    print("   表项逐字段偏移：" + " · ".join("%s@+0x%x/%dB" % (n, o, w) for o, w, n, _ in 命令字段))
    for i, o, f in r["命令"]:
        print("   [%2d] @RVA 0x%x %-14s %-24s cat=%2d state=0x%04x(%s) ret=0x%08x argc=%d func=%s"
              % (i, pe.取址(d["m_pBeginCmdInfo"]) + i * 命令项大小, f["m_szName"][1], f["m_szEgName"][1],
                 f["m_shtCategory"][0], f["m_wState"][0], "·".join(
                     v for k, v in 命令状态位.items() if f["m_wState"][0] & (1 << k)) or "无",
                 f["m_dtRetValType"][0], f["m_nArgCount"][0],
                 ("0x%08x" % r["函数"][i]) if i < len(r["函数"]) else "<无>"))
        for j, _, g in 解表(pe, f["m_nArgCount"][0], f["m_pBeginArgInfo"][0], 参数项大小, 参数字段):
            print("        参数%d %-12s type=0x%08x state=0x%08x default=%d"
                  % (j, g["m_szName"][1], g["m_dtType"][0], g["m_dwState"][0], g["m_nDefault"][0]))
    for i, _, 读 in r["物理槽"][1]:
        print("   ⚠ 声明数与物理槽数不齐：表外第 %d 槽仍是命令项：%s" % (i, 读))
    print("⑤ 常量表：声明数 m_nLibConstCount=%d" % d["m_nLibConstCount"])
    for i, _, g in 解表(pe, d["m_nLibConstCount"], d["m_pLibConst"], 常量项大小, 常量字段):
        print("   [%d] name=%s reserved=%s type=%s text=%s value=%s" % (
            i, g["m_szName"][1], g["m_shtReserved"][1], g["m_shtType"][1], g["m_szText"][1], g["m_dbValue"][1]))
    print("⑥ 类型表：声明数 m_nDataTypeCount=%d" % d["m_nDataTypeCount"])
    for i, _, g in 解表(pe, d["m_nDataTypeCount"], d["m_pDataType"], 类型项大小, 类型字段):
        下标 = []
        if g["m_pnCmdsIndex"][0] and g["m_nCmdCount"][0]:
            try:
                下标 = list(struct.unpack_from("<%di" % g["m_nCmdCount"][0], pe.d,
                            pe.转偏移(pe.取址(g["m_pnCmdsIndex"][0]))))
            except 解析错误:
                下标 = ["<指向不合法>"]
        print("   [%d] %s eg=%s state=0x%08x 成员命令下标=%s 事件=%d 属性=%d 元素=%d"
              % (i, g["m_szName"][1], g["m_szEgName"][1], g["m_dwState"][0], 下标,
                 g["m_nEventCount"][0], g["m_nPropertyCount"][0], g["m_nElementCount"][0]))
    print()

# ── 自测：反向样本（判据可信性） ──
def 自测(样本="/tmp/易语言源码/lib/shellEx.fne"):
    好 = open(样本, "rb").read()
    例 = [("空文件", b""), ("只有 DOS 头 0x40", 好[:0x40]), ("截断到 PE 头中间", 好[:0xC8]), ("截断到节表中间", 好[:0x1A0]),
          ("整份砍掉后半", 好[:len(好) // 2]), ("随机字节流", bytes(range(256)) * 4), ("无 MZ 签名", b"ZZ" + 好[2:])]
    try:
        pe = PE(好)
        结构偏移 = pe.转偏移(解接缝(pe)[3])
        改例 = [("格式号改成 0", 0x00, b"\0\0\0\0"), ("命令数改成 99（表外）", 0x64, (99).to_bytes(4, "little")),
               ("命令表指针清 0 而计数非 0", 0x68, b"\0\0\0\0"), ("GUID 指针指到镜像外", 0x04, b"\xff\xff\xff\xff"),
               ("命令表指针指向文件尾外", 0x68, (pe.基址 + 0x700000).to_bytes(4, "little"))]
        for 名, 处, 值 in 改例:
            b = bytearray(好); b[结构偏移 + 处:结构偏移 + 处 + 4] = 值
            例.append((名, bytes(b)))
        b = bytearray(好); o = pe.转偏移(解接缝(pe)[1]); b[o:o + 6] = b"\x0f\x0b\x0f\x0b\x0f\x0b"
        例.append(("GetNewInf 机器码换成 ud2", bytes(b)))
    except 解析错误 as ex:
        print("警告：好样本自己就解不动（%s），反向样本只跑通用那批" % ex)
    print("自测：喂 %d 个坏样本，断言「报错且不产出字段」" % len(例))
    失败 = 0
    for 名, 数据 in 例:
        try:
            pe = PE(数据, 名)
            d = {f[2]: f[4] for f in 读字段(pe, pe.转偏移(解接缝(pe)[3]), 库信息字段)}
            if d["m_dwLibFormatVer"] != 库格式号:
                raise 解析错误("格式号不符 0x%08x" % d["m_dwLibFormatVer"])
            解表(pe, d["m_nCmdCount"], d["m_pBeginCmdInfo"], 命令项大小, 命令字段)
            print("  ✗ %-26s 竟然解析成功 —— 假绿" % 名); 失败 += 1
        except 解析错误 as ex:
            print("  ✓ %-26s 报错：%s" % (名, ex))
        except (struct.error, IndexError, ValueError, OverflowError, TypeError) as ex:
            print("  ✗ %-26s 抛了非解析错误（%s: %s）" % (名, type(ex).__name__, ex)); 失败 += 1
    try:
        print("  ✓ 正向样本 %s 解析成功（命令 %d 条）" % (os.path.basename(样本), len(反解(样本)["命令"])))
    except 解析错误 as ex:
        print("  ✗ 正向样本反而失败：%s" % ex); 失败 += 1
    print("自测结论：%s（失败 %d）" % ("通过" if 失败 == 0 else "不通过", 失败))
    return 1 if 失败 else 0

def 扫全部(目录):
    print("全树 %s：导出面 · 声明数 m_nCmdCount vs 物理槽数 (funcPtr-cmdPtr)/%d" % (目录, 命令项大小))
    print("%-24s %5s %6s %8s  %s" % ("文件", "导出", "声明", "物理槽", "判"))
    不齐, 未判, 分布, 总 = [], [], {}, 0
    for p in sorted(glob.glob(os.path.join(目录, "**", "*.fne"), recursive=True)):
        总 += 1
        try:
            ex = PE(open(p, "rb").read(), p).导出(); 分布[len(ex)] = 分布.get(len(ex), 0) + 1
            r = 反解(p); n = r["字典"]["m_nCmdCount"]; s, 多 = r["物理槽"]; 判 = 计数判定(r)
            print("%-24s %5d %6d %8s  %s" % (os.path.basename(p), len(ex), n, "不适用" if s is None else s, 判))
            if 判 == "不齐":
                不齐.append((os.path.basename(p), n, s, 多[0][2]))
        except 解析错误 as ex:
            print("%-24s %5s %6s %8s  未判：%s" % (os.path.basename(p), "?", "-", "-", str(ex)[:34]))
            未判.append(os.path.basename(p))
    print("共 %d 个 .fne · 齐 %d · 不齐 %d · 未判 %d · 导出个数分布 %s"
          % (总, 总 - len(不齐) - len(未判), len(不齐), len(未判), dict(sorted(分布.items()))))
    print("不齐清单（文件, 声明数, 物理槽数, 表外第一槽名）：%s" % 不齐)
    print("未判清单：%s" % 未判)
    return 0

def main():
    ap = argparse.ArgumentParser(description="GetNewInf 接缝静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/lib/shellEx.fne")
    ap.add_argument("--目录", default="/tmp/易语言源码")
    ap.add_argument("--全部", action="store_true"); ap.add_argument("--自测", action="store_true")
    a = ap.parse_args()
    if not a.自测 and not a.全部:
        出报告(反解(a.样本)); return 0
    return (自测(a.样本) if a.自测 else 0) | (扫全部(a.目录) if a.全部 else 0)


if __name__ == "__main__":
    sys.exit(main())
