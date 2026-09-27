# -*- coding: utf-8 -*-
"""挖真文本 · 主流程 —— 遍历语料 · 硬/弱/整文件三类取证 · 去重 · 落盘 · 打印读数。"""
import hashlib
import json
import os
import re

from .容器段表 import const_name, seg_of, seg_table
from .常量 import DST, MIN_DECL, OUTJSON, SRC, VER, VER_LINE, WEAK_FILES
from .行判定 import check_value, decl_lines, expand


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
