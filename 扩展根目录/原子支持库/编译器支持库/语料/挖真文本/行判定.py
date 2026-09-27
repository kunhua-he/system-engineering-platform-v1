# -*- coding: utf-8 -*-
"""挖真文本 · 行判定 —— GBK 可解 / 行长 / 控制字符 / 声明行计数 / 行分类与边界扩张。"""
from .常量 import CTRL, DECL_RE, MAXLINE, VER


# ── 行工具 ────────────────────────────────────────────────────────────────
def gbk_ok(x):
    try:
        x.decode("gbk")
        return True
    except UnicodeDecodeError:
        return False


def check_value(val):
    probs = []
    nb = blk = 0
    for i, ln in enumerate(val.split(b"\n")):
        if ln.endswith(b"\r"):
            ln = ln[:-1]
        if len(ln) > MAXLINE:
            probs.append(f"行{i} 超长 {len(ln)}")
        elif any(c in ln for c in CTRL):
            probs.append(f"行{i} 含控制字符")
        elif not gbk_ok(ln):
            probs.append(f"行{i} 非 GBK")
        elif ln.strip():
            nb += 1
        else:
            blk += 1
    return (not probs), probs, nb, blk


def decl_lines(val):
    n, cnt = 0, {}
    for ln in val.split(b"\n"):
        if ln.endswith(b"\r"):
            ln = ln[:-1]
        if not gbk_ok(ln):
            continue
        m = DECL_RE.match(ln.decode("gbk"))
        if m:
            n += 1
            cnt[m.group(1)] = cnt.get(m.group(1), 0) + 1
    return n, cnt


def classify(raw):
    if len(raw) > MAXLINE:
        return "OTHER"
    if not raw.strip():
        return "BLANK"
    if any(c in raw for c in CTRL) or not gbk_ok(raw):
        return "OTHER"
    s = raw.decode("gbk")
    st = s.lstrip(" ")
    if st.startswith("'"):
        return "SOURCE"
    if st.startswith("."):
        return "SOURCE" if len(st) > 1 and (st[1].isalpha() or st[1] == "_" or ord(st[1]) > 127) else "OTHER"
    if st and (st[0].isalpha() or st[0] == "_" or ord(st[0]) > 127 or st[0] in '#"'):
        return "SOURCE"
    return "OTHER"


def line_at(b, pos):
    ls = b.rfind(b"\n", 0, pos) + 1
    le = b.find(b"\n", pos)
    nxt = len(b) if le < 0 else le + 1
    e = le if le >= 0 else len(b)
    if e > ls and b[e - 1:e] == b"\r":
        e -= 1
    return ls, e, nxt


def expand(b, a):
    """按行形状从锚点向前扩张（弱证据用）。"""
    ls, le, nxt = line_at(b, a)
    start = ls if b[ls:ls + len(VER)] == VER else a
    end = nxt
    while end < len(b):
        _, le2, nxt2 = line_at(b, end)
        if classify(b[end:le2]) == "OTHER":
            break
        end = nxt2
    if start == ls:
        while start >= 2:
            pls, ple, _ = line_at(b, start - 2)
            if pls >= start or classify(b[pls:ple]) == "OTHER":
                break
            start = pls
    return start, end
