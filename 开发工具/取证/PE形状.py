# -*- coding: utf-8 -*-
"""PE形状 —— fail-closed 异常与**唯一一份**只读 PE32 解析器。

**为什么单独一件**：`接缝反解/形状.py` 与 `界面反解/形状.py` 原本**各养一份** PE 解析器
（两件的文件头都写着「纯搬家」—— 各自从自身的老脚本搬的）。那是同一条腿的第二份实现：
同一件事两套代码，一处修了另一处不知道，实测两件已经**各自长出了对方没有的方法**
（一份有 `取址`/`读串`/`导出`，另一份有 `读双字节`/`节区间`）。本件把两份合成**一份并集**：

| 谁 | 要哪几个方法 |
|---|---|
| 接缝反解 | `转偏移` · `取址` · `读四字节` · `读串` · `导出` |
| 界面反解 | `转偏移` · `读双字节` · `读四字节` · `节区间` · `资源目录` |

**唯一的行为差异**是「没有资源目录就抛」：接缝反解要扫**整个库目录**（`.fne` 未必都带资源目录）
⇒ 不能无条件抛。故把它从构造器里挪出来做成 `要资源目录()`，由界面反解自身调
（fail-closed 一点没变，只是**谁来决定要不要**清楚了）。

放置位置：`开发工具/取证/` 下（与 `接缝反解.py` / `界面反解.py` 同级）—— 两个子包都能
`from PE形状 import …`（跑入口时脚本所在目录已在 `sys.path` 上）。
"""

import struct


class 解析错误(Exception):
    """字节不支持某种解读时抛这个 —— 绝不返回编出来的字段（fail-closed）。"""


