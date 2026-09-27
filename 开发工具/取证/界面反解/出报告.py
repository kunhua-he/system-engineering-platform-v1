# -*- coding: utf-8 -*-
"""出报告 —— 把 `反解数据` 的读数打成九节文本（原 `界面反解.py::出报告`，纯搬家）。"""

import struct

from .常量 import 资源类型名, 菜单选项位
from .对话框 import 类名, 文字显示


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
