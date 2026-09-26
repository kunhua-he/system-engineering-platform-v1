#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""挖真文本（定稿）—— 把 `/tmp/易语言源码/` 里的真·易语言源码文本挖出来并落盘。

只读 `/tmp/易语言源码/`；只写 `语料/真文本/` 与本目录下的 `_挖出.json`。

一条命令复跑：  python3 挖真文本.py

────────────────────────────────────────────────────────────────────────────
为什么换判据（前两版都栽在同一处：靠行形状猜边界）
  v1 行分类太松 ⇒ `static_lib/lanyuku_static.lib` 出一段 295751 字节、只有 4 行的
     假样本（整块二进制恰好 GBK 可解）；
  v2/v3 行分类太紧 ⇒ `返回 (0)` 这类「列 0 无点语句」被判成 OTHER，真文本被腰斩
     （抖音解析2 的 D3D_HOOK_DEMO 真文本 7881 字节，v3 只切出 1701 字节）。

判据一（硬）：**边界不猜，读容器**。实测常量记录形状是

    \\x00 | u32 记录总长 | \\x04\\x00 | 名字 | \\x00\\x00 | [\\x1a] | u32 值长 | 值

  `u32 值长` 就在值首字节之前 4 字节。例：`D3D_HOOK_DEMO` 值首 159173，
  u32@159169 = 7881，159173+7881 = 167054，正好落在 `.常量 DEFAULT_QUALITY, "0"\\r\\n`
  之后 —— 逐字节对上。源码文本的值一律以 `.版本 2\\r\\n` 开头。

  硬证据四条全过：① 锚点 = `.版本 2\\r\\n`；② u32(a-4) = L 且 a+L 不越界；
  ③ 值 [a,a+L) 逐行「GBK 可解 + 无控制字符（\\t 除外）+ 行长 ≤512」全过；
  ④ 值内 ≥1 行 `.版本 2`、≥2 行列 0 声明关键字。

判据二（弱）：`.fne` / `.lib` / `.dll` / `.exe` 这些**不是容器**的文件里也嵌着源码文本
  （`ExuiKrnln/ExuiTool.exe`、`HPSocket_E.fne`、`e2ee.fne` …）。它们没有长度字段可读，
  只能按行形状向前扩张切边界 ⇒ **单独登记为弱证据**，不与硬证据混。

