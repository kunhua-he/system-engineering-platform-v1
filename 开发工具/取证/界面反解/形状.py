# -*- coding: utf-8 -*-
"""形状 —— fail-closed 异常与只读 PE32 解析器（原 `界面反解.py::解析错误/PE`，纯搬家）。"""

import struct


class 解析错误(Exception):
    """字节不支持某种解读时抛这个 —— 绝不返回编出来的字段。"""


class PE:
    def __init__(self, 数据, 路径="<内存>"):
        self.路径, self.原始字节 = 路径, 数据
        if len(数据) < 0x40:
            raise 解析错误("文件短于 64 字节，DOS 头都不完整")
        if 数据[:2] != b"MZ":
            raise 解析错误("无 MZ 签名，不是 PE 文件")
        self.PE头偏移 = struct.unpack_from("<I", 数据, 0x3C)[0]
        if self.PE头偏移 + 24 > len(数据) or 数据[self.PE头偏移:self.PE头偏移 + 4] != b"PE\0\0":
            raise 解析错误("e_lfanew(0x%x) 越界或处无 PE\\0\\0 签名" % self.PE头偏移)
        self.机器, self.节数, _, _, _, self.可选头长, _ = struct.unpack_from("<HHIIIHH", 数据, self.PE头偏移 + 4)
        if self.可选头长 == 0 or self.PE头偏移 + 24 + self.可选头长 > len(数据):
            raise 解析错误("可选头长度 %d 为 0 或越界（只剩 %d）"
                        % (self.可选头长, len(数据) - self.PE头偏移 - 24))
        self.魔数 = struct.unpack_from("<H", 数据, self.PE头偏移 + 24)[0]
        if self.魔数 != 0x10B:
            raise 解析错误("魔数 0x%x 不是 PE32；64 位资源目录布局未取证，拒绝猜" % self.魔数)
        self.基址 = struct.unpack_from("<I", 数据, self.PE头偏移 + 24 + 28)[0]
        self.节 = []
        for 节序 in range(self.节数):
            节表项偏移 = self.PE头偏移 + 24 + self.可选头长 + 节序 * 40
            if 节表项偏移 + 40 > len(数据):
                raise 解析错误("节表第 %d 项越界" % 节序)
            名 = 数据[节表项偏移:节表项偏移 + 8].rstrip(b"\0").decode("latin1")
            虚长, 虚址, 原长, 原址 = struct.unpack_from("<IIII", 数据, 节表项偏移 + 8)
            if 原址 + 原长 > len(数据):
                raise 解析错误("节 %s 原始数据越界（%d+%d > %d）" % (名, 原址, 原长, len(数据)))
            self.节.append((名, 虚址, 虚长, 原址, 原长))
        if not self.节:
            raise 解析错误("节数为 0")
        self.资源目录 = struct.unpack_from("<II", 数据, self.PE头偏移 + 24 + 96 + 2 * 8)
        if self.资源目录[0] == 0:
            raise 解析错误("DataDirectory[2] 为空：本文件无资源目录")

    def 转偏移(self, rva):
        for 名, 虚址, 虚长, 原址, 原长 in self.节:
            if 虚址 <= rva < 虚址 + max(虚长, 原长):
                文偏移 = 原址 + (rva - 虚址)
                if 文偏移 >= len(self.原始字节):
                    raise 解析错误("RVA 0x%x 映到文件外 0x%x" % (rva, 文偏移))
                return 文偏移
        raise 解析错误("RVA 0x%x 不在任何节里" % rva)

    def 读u16(self, 偏移):
        if 偏移 < 0 or 偏移 + 2 > len(self.原始字节):
            raise 解析错误("读 u16 越界 @0x%x" % 偏移)
        return struct.unpack_from("<H", self.原始字节, 偏移)[0]

    def 读u32(self, 偏移):
        if 偏移 < 0 or 偏移 + 4 > len(self.原始字节):
            raise 解析错误("读 u32 越界 @0x%x" % 偏移)
        return struct.unpack_from("<I", self.原始字节, 偏移)[0]

    def 节区间(self, 名):
        for 节名, 虚址, 虚长, 原址, 原长 in self.节:
            if 节名 == 名:
                return 原址, 原址 + 原长
        raise 解析错误("没有 %s 节" % 名)