class PE:
    """只读 PE32 解析器。任何越界都抛 `解析错误`，不做「尽量猜」。"""

    def __init__(self, 数据, 路径="<内存>"):
        self.路径, self.原始字节 = 路径, 数据
        if len(数据) < 0x40:
            raise 解析错误("文件短于 64 字节，DOS 头都不完整")
        if 数据[:2] != b"MZ":
            raise 解析错误("无 MZ 签名，不是 PE 文件")
        self.PE头偏移 = struct.unpack_from("<I", 数据, 0x3C)[0]
        if self.PE头偏移 + 24 > len(数据) or 数据[self.PE头偏移:self.PE头偏移 + 4] != b"PE\0\0":
            raise 解析错误("e_lfanew(0x%x) 越界或处无 PE\\0\\0 签名" % self.PE头偏移)
        self.机器, self.节数, _, _, _, self.可选头长, _ = struct.unpack_from(
            "<HHIIIHH", 数据, self.PE头偏移 + 4)
        if self.可选头长 == 0 or self.PE头偏移 + 24 + self.可选头长 > len(数据):
            raise 解析错误("可选头长度 %d 为 0 或越界（只剩 %d）"
                        % (self.可选头长, len(数据) - self.PE头偏移 - 24))
        self.魔数 = struct.unpack_from("<H", 数据, self.PE头偏移 + 24)[0]
        if self.魔数 != 0x10B:
            raise 解析错误("魔数 0x%x 不是 PE32（64 位布局未取证，拒绝猜）" % self.魔数)
        self.基址 = struct.unpack_from("<I", 数据, self.PE头偏移 + 24 + 28)[0]
        self.节 = []
        for 节序 in range(self.节数):
            节表项偏移 = self.PE头偏移 + 24 + self.可选头长 + 节序 * 40
            if 节表项偏移 + 40 > len(数据):
                raise 解析错误("节表第 %d 项越界" % 节序)
            节名 = 数据[节表项偏移:节表项偏移 + 8].rstrip(b"\0").decode("latin1")
            虚长, 虚址, 原长, 原址 = struct.unpack_from("<IIII", 数据, 节表项偏移 + 8)
            if 原址 + 原长 > len(数据):
                raise 解析错误("节 %s 原始数据越界（%d+%d > %d）"
                            % (节名, 原址, 原长, len(数据)))
            self.节.append((节名, 虚址, 虚长, 原址, 原长))
        if not self.节:
            raise 解析错误("节数为 0")
        # DataDirectory[2] = 资源目录。**只读出来，不在这里判空** —— 要不要有资源目录
        # 由调用方决定（见 `要资源目录`）。
        self.资源目录 = struct.unpack_from("<II", 数据, self.PE头偏移 + 24 + 96 + 2 * 8)

    def 要资源目录(self):
        """要求本件带资源目录；空的就抛（界面反解走这条 —— 它反解的就是资源）。"""
        if self.资源目录[0] == 0:
            raise 解析错误("DataDirectory[2] 为空：本文件无资源目录")
        return self.资源目录

    def 转偏移(self, rva):
        for 节名, 虚址, 虚长, 原址, 原长 in self.节:
            if 虚址 <= rva < 虚址 + max(虚长, 原长):
                文偏移 = 原址 + (rva - 虚址)
                if 文偏移 >= len(self.原始字节):
                    raise 解析错误("RVA 0x%x 映到文件外 0x%x" % (rva, 文偏移))
                return 文偏移
        raise 解析错误("RVA 0x%x 不在任何节里" % rva)

    def 取址(self, 绝对址):
        """把结构里存的指针（绝对地址）折成 RVA；0 → None。"""
        if 绝对址 == 0:
            return None
        if self.基址 <= 绝对址 < self.基址 + 0x40000000:
            return 绝对址 - self.基址
        if 绝对址 < len(self.原始字节):
            return 绝对址
        raise 解析错误("指针 0x%x 既不在镜像里也不像 RVA" % 绝对址)

    def 读双字节(self, 偏移):
        if 偏移 < 0 or 偏移 + 2 > len(self.原始字节):
            raise 解析错误("读双字节越界 @0x%x" % 偏移)
        return struct.unpack_from("<H", self.原始字节, 偏移)[0]

    def 读四字节(self, 偏移):
        if 偏移 < 0 or 偏移 + 4 > len(self.原始字节):
            raise 解析错误("读四字节越界 @0x%x" % 偏移)
        return struct.unpack_from("<I", self.原始字节, 偏移)[0]

    def 节区间(self, 名):
        """按节名取 `(原址, 原址+原长)`；没有这一节就抛。"""
        for 节名, 虚址, 虚长, 原址, 原长 in self.节:
            if 节名 == 名:
                return 原址, 原址 + 原长
        raise 解析错误("没有 %s 节" % 名)

    def 读串(self, 绝对址):
        """读以 NUL 结尾的 GBK 串；指针为 0 ⇒ None。"""
        rva = self.取址(绝对址)
        if rva is None:
            return None
        文偏移 = self.转偏移(rva)
        尾部 = self.原始字节.find(b"\0", 文偏移)
        if 尾部 < 0:
            raise 解析错误("0x%x 处的字符串没有 NUL 结尾" % 绝对址)
        return self.原始字节[文偏移:尾部].decode("gbk", "replace")

    def 导出(self):
        """读导出表 ⇒ `[(名, 序号, RVA)…]`；无导出目录就抛。"""
        目录 = struct.unpack_from("<II", self.原始字节, self.PE头偏移 + 24 + 96)
        if 目录[0] == 0:
            raise 解析错误("无导出目录（本库不是支持库？）")
        文偏移 = self.转偏移(目录[0])
        if 文偏移 + 40 > len(self.原始字节):
            raise 解析错误("导出目录越界")
        _, _, _, _, _, 基序, 函数数, 名字数, 函数表, 名字表, 序号表 = struct.unpack_from(
            "<IIHHIIIIIII", self.原始字节, 文偏移)
        if 函数数 == 0:
            raise 解析错误("导出函数数为 0")
        函数表项 = struct.unpack_from("<%dI" % 函数数, self.原始字节, self.转偏移(函数表))
        结果 = []
        for 序号 in range(名字数):
            串起 = self.转偏移(self.读四字节(self.转偏移(名字表) + 4 * 序号))
            名序 = struct.unpack_from("<H", self.原始字节, self.转偏移(序号表) + 2 * 序号)[0]
            if 名序 >= 函数数:
                raise 解析错误("名字序号 %d 超出函数数 %d" % (名序, 函数数))
            名尾 = self.原始字节.find(b"\0", 串起)
            结果.append((self.原始字节[串起:名尾], 基序 + 名序, 函数表项[名序]))
        return 结果