判据三（硬，边界由文件本身确定）：`samples/e8/ManyFiles/e8test3.txt` 整文件即源码文本。
"""
import hashlib
import json
import os
import re
import sys

SRC = "/tmp/易语言源码"
HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "真文本")
OUTJSON = os.path.join(HERE, "_挖出.json")

MAXLINE = 512
MIN_DECL = 2
VER = ".版本 2\r\n".encode("gbk")
VER_LINE = ".版本".encode("gbk")

DECL = ["版本", "支持库", "程序集", "子程序", "参数", "局部变量", "程序集变量", "全局变量",
        "数据类型", "成员", "常量", "DLL命令", "自定义数据类型", "组件", "图片资源",
        "声音资源", "窗口", "菜单", "易模块", "类", "方法", "初始化", "结束",
        "信息", "作者", "描述", "代码", "模块", "链接", "结构", "属性", "公开", "私有"]
DECL_RE = re.compile(r"^\.(" + "|".join(DECL) + r")(?![0-9A-Za-z_\u4e00-\u9fff])")

HDR = b"\x19\x73\x11\x15"
HDR_END = b"\x19\x73\x00"
CONST_RE = re.compile(rb"\x04\x00([\x20-\x7e\x81-\xfe]{1,60}?)\x00\x00", re.S)
CTRL = bytes(c for c in range(0x20) if c != 9) + b"\x7f"

# 已知内嵌源码文本、但不是容器的文件（弱证据扫描白名单；按扩展名不可能穷举，故显式列）
WEAK_FILES = [
    "lib/ExuiKrnln/ExuiTool.exe",
    "lib/HPSocket_E.fne", "static_lib/HPSocket_E_static.lib",
    "lib/e2ee.fne", "static_lib/e2ee_static.lib",
    "lib/iDraw/eTools/Plugin/E2EE自动添加订阅函数.dll",
    "lib/iDraw/eTools/Plugin/一键加入读写方法.dll",
    "lib/iDraw/eTools/ViewEcInfo.exe", "lib/eTools/ViewEcInfo.exe",
    "ecom/模块打开方式选中这个程序.exe",
]


# ── 容器段表 ──────────────────────────────────────────────────────────────
def seg_table(b):
    out, i = [], 0
    while True:
        j = b.find(HDR, i)
        if j < 0:
            break
        t = b[j + 0x0B]
        if b[j + 8:j + 0x0B] == HDR_END and b[j + 0x27:j + 0x2A] == HDR_END and t:
            nm = b[j + 0x0C:j + 0x27]
            key = bytes([0x73, 0x00, t, 0x19])
            dec = bytes(nm[k] ^ key[k % 4] for k in range(len(nm)))
            try:
                out.append((j, t, dec.split(b"\x00")[0].decode("gbk")))
            except UnicodeDecodeError:
                pass
        i = j + 1
    out.sort()
    return out


def seg_of(tab, off):
    cur = None
    for st, t, n in tab:
        if st <= off:
            cur = (st, t, n)
        else:
            break
    return cur


def const_name(b, off, back=4096):
    best = None
    for m in CONST_RE.finditer(b, max(0, off - back), off):
        try:
            best = (m.start(), m.group(1).decode("gbk"))
        except UnicodeDecodeError:
            continue
    return best


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


# ── 主流程 ────────────────────────────────────────────────────────────────
def main():
    hard, weak_ev, weak_json = [], [], []
    for dp, dn, fn in os.walk(SRC):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, SRC)
            try:
                b = open(p, "rb").read()
            except Exception:
                continue
            anchors, i = [], 0
            while True:
                j = b.find(VER, i)
                if j < 0:
                    break
                anchors.append(j)
                i = j + 1
            if not anchors:
                continue
            tab = seg_table(b)
            covered = []
            for a in anchors:
                L = int.from_bytes(b[a - 4:a], "little") if a >= 4 else 0
                if L < 16 or a + L > len(b):
                    continue
                raw = b[a:a + L]
                val = raw.rstrip(b"\x00")
                ok, probs, nb, blk = check_value(val)
                ver = sum(1 for ln in val.split(b"\n") if ln.startswith(VER_LINE))
                nd, kc = decl_lines(val)
                if not (ok and ver >= 1 and nd >= MIN_DECL):
                    continue
                st = seg_of(tab, a)
                cn = const_name(b, a)
                covered.append((a, a + len(val)))
                hard.append({
                    "file": rel, "anchor": a, "end": a + len(val), "bytes": len(val),
                    "declared_len": L, "trailing_nul": len(raw) - len(val),
                    "lines": nb + blk, "nonblank": nb,
                    "version_lines": ver, "decl_lines": nd, "decl_kinds": kc,
                    "seg_type": st[1] if st else None, "seg_name": st[2] if st else None,
                    "seg_start": st[0] if st else None,
                    "const_name": cn[1] if cn else None,
                    "const_off": cn[0] if cn else None,
                    "sha12": hashlib.sha256(val).hexdigest()[:12],
                    "text": val,
                })
            # 弱证据：白名单文件 + 行形状扩张
            if rel in WEAK_FILES:
                for a in anchors:
                    if any(s <= a < e for s, e in covered):
                        continue
                    s, e = expand(b, a)
                    val = b[s:e]
                    ok, probs, nb, blk = check_value(val)
                    ver = sum(1 for ln in val.split(b"\n") if ln.startswith(VER_LINE))
                    nd, kc = decl_lines(val)
                    if not (ok and ver >= 1 and nd >= MIN_DECL):
                        weak_json.append({"file": rel, "anchor": a, "bytes": e - s,
                                          "reason": "非良构/声明不足", "problems": probs[:4]})
                        continue
                    weak_ev.append({
                        "file": rel, "anchor": s, "end": e, "bytes": len(val),
                        "declared_len": None, "trailing_nul": 0,
                        "lines": nb + blk, "nonblank": nb,
                        "version_lines": ver, "decl_lines": nd, "decl_kinds": kc,
                        "seg_type": None, "seg_name": None, "seg_start": None,
                        "const_name": None, "const_off": None,
                        "sha12": hashlib.sha256(val).hexdigest()[:12],
                        "text": val,
                    })

    # 去重：同文件内被更大范围完全包含的锚点
    def dedup(rows):
        keep = []
        for r in sorted(rows, key=lambda r: (-r["bytes"], r["file"], r["anchor"])):
            if any(k["file"] == r["file"] and k["anchor"] <= r["anchor"]
                   and k["end"] >= r["end"] for k in keep):
                continue
            keep.append(r)
        return keep

    hard = dedup(hard)
    weak_ev = dedup(weak_ev)

    # e8test3.txt：整文件即源码文本
    p = os.path.join(SRC, "samples/e8/ManyFiles/e8test3.txt")
    plain = []
    if os.path.exists(p):
        b = open(p, "rb").read()
        ok, probs, nb, blk = check_value(b)
        nd, kc = decl_lines(b)
        if ok and nd >= MIN_DECL:
            plain.append({
                "file": "samples/e8/ManyFiles/e8test3.txt", "anchor": 0, "end": len(b),
                "bytes": len(b), "declared_len": None, "trailing_nul": 0,
                "lines": nb + blk, "nonblank": nb,
                "version_lines": sum(1 for ln in b.split(b"\n") if ln.startswith(VER_LINE)),
                "decl_lines": nd, "decl_kinds": kc,
                "seg_type": None, "seg_name": None, "seg_start": None,
                "const_name": None, "const_off": None,
                "sha12": hashlib.sha256(b).hexdigest()[:12], "text": b,
            })

    # ── 落盘 ─────────────────────────────────────────────────────────────
    os.makedirs(DST, exist_ok=True)
    for f in os.listdir(DST):
        if f.endswith(".txt"):
            os.remove(os.path.join(DST, f))

    def slug(s):
        return re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]+", "_", s)[:40]

    def write(rows, tier):
        manifest = []
        seen = {}
        for r in rows:
            key = r["sha12"]
            name = f"{tier}-{slug(os.path.splitext(r['file'])[0])}-{r['anchor']}.txt"
            if key in seen:                       # 同内容只落一份
                r["dup_of"] = seen[key]
                continue
            seen[key] = name
            # 落盘一律 UTF-8（原文是 GBK；编码转换只在边界做一次）
            with open(os.path.join(DST, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(r["text"].decode("gbk"))
            r["sample"] = name
            manifest.append(name)
        return manifest

    m1 = write(hard, "硬")
    m2 = write(plain, "硬文本")
    m3 = write(weak_ev, "弱")

    json.dump({"hard": [{k: v for k, v in r.items() if k != "text"} for r in hard],
               "hard_plain": [{k: v for k, v in r.items() if k != "text"} for r in plain],
               "weak": [{k: v for k, v in r.items() if k != "text"} for r in weak_ev],
               "weak_rejected": weak_json},
              open(OUTJSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    uniq = {}
    for r in hard + plain + weak_ev:
        uniq.setdefault(r["sha12"], r)
    print(f"硬证据（容器长度背书） {len(hard)} 处 → 落盘 {len(m1)} 份")
    print(f"硬证据（整文件即文本） {len(plain)} 处 → 落盘 {len(m2)} 份")
    print(f"弱证据（无长度字段）   {len(weak_ev)} 处 → 落盘 {len(m3)} 份")
    print(f"唯一文本 {len(uniq)} 份 · 唯一字节 {sum(r['bytes'] for r in uniq.values())}")
    print(f"全部出现处合计字节 {sum(r['bytes'] for r in hard + plain + weak_ev)}")
    for r in sorted(hard + plain + weak_ev, key=lambda r: (-r["bytes"], r["file"])):
        print(f"  {r['bytes']:>8}  {r.get('sample') or '(dup ' + str(r.get('dup_of')) + ')':<34} "
              f"t{str(r['seg_type']):<4} {r['file']}@{r['anchor']}")


if __name__ == "__main__":
    main()
