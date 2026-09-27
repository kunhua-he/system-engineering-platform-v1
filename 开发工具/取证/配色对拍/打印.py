# -*- coding: utf-8 -*-
"""打印 —— 把读数打成可读报告（原 `配色对拍.py::打印`，纯搬家）。"""


def 打印(读数):
    w, h = 读数["尺寸"]
    print(f"=== {读数['路径']} ===")
    print(f"  尺寸 {w}x{h} · 采样色数 {读数['色数']}")
    print(f"  纯黑 {读数['黑']} px（{读数['黑占比']:.2f}%）· 强边 {读数['强边']} · 斜面 {读数['斜面']}")
    print("  前 8 众数色：")
    for c, n in 读数["众数"]:
        print(f"    rgb{c}  {n * 4} px  ({n * 4 * 100 // (w * h)}%)")
    print("  黑像素最多的 14 行：")
    for n, y in sorted(((n, y) for y, n in enumerate(读数["逐行黑"])), reverse=True)[:14]:
        print(f"    y={y:>3}  黑 {n:>4}  ({n * 100 // w}%)")
    print()
