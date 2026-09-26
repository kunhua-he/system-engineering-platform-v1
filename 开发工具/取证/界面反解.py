#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""界面反解 —— 纯静态字节解析 `e.exe` 的 PE 资源目录树与界面模板。

**只读字节，不加载、不注入、不执行**：全脚本只做 PE 头 / 节表 / 资源目录 /
资源模板的字节解析，没有 dlopen / ctypes / subprocess 触碰语料的路径；
`/tmp/易语言源码/` 只读，不写、不改 mtime。

反解对象与判据：`项目文档/设计文档/界面实测.md`。
  · 资源目录树（13 个顶层类型 → 逐条叶子 id 与字节大小）
  · 类型 4 菜单（MENUHEADER + MENUITEMTEMPLATE，UTF-16 文字）
  · 类型 5 对话框（DLGTEMPLATE / DLGTEMPLATEEX + 逐控件）
  · 类型 6 字符串表、类型 9 加速键、12/14 图标光标组、16 版本
  · 类型 10 RCDATA 与自定义类型 240 的压缩判定

    python3 开发工具/取证/界面反解.py                  # 默认 /tmp/易语言源码/e.exe
    python3 开发工具/取证/界面反解.py --样本 <path>
    python3 开发工具/取证/界面反解.py --自测           # 反向样本断言（必跑）

