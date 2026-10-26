# -*- coding: utf-8 -*-
"""挖真文本 · 行判定 —— GBK 可解 / 行长 / 控制字符 / 声明行计数 / 行分类与边界扩张。"""
from .挖出落点 import 控制字符, 声明行正则, 最大行长, 版本锚


# ── 行工具 ────────────────────────────────────────────────────────────────
def GBK合规(原文):
    try:
        原文.decode("gbk")
        return True
    except UnicodeDecodeError:
        return False


def 检查候选文本(候选字节):
    probs = []
    nb = blk = 0
    for 序号, ln in enumerate(候选字节.split(b"\n")):
        if ln.endswith(b"\r"):
            ln = ln[:-1]
        if len(ln) > 最大行长:
            probs.append(f"行{序号} 超长 {len(ln)}")
        elif any(单字符 in ln for 单字符 in 控制字符):
            probs.append(f"行{序号} 含控制字符")
        elif not GBK合规(ln):
            probs.append(f"行{序号} 非 GBK")
        elif ln.strip():
            nb += 1
        else:
            blk += 1
    return (not probs), probs, nb, blk


def 声明行数(候选字节):
    声明数, 分组声明数 = 0, {}
    for ln in 候选字节.split(b"\n"):
        if ln.endswith(b"\r"):
            ln = ln[:-1]
        if not GBK合规(ln):
            continue
        正则匹配 = 声明行正则.match(ln.decode("gbk"))
        if 正则匹配:
            声明数 += 1
            分组声明数[正则匹配.group(1)] = 分组声明数.get(正则匹配.group(1), 0) + 1
    return 声明数, 分组声明数


def 行分类(raw):
    if len(raw) > 最大行长:
        return "OTHER"
    if not raw.strip():
        return "BLANK"
    if any(单字符 in raw for 单字符 in 控制字符) or not GBK合规(raw):
        return "OTHER"
    行文 = raw.decode("gbk")
    st = 行文.lstrip(" ")
    if st.startswith("'"):
        return "SOURCE"
    if st.startswith("."):
        return "SOURCE" if len(st) > 1 and (st[1].isalpha() or st[1] == "_" or ord(st[1]) > 127) else "OTHER"
    if st and (st[0].isalpha() or st[0] == "_" or ord(st[0]) > 127 or st[0] in '#"'):
        return "SOURCE"
    return "OTHER"


def 定位行(字节流, 字节位置):
    ls = 字节流.rfind(b"\n", 0, 字节位置) + 1
    le = 字节流.find(b"\n", 字节位置)
    nxt = len(字节流) if le < 0 else le + 1
    行尾 = le if le >= 0 else len(字节流)
    if 行尾 > ls and 字节流[行尾 - 1:行尾] == b"\r":
        行尾 -= 1
    return ls, 行尾, nxt


def 扩张边界(字节流, 锚点):
    """按行形状从锚点向前扩张（弱证据用）。"""
    ls, le, nxt = 定位行(字节流, 锚点)
    锚起点 = ls if 字节流[ls:ls + len(版本锚)] == 版本锚 else 锚点
    区间终点 = nxt
    while 区间终点 < len(字节流):
        _, 行尾, 下一行起 = 定位行(字节流, 区间终点)
        if 行分类(字节流[区间终点:行尾]) == "OTHER":
            break
        区间终点 = 下一行起
    if 锚起点 == ls:
        while 锚起点 >= 2:
            pls, ple, _ = 定位行(字节流, 锚起点 - 2)
            if pls >= 锚起点 or 行分类(字节流[pls:ple]) == "OTHER":
                break
            锚起点 = pls
    return 锚起点, 区间终点
