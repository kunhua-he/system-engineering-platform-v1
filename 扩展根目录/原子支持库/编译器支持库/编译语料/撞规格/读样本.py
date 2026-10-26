"""读样本 —— 读 `真文本/*.txt` → [(样本名, 原文(GBK bytes), 层级)]。"""

import os


def 读样本(DST):
    """读 `真文本/*.txt`（UTF-8，由 挖真文本.py 从 GBK 原文转来）。"""
    rows = []
    for 文件名 in sorted(os.listdir(DST)):
        if not 文件名.endswith(".txt"):
            continue
        # newline="" 关掉通用换行翻译，否则 \r\n 会被悄悄折成 \n（换行读数就废了）
        with open(os.path.join(DST, 文件名), encoding="utf-8", newline="") as fh:
            text = fh.read()
        tier = 文件名.split("-")[0]
        rows.append((文件名, text.encode("gbk"), tier))
    return rows