**一处与文档格式的实测偏差**：菜单项的 mtID 在本文件里对 `MF_END` 项**存在**
（MSDN 说「最后一项无 mtID」）。判据见界面实测.md §二 2.2。
"""

import argparse, math, os, struct, sys
from collections import Counter

# ── 常量：全部来自 PE/资源格式规范；名称只为出报告，不参与解码 ──
资源类型名 = {1: "CURSOR", 2: "BITMAP", 3: "ICON", 4: "MENU", 5: "DIALOG", 6: "STRING",
              7: "FONTDIR", 8: "FONT", 9: "ACCELERATOR", 10: "RCDATA", 11: "MESSAGETABLE",
              12: "GROUP_CURSOR", 14: "GROUP_ICON", 16: "VERSION", 17: "DLGINCLUDE",
              19: "PLUGPLAY", 20: "VXD", 21: "ANICURSOR", 22: "ANIICON", 23: "HTML",
              24: "MANIFEST"}
资源类型名[240] = "自定义240"
预定义控件类 = {0x80: "BUTTON", 0x81: "EDIT", 0x82: "STATIC", 0x83: "LISTBOX",
                0x84: "SCROLLBAR", 0x85: "COMBOBOX"}
菜单选项位 = {0x01: "MF_GRAYED", 0x02: "MF_DISABLED", 0x04: "MF_CHECKED", 0x08: "MF_POPUP_ALT",
              0x10: "MF_POPUP", 0x20: "MF_MENUBARBREAK", 0x40: "MF_MENUBREAK", 0x80: "MF_END"}
控件样式位 = {0x80000000: "WS_POPUP", 0x40000000: "WS_CHILD", 0x10000000: "WS_VISIBLE",
              0x08000000: "WS_DISABLED", 0x04000000: "WS_CLIPSIBLINGS", 0x02000000: "WS_CLIPCHILDREN",
              0x00800000: "WS_BORDER", 0x00200000: "WS_VSCROLL", 0x00100000: "WS_HSCROLL",
              0x00020000: "WS_GROUP", 0x00010000: "WS_TABSTOP"}
对话框样式位 = {0x80000000: "DS_MODALFRAME", 0x40000000: "DS_CONTROL", 0x00000040: "DS_SETFONT",
                0x00000001: "DS_ABSALIGN", 0x00000004: "DS_SYSMODAL", 0x00000100: "DS_NOIDLEMSG",
                0x00000400: "DS_3DLOOK", 0x00000800: "DS_FIXEDSYS", 0x00008000: "DS_CENTER",
                0x00010000: "DS_CENTERMOUSE", 0x00020000: "DS_CONTEXTHELP"}
按钮样式 = {0x00000000: "BS_PUSHBUTTON", 0x00000001: "BS_DEFPUSHBUTTON", 0x00000002: "BS_CHECKBOX",
            0x00000003: "BS_AUTOCHECKBOX", 0x00000004: "BS_RADIOBUTTON", 0x00000005: "BS_3STATE",
            0x00000006: "BS_AUTO3STATE", 0x00000007: "BS_GROUPBOX", 0x00000009: "BS_AUTORADIOBUTTON",
            0x0000000B: "BS_OWNERDRAW", 0x00000080: "BS_BITMAP", 0x000000A0: "BS_AUTOCHECKBOX|BS_LEFTTEXT"}
编辑样式 = {0x00000000: "ES_LEFT", 0x00000001: "ES_CENTER", 0x00000002: "ES_RIGHT",
            0x00000004: "ES_MULTILINE", 0x00000008: "ES_UPPERCASE", 0x00000020: "ES_AUTOVSCROLL",
            0x00000040: "ES_AUTOHSCROLL", 0x00000080: "ES_NOHIDESEL", 0x00000800: "ES_READONLY",
            0x00001000: "ES_WANTRETURN", 0x00002000: "ES_NUMBER", 0x00000100: "ES_PASSWORD"}
静态样式 = {0x00000000: "SS_LEFT", 0x00000001: "SS_CENTER", 0x00000002: "SS_RIGHT",
            0x00000003: "SS_ICON", 0x0000000E: "SS_BITMAP", 0x0000000B: "SS_SIMPLE",
            0x0000000C: "SS_LEFTNOWORDWRAP", 0x00000100: "SS_SUNKEN", 0x00000200: "SS_NOPREFIX"}
组合框样式 = {0x00000000: "CBS_SIMPLE", 0x00000001: "CBS_DROPDOWN", 0x00000002: "CBS_DROPDOWNLIST",
              0x00000003: "CBS_DROPDOWN|CBS_AUTOHSCROLL"}
虚拟键名 = {0x1B: "VK_ESCAPE", 0x21: "VK_PRIOR/PageUp", 0x22: "VK_NEXT/PageDown", 0x0D: "VK_RETURN",
            0x08: "VK_BACK", 0x09: "VK_TAB", 0x2E: "VK_DELETE", 0x2D: "VK_INSERT", 0x24: "VK_HOME",
            0x23: "VK_END", 0x25: "VK_LEFT", 0x26: "VK_UP", 0x27: "VK_RIGHT", 0x28: "VK_DOWN",
            0x70: "VK_F1", 0x71: "VK_F2", 0x72: "VK_F3", 0x77: "VK_F8", 0x78: "VK_F9"}
压缩签名 = [(b"\x78\x9c", "zlib 默认"), (b"\x78\x01", "zlib 最快"), (b"\x78\xda", "zlib 最优"),
            (b"\x1f\x8b\x08", "gzip"), (b"\xfd7zXZ\x00", "xz/lzma"), (b"PK\x03\x04", "zip"),
            (b"7z\xbc\xaf\x27\x1c", "7z"), (b"UPX0", "UPX"), (b"Rar!\x1a\x07", "rar"),
            (b"\x28\xb5\x2f\xfd", "zstd"), (b"BZh", "bzip2")]

class 解析错误(Exception):
    """字节不支持某种解读时抛这个 —— 绝不返回编出来的字段。"""

# ── PE：只读 PE32 解析；任何越界抛 解析错误，不做「尽量猜」 ──
class PE:
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
            raise 解析错误("魔数 0x%x 不是 PE32；64 位资源目录布局未取证，拒绝猜" % self.魔数)
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
        self.资源目录 = struct.unpack_from("<II", 数据, self.e + 24 + 96 + 2 * 8)
        if self.资源目录[0] == 0:
            raise 解析错误("DataDirectory[2] 为空：本文件无资源目录")

    def 转偏移(self, rva):
        for 名, 虚址, 虚长, 原址, 原长 in self.节:
            if 虚址 <= rva < 虚址 + max(虚长, 原长):
                o = 原址 + (rva - 虚址)
                if o >= len(self.d):
                    raise 解析错误("RVA 0x%x 映到文件外 0x%x" % (rva, o))
                return o
        raise 解析错误("RVA 0x%x 不在任何节里" % rva)

    def 读u16(self, 偏移):
        if 偏移 < 0 or 偏移 + 2 > len(self.d):
            raise 解析错误("读 u16 越界 @0x%x" % 偏移)
        return struct.unpack_from("<H", self.d, 偏移)[0]

    def 读u32(self, 偏移):
        if 偏移 < 0 or 偏移 + 4 > len(self.d):
            raise 解析错误("读 u32 越界 @0x%x" % 偏移)
        return struct.unpack_from("<I", self.d, 偏移)[0]

    def 节区间(self, 名):
        for n, 虚址, 虚长, 原址, 原长 in self.节:
            if n == 名:
                return 原址, 原址 + 原长
        raise 解析错误("没有 %s 节" % 名)

def 走资源树(pe):
    """递归到叶子，逐层校验：目录必须在 .rsrc 内、层数 ≤ 3、不重入、数据项不越界。"""
    起, 止 = pe.节区间(".rsrc")
    根 = pe.转偏移(pe.资源目录[0])
    if not (起 <= 根 < 止):
        raise 解析错误("资源目录根 RVA 0x%x 不在 .rsrc 内" % pe.资源目录[0])
    叶子, 见过 = [], set()

    def 串(base, off):
        o = base + off
        if o + 2 > len(pe.d):
            raise 解析错误("资源名字符串越界 @0x%x" % o)
        n = pe.读u16(o)
        if o + 2 + 2 * n > len(pe.d):
            raise 解析错误("资源名字符串长度 %d 越界 @0x%x" % (n, o))
        return pe.d[o + 2:o + 2 + 2 * n].decode("utf-16le", "replace")

    def 走(偏移, 路径, 层):
        if 层 > 3:
            raise 解析错误("资源目录层数 > 3（id 表/名字表/语言表三层为上限）")
        if not (起 <= 偏移 and 偏移 + 16 <= 止):
            raise 解析错误("资源目录节点 0x%x 不在 .rsrc[0x%x,0x%x) 内" % (偏移, 起, 止))
        if 偏移 in 见过:
            raise 解析错误("资源目录自指环 @0x%x" % 偏移)
        见过.add(偏移)
        具名数, ID数 = pe.读u16(偏移 + 12), pe.读u16(偏移 + 14)
        项数 = 具名数 + ID数
        if 项数 == 0 or 项数 > 0x4000:
            raise 解析错误("资源目录项数 %d 不合理 @0x%x" % (项数, 偏移))
        for i in range(项数):
            e = 偏移 + 16 + i * 8
            if e + 8 > 止:
                raise 解析错误("资源目录项第 %d 条越界 @0x%x" % (i, e))
            名域, 指域 = pe.读u32(e), pe.读u32(e + 4)
            if 名域 & 0x80000000:
                键 = 串(根, 名域 & 0x7FFFFFFF)
            else:
                键 = 名域
            子 = 根 + (指域 & 0x7FFFFFFF)
            if 指域 & 0x80000000:
                走(子, 路径 + [键], 层 + 1)
            else:
                if not (起 <= 子 and 子 + 16 <= 止):
                    raise 解析错误("资源数据项 0x%x 不在 .rsrc 内" % 子)
                rva, 大小, 代码页, _ = struct.unpack_from("<IIII", pe.d, 子)
                数据偏移 = pe.转偏移(rva)
                if 数据偏移 + 大小 > len(pe.d):
                    raise 解析错误("资源(type=%s id=%s) 数据越界：0x%x+%d" % (路径[0], 键, 数据偏移, 大小))
                全 = 路径 + [键]
                叶子.append({"路径": 全, "类型": 全[0], "id": 全[1], "语言": 全[-1],
                             "rva": rva, "大小": 大小, "代码页": 代码页,
                             "数据项偏移": 子, "数据偏移": 数据偏移})
    走(根, [], 0)
    if not 叶子:
        raise 解析错误("资源目录走到底没有叶子")
    for 叶 in 叶子:
        if len(叶["路径"]) != 3:
            raise 解析错误("资源叶子路径深 %d != 3（类型/id/语言）：目录结构非预期，不猜"
                        % len(叶["路径"]))
    return 叶子

# ── 菜单：MENUHEADER + MENUITEMTEMPLATE，文字是 UTF-16LE 带 NUL ──
def 解菜单(b, 资源id):
    if len(b) < 4:
        raise 解析错误("菜单 %s 短于 MENUHEADER" % 资源id)
    版本, 头大小 = struct.unpack_from("<HH", b, 0)
    if 版本 != 0 or 头大小 != 0:
        raise 解析错误("菜单 %s 版本=%d 头大小=%d：非标准 MENU 模板（MENUEX 未取证，不猜）"
                    % (资源id, 版本, 头大小))
    i, 深度, 项 = 4, 0, []
    while i < len(b):
        if i + 2 > len(b):
            raise 解析错误("菜单 %s 在 0x%x 处截断（读选项）" % (资源id, i))
        选 = struct.unpack_from("<H", b, i)[0]
        i += 2
        # 实测：本文件的 mtID 只在 MF_POPUP 项缺席（含 MF_END 项仍在）—— 见界面实测.md §二 2.2
        编号 = None
        if not (选 & 0x10):
            if i + 2 > len(b):
                raise 解析错误("菜单 %s 在 0x%x 处截断（读 mtID）" % (资源id, i))
            编号 = struct.unpack_from("<H", b, i)[0]
            i += 2
        起 = i
        while True:
            if i + 2 > len(b):
                raise 解析错误("菜单 %s 的文字没有 NUL 结尾（从 0x%x 起）" % (资源id, 起))
            if struct.unpack_from("<H", b, i)[0] == 0:
                i += 2
                break
            i += 2
        文字 = b[起:i - 2].decode("utf-16le")
        if any(ord(c) < 0x20 and c != "\t" for c in 文字):
            raise 解析错误("菜单 %s 的文字含控制字符（%r）：对齐判错" % (资源id, 文字[:12]))
        项.append({"层": 深度, "偏移": 起, "选项": 选, "编号": 编号, "文字": 文字})
        if 选 & 0x10:
            深度 += 1
        elif 选 & 0x80:
            深度 -= 1
            if 深度 < 0:
                raise 解析错误("菜单 %s 的 MF_END 下溢 @0x%x" % (资源id, i))
    if i != len(b):
        raise 解析错误("菜单 %s 消耗 %d != 声明 %d：模板边界不自洽" % (资源id, i, len(b)))
    if 深度 != 0:
        raise 解析错误("菜单 %s 结束时层深 %d != 0：MF_END 与 MF_POPUP 不配对" % (资源id, 深度))
    if not 项:
        raise 解析错误("菜单 %s 一项都没有" % 资源id)
    return 项

# ── 对话框：DLGTEMPLATE(18) 或 DLGTEMPLATEEX(26)；控件 18 或 24 字节 ──
def _变量数组(b, i, 资源id, 字段):
    """菜单/类/标题三个变长数组共用：0x0000 空、0xFFFF+序数、或 UTF-16 串。"""
    if i + 2 > len(b):
        raise 解析错误("对话框 %s 的 %s 数组越界 @0x%x" % (资源id, 字段, i))
    w = struct.unpack_from("<H", b, i)[0]
    if w == 0:
        return None, i + 2, "空"
    if w == 0xFFFF:
        if i + 4 > len(b):
            raise 解析错误("对话框 %s 的 %s 序数越界 @0x%x" % (资源id, 字段, i))
        return struct.unpack_from("<H", b, i + 2)[0], i + 4, "序数"
    起 = i
    while True:
        if i + 2 > len(b):
            raise 解析错误("对话框 %s 的 %s 串没有 NUL 结尾（从 0x%x 起）" % (资源id, 字段, 起))
        if struct.unpack_from("<H", b, i)[0] == 0:
            break
        i += 2
    return b[起:i].decode("utf-16le"), i + 2, "串"

def 解对话框(b, 资源id):
    if len(b) < 18:
        raise 解析错误("对话框 %s 短于 DLGTEMPLATE" % 资源id)
    扩展 = struct.unpack_from("<I", b, 0)[0] == 0xFFFF0001
    if 扩展:
        if len(b) < 26:
            raise 解析错误("对话框 %s 声明 DLGTEMPLATEEX 但短于 26 字节" % 资源id)
        _, 签名, 帮助id, 扩展样式, 样式, 控件数, x, y, cx, cy = struct.unpack_from("<HHIIIHhhhh", b, 0)
        if 签名 != 0xFFFF:
            raise 解析错误("对话框 %s 的 DLGTEMPLATEEX 签名 0x%x != 0xFFFF" % (资源id, 签名))
        i = 26
    else:
        样式, 扩展样式, 控件数, x, y, cx, cy = struct.unpack_from("<IIHhhhh", b, 0)
        帮助id = None
        i = 18
    菜单, i, _ = _变量数组(b, i, 资源id, "菜单")
    类, i, _ = _变量数组(b, i, 资源id, "类")
    标题, i, 标题形 = _变量数组(b, i, 资源id, "标题")
    字体 = None
    if 样式 & 0x40:
        if 扩展:
            if i + 6 > len(b):
                raise 解析错误("对话框 %s 的字体块越界" % 资源id)
            号, 粗细, 斜, 字符集 = struct.unpack_from("<HHBB", b, i)
            i += 6
            名, i, _ = _变量数组(b, i, 资源id, "字体名")
            字体 = {"号": 号, "粗细": 粗细, "斜体": 斜, "字符集": 字符集, "名": 名}
        else:
            if i + 2 > len(b):
                raise 解析错误("对话框 %s 的字号越界" % 资源id)
            号 = struct.unpack_from("<H", b, i)[0]
            i += 2
            名, i, _ = _变量数组(b, i, 资源id, "字体名")
            字体 = {"号": 号, "名": 名}
    控件 = []
    for n in range(控件数):
        i = (i + 3) & ~3
        if 扩展:
            if i + 24 > len(b):
                raise 解析错误("对话框 %s 第 %d 个控件头越界 @0x%x" % (资源id, n, i))
            头 = struct.unpack_from("<IIIhhhhI", b, i)
            帮助id2, 扩样, 样, x2, y2, cx2, cy2, id2 = 头
            i += 24
        else:
            if i + 18 > len(b):
                raise 解析错误("对话框 %s 第 %d 个控件头越界 @0x%x" % (资源id, n, i))
            样, 扩样, x2, y2, cx2, cy2, id2 = struct.unpack_from("<IIhhhhH", b, i)
            帮助id2 = None
            i += 18
        类2, i, 类形 = _变量数组(b, i, 资源id, "控件类")
        题2, i, 题形 = _变量数组(b, i, 资源id, "控件标题")
        if i + 2 > len(b):
            raise 解析错误("对话框 %s 第 %d 个控件的附加数据长度越界" % (资源id, n))
        附加 = struct.unpack_from("<H", b, i)[0]
        i += 2
        if i + 附加 > len(b):
            raise 解析错误("对话框 %s 第 %d 个控件的附加数据越界（%d 字节）" % (资源id, n, 附加))
        i += 附加
        if 附加 % 2:
            i += 1
        控件.append({"样式": 样, "扩展样式": 扩样, "帮助id": 帮助id2, "x": x2, "y": y2, "cx": cx2,
                     "cy": cy2, "id": id2, "类": 类2, "类形": 类形, "标题": 题2, "标题形": 题形,
                     "附加": 附加, "偏移": i})
    if i != len(b):
        raise 解析错误("对话框 %s 消耗 %d != 声明 %d：模板边界不自洽" % (资源id, i, len(b)))
    return {"扩展": 扩展, "帮助id": 帮助id, "样式": 样式, "扩展样式": 扩展样式, "控件数": 控件数,
            "x": x, "y": y, "cx": cx, "cy": cy, "菜单": 菜单, "类": 类, "标题": 标题,
            "标题形": 标题形, "字体": 字体, "控件": 控件}

def 类名(值, 形):
    if 形 == "空":
        return "（空）"
    if 形 == "序数":
        return "预定义#%d=%s" % (值, 预定义控件类.get(值, "未登记"))
    return str(值)

def 文字显示(值, 形):
    if 形 == "空":
        return ""
    if 形 == "序数":
        return "#%d（资源序数）" % 值
    return 值

# ── 字符串表：每块 ≤16 条，每条 WORD 字符数（含 NUL） ──
def 解字符串表(b, 块id):
    i, 串 = 0, []
    for k in range(16):
        if i >= len(b):
            break
        if i + 2 > len(b):
            raise 解析错误("字符串块 %s 第 %d 条长度字段越界 @0x%x" % (块id, k, i))
        L = struct.unpack_from("<H", b, i)[0]
        i += 2
        if L == 0:
            串.append("")
            continue
        if i + 2 * L > len(b):
            raise 解析错误("字符串块 %s 第 %d 条声明 %d 字符越界" % (块id, k, L))
        串.append(b[i:i + 2 * L].decode("utf-16le").rstrip("\0"))
        i += 2 * L
    if i != len(b):
        raise 解析错误("字符串块 %s 消耗 %d != 声明 %d" % (块id, i, len(b)))
    return 串

# ── 加速键：ACCEL 8 字节一条（fVirt, key, cmd, pad） ──
def 解加速键(b, 资源id):
    if not b or len(b) % 8:
        raise 解析错误("加速键 %s 长度 %d 不是 8 的整数倍" % (资源id, len(b)))
    out = []
    for i in range(0, len(b), 8):
        fVirt, key, cmd, 垫 = struct.unpack_from("<HHHH", b, i)
        if fVirt & 0xFF00:
            raise 解析错误("加速键 %s 第 %d 条 fVirt=0x%04x 高字节非 0：对齐判错" % (资源id, i // 8, fVirt))
        标 = []
        if fVirt & 0x01:
            标.append("FVIRTKEY")
        if fVirt & 0x02:
            标.append("FNOINVERT")
        if fVirt & 0x04:
            标.append("FSHIFT")
        if fVirt & 0x08:
            标.append("FCONTROL")
        if fVirt & 0x10:
            标.append("FALT")
        out.append({"fVirt": fVirt, "标志": "|".join(标) or "0", "键": key,
                    "键名": 虚拟键名.get(key, "0x%02x" % key), "命令": cmd})
    return out

# ── 图标组 / 光标组：ICONDIR + 条目（图标 1+1+1+1+2+2+4+2，光标 2+2+2+2+4+2） ──
def 解图标组(b, 资源id, 是光标):
    if len(b) < 6:
        raise 解析错误("%s组 %s 短于 ICONDIR" % ("光标" if 是光标 else "图标", 资源id))
    保留, 类型, 数 = struct.unpack_from("<HHH", b, 0)
    期望 = 2 if 是光标 else 1
    if 类型 != 期望:
        raise 解析错误("%s组 %s 的 type=%d != %d" % ("光标" if 是光标 else "图标", 资源id, 类型, 期望))
    if 数 == 0 or 6 + (14 if 是光标 else 14) * 数 > len(b):
        raise 解析错误("%s组 %s 声明 %d 条，条目区越界" % ("光标" if 是光标 else "图标", 资源id, 数))
    条 = []
    for i in range(数):
        o = 6 + 14 * i
        if 是光标:
            宽, 高, 平面, 位深, 字节, rid = struct.unpack_from("<HHHHIH", b, o)
            色数 = None
        else:
            宽, 高, 色数, _, 平面, 位深, 字节, rid = struct.unpack_from("<BBBBHHIH", b, o)
        if 字节 == 0:
            raise 解析错误("%s组 %s 第 %d 条字节数为 0" % ("光标" if 是光标 else "图标", 资源id, i))
        条.append({"宽": 宽, "高": 高, "色数": 色数, "平面": 平面, "位深": 位深, "字节": 字节, "id": rid})
    return {"类型": 类型, "条": 条}

# ── VERSION：VS_VERSIONINFO，键是 NUL 结尾 UTF-16，值按 4 字节对齐 ──
def 解版本(b, 资源id):
    out = []

    def 走(起, 止, 层):
        o = 起
        while o + 6 <= 止:
            长, 值长, 型 = struct.unpack_from("<HHH", b, o)
            if 长 == 0:
                break
            if 长 < 6 or o + 长 > 止:
                raise 解析错误("版本资源 %s 的子块长度 %d 越界 @0x%x" % (资源id, 长, o))
            k = o + 6
            while True:
                if k + 2 > o + 长:
                    raise 解析错误("版本资源 %s 的键没有 NUL 结尾 @0x%x" % (资源id, o))
                if struct.unpack_from("<H", b, k)[0] == 0:
                    break
                k += 2
            键 = b[o + 6:k].decode("utf-16le")
            v = (k + 2 + 3) & ~3
            字节数 = 值长 * 2 if 型 == 1 else 值长
            if v + 字节数 > o + 长:
                raise 解析错误("版本资源 %s 的子块 %r 的值越界" % (资源id, 键))
            if 型 == 1:
                out.append((层, 键, b[v:v + 字节数].decode("utf-16le").rstrip("\0")))
            else:
                out.append((层, 键, "<%d 字节二进制> %s" % (值长, b[v:v + 字节数][:12].hex(" "))))
            走(v + 字节数, o + 长, 层 + 1)     # 型 0 的根块也有子块（StringFileInfo/VarFileInfo）
            o = (o + 长 + 3) & ~3
    走(0, len(b), 0)
    if not out:
        raise 解析错误("版本资源 %s 没解出任何键" % 资源id)
    return out

# ── 压缩判定：熵 + 已知签名；判不出就报「不判」，不猜算法 ──
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

def 反解(路径):
    with open(路径, "rb") as fh:
        数据 = fh.read()
    return 反解数据(数据, 路径)

def 反解数据(数据, 路径="<内存>"):
    pe = PE(数据, 路径)
    叶子 = 走资源树(pe)
    分类 = {}
    for 叶 in 叶子:
        分类.setdefault(叶["类型"], []).append(叶)
    r = {"路径": 路径, "字节数": len(数据), "pe": pe, "叶子": 叶子, "分类": 分类,
         "菜单": {}, "对话框": {}, "字符串": {}, "加速键": {}, "图标组": {}, "版本": {},
         "其它": [], "图形": []}
    for 叶 in 叶子:
        类, rid = 叶["类型"], 叶["id"]
        已见 = {4: r["菜单"], 5: r["对话框"], 6: r["字符串"], 9: r["加速键"],
                12: r["图标组"], 14: r["图标组"], 16: r["版本"]}.get(类)
        if 已见 is not None and rid in 已见:
            raise 解析错误("资源 (type=%s id=%s) 重复：目录不自洽" % (类, rid))
        b = 数据[叶["数据偏移"]:叶["数据偏移"] + 叶["大小"]]
        if 类 == 4:
            r["菜单"][rid] = (叶, 解菜单(b, rid))
        elif 类 == 5:
            r["对话框"][rid] = (叶, 解对话框(b, rid))
        elif 类 == 6:
            r["字符串"][rid] = (叶, 解字符串表(b, rid))
        elif 类 == 9:
            r["加速键"][rid] = (叶, 解加速键(b, rid))
        elif 类 in (12, 14):
            r["图标组"][rid] = (叶, 解图标组(b, rid, 类 == 12))
        elif 类 == 16:
            r["版本"][rid] = (叶, 解版本(b, rid))
        elif 类 in (10, 240, 23):
            r["其它"].append((叶, 压缩判定(b)))
        elif 类 in (2, 3, 1):
            r["图形"].append((叶, 压缩判定(b)))
    return r

# ── 出报告 ──
def 出报告(r):
    pe, d = r["pe"], r["pe"].d
    print("=" * 96)
    print("样本 %s（%d 字节）｜ 机器 0x%04x · %d 节 · 魔数 0x%x(PE32) · ImageBase 0x%08x"
          % (r["路径"], r["字节数"], pe.机器, pe.节数, pe.魔数, pe.基址))
    print("  节：" + " ".join("%s[rva 0x%x vsz 0x%x raw 0x%x rsz 0x%x]" % (a, b, c, e, f)
                             for a, b, c, e, f in pe.节))
    print("  资源目录 RVA 0x%x 大小 0x%x" % pe.资源目录)

    print("\n① 资源目录树：%d 个顶层类型 · %d 条叶子 · 叶字节合计 %d（.rsrc raw %d）"
          % (len(r["分类"]), len(r["叶子"]), sum(x["大小"] for x in r["叶子"]), 0xba000))
    print("   %-6s %-14s %6s %10s %8s" % ("类型", "名", "条数", "总字节", "占叶字节"))
    总叶 = sum(x["大小"] for x in r["叶子"])
    for 类 in sorted(r["分类"], key=lambda x: (isinstance(x, str), x)):
        条 = r["分类"][类]
        总 = sum(x["大小"] for x in 条)
        print("   %-6s %-14s %6d %10d %7.2f%%" % (类, 资源类型名.get(类, "?"), len(条), 总, 100 * 总 / 总叶))
    print("   ── 逐条叶子 ──")
    for 类 in sorted(r["分类"], key=lambda x: (isinstance(x, str), x)):
        for 叶 in r["分类"][类]:
            print("   type %-4s id %-8s rva 0x%06x 大小 %7d 代码页 %5d 数据项偏移 0x%06x"
                  % (类, 叶["id"], 叶["rva"], 叶["大小"], 叶["代码页"], 叶["数据项偏移"]))

    print("\n② 菜单（类型 4）：%d 个资源 · %d 项" % (len(r["菜单"]), sum(len(v[1]) for v in r["菜单"].values())))
    for rid in sorted(r["菜单"]):
        叶, 项 = r["菜单"][rid]
        print("   ── 菜单 id=%s（RVA 0x%x · %d 字节 · %d 项）" % (rid, 叶["rva"], 叶["大小"], len(项)))
        for t in 项:
            print("      %s%s [opt=0x%04x %s] id=%-7s @0x%04x %r"
                  % ("  " * t["层"], ">" if t["选项"] & 0x10 else " ",
                     t["选项"], "|".join(名 for 位, 名 in 菜单选项位.items() if t["选项"] & 位) or "0",
                     ("0x%04x" % t["编号"]) if t["编号"] is not None else "  -   ",
                     t["偏移"], t["文字"]))

    print("\n③ 对话框（类型 5）：%d 个资源 · %d 个控件"
          % (len(r["对话框"]), sum(len(v[1]["控件"]) for v in r["对话框"].values())))
    for rid in sorted(r["对话框"]):
        叶, g = r["对话框"][rid]
        print("   ── 对话框 id=%s（RVA 0x%x · %d 字节 · %s · 控件 %d）"
              % (rid, 叶["rva"], 叶["大小"], "DLGTEMPLATEEX" if g["扩展"] else "DLGTEMPLATE", g["控件数"]))
        print("      style=0x%08x exStyle=0x%08x 位置(%d,%d) 尺寸 %dx%d 标题=%r 字体=%s 菜单=%s"
              % (g["样式"], g["扩展样式"], g["x"], g["y"], g["cx"], g["cy"],
                 g["标题"] if g["标题形"] != "序数" else "#%d" % g["标题"],
                 ("%s %dpt" % (g["字体"].get("名"), g["字体"]["号"])) if g["字体"] else "无",
                 g["菜单"] if g["菜单"] is not None else "无"))
        for j, c in enumerate(g["控件"]):
            print("      [%2d] cls=%-28s (%4d,%4d,%4d,%4d) id=%-6d style=0x%08x ex=0x%08x 标题=%r 附加=%d @0x%04x"
                  % (j, 类名(c["类"], c["类形"]), c["x"], c["y"], c["cx"], c["cy"], c["id"],
                     c["样式"], c["扩展样式"], 文字显示(c["标题"], c["标题形"]), c["附加"], c["偏移"]))

    print("\n④ 字符串表（类型 6）：%d 块 · %d 条非空"
          % (len(r["字符串"]), sum(1 for v in r["字符串"].values() for s in v[1] if s)))
    for bid in sorted(r["字符串"]):
        叶, 串 = r["字符串"][bid]
        print("   ── 块 %s（RVA 0x%x · %d 字节）" % (bid, 叶["rva"], 叶["大小"]))
        for j, s in enumerate(串):
            if s:
                print("      [%d] %r" % ((bid - 1) * 16 + 1 + j, s))

    print("\n⑤ 加速键（类型 9）：%d 个资源" % len(r["加速键"]))
    for rid in sorted(r["加速键"]):
        叶, 条 = r["加速键"][rid]
        for a in 条:
            print("   id=%s fVirt=0x%04x(%s) key=0x%02x(%s) cmd=0x%04x"
                  % (rid, a["fVirt"], a["标志"], a["键"], a["键名"], a["命令"]))

    print("\n⑥ 图标/光标组（类型 12/14）：%d 个资源" % len(r["图标组"]))
    for rid in sorted(r["图标组"]):
        叶, g = r["图标组"][rid]
        print("   id=%-8s type=%d 条数=%d" % (rid, g["类型"], len(g["条"])))
        for i, t in enumerate(g["条"]):
            print("      [%d] %dx%d 色数=%s 平面=%d 位深=%d 字节=%d 引用id=%d"
                  % (i, t["宽"], t["高"], t["色数"], t["平面"], t["位深"], t["字节"], t["id"]))

    print("\n⑦ 版本（类型 16）：")
    for rid in sorted(r["版本"]):
        for 层, 键, 值 in r["版本"][rid][1]:
            print("   %s%-22s = %s" % ("  " * 层, 键, 值))

    print("\n⑧ 压缩判定：RCDATA(10) / 自定义240 / HTML(23)")
    for 叶, c in r["其它"]:
        b = d[叶["数据偏移"]:叶["数据偏移"] + 叶["大小"]]
        print("   type %-4s id %-8s %7d 字节 熵=%.3f" % (叶["类型"], 叶["id"], 叶["大小"], c["熵"]))
        print("      容器=%s 头部压缩签名=%s" % (c["容器"] or "未识别", c["头部命中"] or "无"))
        print("      判定=%s" % c["判定"])
        if c["中段命中"]:
            print("      中段命中 %s —— 高熵数据里的巧合字节，不作压缩依据" % c["中段命中"])
        print("      头 32 字节：%s" % b[:32].hex(" "))
        if c["容器"] and c["容器"].startswith("ICONDIR"):
            # 这里嵌的是 16 字节 ICONDIRENTRY（组资源用的是 14 字节 GRPICONDIRENTRY）——见界面实测.md §六
            数 = struct.unpack_from("<H", b, 4)[0]
            for i in range(数):
                w, h, cc, _, pl, bc, sz, off = struct.unpack_from("<BBBBHHII", b, 6 + 16 * i)
                print("      图[%d] %dx%d 色数=%d 平面=%d 位深=%d 字节=%d 偏移=%d"
                      % (i, w, h, cc, pl, bc, sz, off))
    print("   ── 位图(2)/图标(3)/光标(1)：%d 条，均为原始像素，不逐条列熵" % len(r["图形"]))
    if r["图形"]:
        熵列 = [c["熵"] for _, c in r["图形"]]
        print("      熵区间 %.3f..%.3f · RT_BITMAP 是裸 DIB（无 BM 文件头），故容器识别 0 命中"
              % (min(熵列), max(熵列)))
    print("\n⑨ 不判（本脚本给不出、且不猜的项）：")
    print("   · 主窗体（IDE 主窗口）自身的控件树与面板尺寸：资源目录里没有窗体定义资源")
    print("   · 菜单/工具条的字体与配色：资源里只有对话框字体，无配色表")
    print("   · 自定义类型 240 每条记录前 8 字节的语义：无对照物")
    print("   · 类型 12/14 图标光标组里 高=2×宽 的成因：只报读数，不作解释")
    print()

# ── 自测：反向样本（判据可信性）；一个都不许「假绿」 ──
def 自测(样本="/tmp/易语言源码/e.exe"):
    好 = open(样本, "rb").read()
    例 = [("空文件", b""), ("只有 DOS 头 0x40", 好[:0x40]), ("截断到 PE 头中间", 好[:0x104]),
          ("无 MZ 签名", b"ZZ" + 好[2:]), ("整份砍掉后半", 好[:len(好) // 2]),
          ("随机字节流", bytes(range(256)) * 8)]
    try:
        pe = PE(好)
        叶 = 走资源树(pe)
        定位 = {}
        for x in 叶:
            定位.setdefault((x["类型"], x["id"]), x)
        def 改(数据, 处, 值):
            b = bytearray(数据)
            b[处:处 + len(值)] = 值
            return bytes(b)
        e = pe.e
        例.append(("可选头长度改 0", 改(好, e + 20, b"\0\0")))
        例.append(("节数改 0xFFFF", 改(好, e + 6, b"\xff\xff")))
        例.append(("资源目录 RVA 指到文件外", 改(好, e + 24 + 96 + 16, (0x700000).to_bytes(4, "little"))))
        例.append(("资源目录根项数改 0xFFFF", 改(好, pe.转偏移(pe.资源目录[0]) + 14, b"\xff\xff")))
        例.append(("资源目录项指到 .rsrc 外", 改(好, pe.转偏移(pe.资源目录[0]) + 16 + 4, (0x00000100).to_bytes(4, "little"))))
        节 = 定位[(4, 127)]
        m = 节["数据偏移"]
        例.append(("菜单版本号改成 1（MENUEX，本解不支持）", 改(好, m, b"\x01\x00")))
        例.append(("菜单末项文字去掉 NUL", 改(好, m + 节["大小"] - 2, b"\x41\x00")))
        例.append(("菜单资源声明长度砍半", 改(好, 节["数据项偏移"] + 4, (节["大小"] // 2).to_bytes(4, "little"))))
        dl = 定位[(5, 303)]
        d0 = dl["数据偏移"]
        例.append(("对话框控件数改成 9999", 改(好, d0 + 8, (9999).to_bytes(2, "little"))))
        例.append(("对话框资源声明长度砍掉 4 字节", 改(好, dl["数据项偏移"] + 4, (dl["大小"] - 4).to_bytes(4, "little"))))
        串 = 定位[(6, 2049)]
        例.append(("字符串块首条长度改成 0xFFFF", 改(好, 串["数据偏移"], b"\xff\xff")))
        加 = 定位[(9, 30997)]
        例.append(("加速键长度改成 25（非 8 倍数）", 改(好, 加["数据项偏移"] + 4, (25).to_bytes(4, "little"))))
        图 = 定位[(14, 126)]
        例.append(("图标组条数改成 9", 改(好, 图["数据偏移"] + 4, (9).to_bytes(2, "little"))))
        版 = 定位[(16, 1)]
        例.append(("版本资源首块长度改成 1", 改(好, 版["数据偏移"], b"\x01\x00")))
    except 解析错误 as ex:
        print("警告：好样本自己就解不动（%s），反向样本只跑通用那批" % ex)

    print("自测：喂 %d 个坏样本，断言「报错且不产出任何字段」" % len(例))
    失败 = 0
    for 名, 数据 in 例:
        try:
            r = 反解数据(数据, 名)
            总 = sum(len(v) for v in r["菜单"].values()) + sum(len(v[1]["控件"]) for v in r["对话框"].values())
            print("  ✗ %-34s 竟然解析成功（解出菜单/控件 %d 项）—— 假绿" % (名, 总))
            失败 += 1
        except 解析错误 as ex:
            print("  ✓ %-34s 报错：%s" % (名, str(ex)[:60]))
        except (struct.error, IndexError, ValueError, OverflowError, TypeError, UnicodeDecodeError) as ex:
            print("  ✗ %-34s 抛了非解析错误（%s: %s）" % (名, type(ex).__name__, str(ex)[:40]))
            失败 += 1
    try:
        r = 反解(样本)
        print("  ✓ 正向样本 %s 解析成功（菜单 %d 项 · 对话框 %d 个 · 控件 %d 个 · 字符串 %d 条）"
              % (os.path.basename(样本), sum(len(v[1]) for v in r["菜单"].values()), len(r["对话框"]),
                 sum(len(v[1]["控件"]) for v in r["对话框"].values()),
                 sum(1 for v in r["字符串"].values() for s in v[1] if s)))
    except 解析错误 as ex:
        print("  ✗ 正向样本反而失败：%s" % ex)
        失败 += 1
    print("自测结论：%s（坏样本 %d 个 · 失败 %d）" % ("通过" if 失败 == 0 else "不通过", len(例), 失败))
    return 1 if 失败 else 0

def main():
    ap = argparse.ArgumentParser(description="e.exe 界面资源静态反解（只读字节，不执行语料）")
    ap.add_argument("--样本", default="/tmp/易语言源码/e.exe")
    ap.add_argument("--自测", action="store_true")
    a = ap.parse_args()
    if a.自测:
        return 自测(a.样本)
    出报告(反解(a.样本))
    return 0

if __name__ == "__main__":
    sys.exit(main())
