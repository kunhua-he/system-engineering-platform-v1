# -*- coding: utf-8 -*-
"""形状 —— fail-closed 异常与只读 PE32 解析器（原 `接缝反解.py::解析错误/PE`，纯搬家）。"""

import struct


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
