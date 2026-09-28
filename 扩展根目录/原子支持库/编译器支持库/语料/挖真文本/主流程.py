# -*- coding: utf-8 -*-
"""挖真文本 · 主流程 —— 遍历语料 · 硬/弱/整文件三类取证 · 去重 · 落盘 · 打印读数。"""
import hashlib
import json
import os
import re

from .容器段表 import 取常量名, 偏移所属段, 段表
from .常量 import 真文本目录, 最少声明行数, 挖出JSON路径, 源码根, 版本锚, 版本行首, 弱证据白名单
from .行判定 import 检查候选文本, 声明行数, 扩张边界


# ── 主流程 ────────────────────────────────────────────────────────────────
def 入口函数():
    hard, weak_ev, weak_json = [], [], []
    for dp, dn, fn in os.walk(源码根):
        for 文件名 in fn:
            路径 = os.path.join(dp, 文件名)
            rel = os.path.relpath(路径, 源码根)
            try:
                字节流 = open(路径, "rb").read()
            except Exception:
                continue
            anchors, 扫描位 = [], 0
            while True:
                头位 = 字节流.find(版本锚, 扫描位)
                if 头位 < 0:
                    break
                anchors.append(头位)
                扫描位 = 头位 + 1
            if not anchors:
                continue
            tab = 段表(字节流)
            covered = []
            for 锚点 in anchors:
                段长 = int.from_bytes(字节流[锚点 - 4:锚点], "little") if 锚点 >= 4 else 0
                if 段长 < 16 or 锚点 + 段长 > len(字节流):
                    continue
                raw = 字节流[锚点:锚点 + 段长]
                val = raw.rstrip(b"\x00")
                ok, probs, nb, blk = 检查候选文本(val)
                ver = sum(1 for ln in val.split(b"\n") if ln.startswith(版本行首))
                nd, kc = 声明行数(val)
                if not (ok and ver >= 1 and nd >= 最少声明行数):
                    continue
                st = 偏移所属段(tab, 锚点)
                cn = 取常量名(字节流, 锚点)
                covered.append((锚点, 锚点 + len(val)))
                hard.append({
                    "file": rel, "anchor": 锚点, "end": 锚点 + len(val), "bytes": len(val),
                    "declared_len": 段长, "trailing_nul": len(raw) - len(val),
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
            if rel in 弱证据白名单:
                for 锚点 in anchors:
                    if any(段起 <= 锚点 < 段止 for 段起, 段止 in covered):
                        continue
                    段起, 段止 = 扩张边界(字节流, 锚点)
                    val = 字节流[段起:段止]
                    ok, probs, nb, blk = 检查候选文本(val)
                    ver = sum(1 for ln in val.split(b"\n") if ln.startswith(版本行首))
                    nd, kc = 声明行数(val)
                    if not (ok and ver >= 1 and nd >= 最少声明行数):
                        weak_json.append({"file": rel, "anchor": 锚点, "bytes": 段止 - 段起,
                                          "reason": "非良构/声明不足", "problems": probs[:4]})
                        continue
                    weak_ev.append({
                        "file": rel, "anchor": 段起, "end": 段止, "bytes": len(val),
                        "declared_len": None, "trailing_nul": 0,
                        "lines": nb + blk, "nonblank": nb,
                        "version_lines": ver, "decl_lines": nd, "decl_kinds": kc,
                        "seg_type": None, "seg_name": None, "seg_start": None,
                        "const_name": None, "const_off": None,
                        "sha12": hashlib.sha256(val).hexdigest()[:12],
                        "text": val,
                    })

    # 去重：同文件内被更大范围完全包含的锚点
    def 去重(rows):
        keep = []
        for 记录 in sorted(rows, key=lambda 记录: (-记录["bytes"], 记录["file"], 记录["anchor"])):
            if any(保留项["file"] == 记录["file"] and 保留项["anchor"] <= 记录["anchor"]
                   and 保留项["end"] >= 记录["end"] for 保留项 in keep):
                continue
            keep.append(记录)
        return keep

    hard = 去重(hard)
    weak_ev = 去重(weak_ev)

    # e8test3.txt：整文件即源码文本
    路径 = os.path.join(源码根, "samples/e8/ManyFiles/e8test3.txt")
    plain = []
    if os.path.exists(路径):
        字节流 = open(路径, "rb").read()
        ok, probs, nb, blk = 检查候选文本(字节流)
        nd, kc = 声明行数(字节流)
        if ok and nd >= 最少声明行数:
            plain.append({
                "file": "samples/e8/ManyFiles/e8test3.txt", "anchor": 0, "end": len(字节流),
                "bytes": len(字节流), "declared_len": None, "trailing_nul": 0,
                "lines": nb + blk, "nonblank": nb,
                "version_lines": sum(1 for ln in 字节流.split(b"\n") if ln.startswith(版本行首)),
                "decl_lines": nd, "decl_kinds": kc,
                "seg_type": None, "seg_name": None, "seg_start": None,
                "const_name": None, "const_off": None,
                "sha12": hashlib.sha256(字节流).hexdigest()[:12], "text": 字节流,
            })

    # ── 落盘 ─────────────────────────────────────────────────────────────
    os.makedirs(真文本目录, exist_ok=True)
    for 文件名 in os.listdir(真文本目录):
        if 文件名.endswith(".txt"):
            os.remove(os.path.join(真文本目录, 文件名))

    def 简化文件名(字节串):
        return re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]+", "_", 字节串)[:40]

    def 落盘(rows, tier):
        manifest = []
        seen = {}
        for 记录 in rows:
            key = 记录["sha12"]
            name = f"{tier}-{简化文件名(os.path.splitext(记录['file'])[0])}-{记录['anchor']}.txt"
            if key in seen:                       # 同内容只落一份
                记录["dup_of"] = seen[key]
                continue
            seen[key] = name
            # 落盘一律 UTF-8（原文是 GBK；编码转换只在边界做一次）
            with open(os.path.join(真文本目录, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(记录["text"].decode("gbk"))
            记录["sample"] = name
            manifest.append(name)
        return manifest

    m1 = 落盘(hard, "硬")
    m2 = 落盘(plain, "硬文本")
    m3 = 落盘(weak_ev, "弱")

    json.dump({"hard": [{键名: 待处理值 for 键名, 待处理值 in 记录.items() if 键名 != "text"} for 记录 in hard],
               "hard_plain": [{键名: 待处理值 for 键名, 待处理值 in 记录.items() if 键名 != "text"} for 记录 in plain],
               "weak": [{键名: 待处理值 for 键名, 待处理值 in 记录.items() if 键名 != "text"} for 记录 in weak_ev],
               "weak_rejected": weak_json},
              open(挖出JSON路径, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    uniq = {}
    for 记录 in hard + plain + weak_ev:
        uniq.setdefault(记录["sha12"], 记录)
    print(f"硬证据（容器长度背书） {len(hard)} 处 → 落盘 {len(m1)} 份")
    print(f"硬证据（整文件即文本） {len(plain)} 处 → 落盘 {len(m2)} 份")
    print(f"弱证据（无长度字段）   {len(weak_ev)} 处 → 落盘 {len(m3)} 份")
    print(f"唯一文本 {len(uniq)} 份 · 唯一字节 {sum(记录['bytes'] for 记录 in uniq.values())}")
    print(f"全部出现处合计字节 {sum(记录['bytes'] for 记录 in hard + plain + weak_ev)}")
    for 记录 in sorted(hard + plain + weak_ev, key=lambda 记录: (-记录["bytes"], 记录["file"])):
        print(f"  {记录['bytes']:>8}  {记录.get('sample') or '(dup ' + str(记录.get('dup_of')) + ')':<34} "
              f"t{str(记录['seg_type']):<4} {记录['file']}@{记录['anchor']}")
