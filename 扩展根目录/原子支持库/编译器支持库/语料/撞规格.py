#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""撞规格 —— 拿真文本逐条撞 `项目文档/设计文档/程序文本格式.md` 第二节的规格。

一条命令复跑：  python3 撞规格.py [--json]

读 `真文本/*.txt`（UTF-8，由 挖真文本.py 从 GBK 原文转来）。
**分析按原字节做**：把样本重新编回 GBK，得到真文本在参照实现里的原始字节，
再按规格的 11 种记号去切 —— 规格里 `记号流::原文` 的类型是 `Vec<u8>`，区间是**字节区间**。

判据（规格 §二）：
  编码 UTF-8（参照 GBK）· 换行写出 LF / 读入认 CRLF+LF · 缩进 4 半角空格 ·
  关键字以 `.` 开头（少数不带点：`返回` `置入代码`）· 注释 `'` 至行尾且不含行尾换行 ·
  文本字面量全角 `“…”`（读入也认半角 `"…"`）· 常量引用 `#名字` ·
  运算符全角 `＝ ＋ ÷` · 界符半角 `( ) [ ] , . & { }` · 空实参有意义
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "真文本")

# ── 规格里点名的字符集 ────────────────────────────────────────────────────
SPEC_OP = set("＝＋÷")                                  # 规格 §二 运算符
SPEC_DELIM = set("()[],.&{}")                           # 规格 §二 界符
SPEC_KEYWORD_DOTTED = {                                 # 规格里点名/举例的带点关键字
    "版本", "子程序", "参数", "局部变量", "如果真", "判断", "计次循环首",
    "程序集", "程序集变量", "全局变量", "数据类型", "成员", "DLL命令", "常量",
    "支持库", "如果真结束", "判断开始", "默认", "判断结束", "计次循环尾",
}
SPEC_KEYWORD_BARE = {"返回", "置入代码"}                 # 规格 §二 点名的不带点关键字

# 已知的易语言指令词（用于把「样本里出现、规格没点名」的关键字分出来）
KNOWN_DOTTED = SPEC_KEYWORD_DOTTED | {
    "如果", "否则", "如果结束", "循环判断首", "循环判断尾", "变量循环首", "变量循环尾",
    "判断循环首", "判断循环尾", "到循环尾", "跳出循环", "返回", "结束",
    "子程序", "库命令", "DLL命令", "局部变量", "程序集变量", "全局变量", "参数",
    "数据类型", "成员", "常量", "资源", "图片资源", "声音资源", "窗口", "菜单",
    "易模块", "类", "方法", "初始化", "公开", "私有", "作者", "描述", "信息",
    "版本", "支持库", "程序集", "组件", "自定义数据类型", "结构",
}

ID_FIRST = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]")
ID_CHAR = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]")
DIGIT = re.compile(r"[0-9]")

# 声明行里「结构字段」的个数：第 0..n-1 个字段是结构位，再往后是**不加引号的自由文本**
# （实测：末字段常把「映射名」与「备注」用全角 `，` 连在一起写，如
#   `.成员 格式标签, 短整数型, , , wFormatTag，记录着此声音的格式代号`）
STRUCT = {"版本": 1, "支持库": 1, "程序集": 1, "全局变量": 2, "程序集变量": 2,
          "子程序": 3, "参数": 3, "局部变量": 4, "常量": 3, "数据类型": 2,
          "自定义数据类型": 2, "成员": 4, "DLL命令": 5}
# 语句类点关键字：整行都是代码，没有备注位
STMT_KW = {"如果", "否则", "如果结束", "如果真", "如果真结束", "判断开始", "判断", "默认",
           "判断结束", "计次循环首", "计次循环尾", "循环判断首", "循环判断尾",
           "变量循环首", "变量循环尾", "判断循环首", "判断循环尾", "到循环尾", "跳出循环"}


def lead_kw(line):
    s = line.lstrip()
    if s.startswith("."):
        m = re.match(r"\.([0-9A-Za-z_\u4e00-\u9fff]+)", s)
        if m:
            return m.group(1)
    return None


def is_remark_field(line, fi):
    """该位置是不是「声明行的非结构自由文本字段」。"""
    kw = lead_kw(line)
    if kw is None or kw in STMT_KW:
        return False
    return fi >= STRUCT.get(kw, 99)

# 半角 ASCII 里「规格没提」但可能出现的符号
ASCII_PUNCT = set(r"!\"#$%'()*+,-./:;<=>?@[\]^_`{|}~")


def _field_idx(line, col):
    """col 之前有几个「顶层半角逗号」（字面量内的不算）→ 就是字段序。"""
    n = 0
    j = 0
    while j < col and j < len(line):
        c = line[j]
        if c in "“”\"":
            close = "”" if c in "“”" else '"'
            j += 1
            while j < len(line) and line[j] != close:
                j += 1
            j += 1
            continue
        if c == ",":
            n += 1
        j += 1
    return n


def tokenize(text):
    """按规格 11 种记号切。返回 (记号表, 未归类字符表)。

    记号表元素 = (种类, 行, 列, 文本, 字段序, 行类)
    行类 = '声明'（行首 `.`）/ '注释'（行首 `'`）/ '语句'
    """
    toks = []
    unknown = []
    lines = text.split("\n")
    nlines = len(lines)
    for li, line in enumerate(lines):
        last = (li == nlines - 1)
        if line.endswith("\r"):
            line = line[:-1]
            crlf = True
        else:
            crlf = False
        terminated = (not last) or text.endswith("\n")
        if last and line == "" and not crlf:
            break                       # 末尾没有换行符 ⇒ 不产出幻影 换行 记号
        i = 0
        n = len(line)
        # 行首缩进
        while i < n and line[i] == " ":
            i += 1
        if i:
            toks.append(("空白", li, 0, line[:i], 0, "缩进"))
        line_start = i
        stripped = line.lstrip()
        line_kind = ("声明" if stripped.startswith(".") else
                     "注释" if stripped.startswith("'") else "语句")
        # 先定位注释起点（不在字面量内的第一个 `'`）
        cut = None
        j = i
        while j < n:
            c = line[j]
            if c in "“”\"":
                close = {"“": "”", "”": "”", '"': '"'}[c]
                j += 1
                while j < n and line[j] != close:
                    j += 1
                j += 1
                continue
            if c == "'":
                cut = j
                break
            j += 1
        code_end = cut if cut is not None else n
        while i < code_end:
            c = line[i]
            fi = _field_idx(line, i)
            if c == " ":
                k = i
                while k < code_end and line[k] == " ":
                    k += 1
                toks.append(("空白", li, i, line[i:k], fi, line_kind))
                i = k
                continue
            if c == "." and i == line_start:
                m = re.match(r"\.([0-9A-Za-z_\u4e00-\u9fff]+)", line[i:])
                if m:
                    toks.append(("关键字", li, i, m.group(0), fi, line_kind))
                    i += len(m.group(0))
                    continue
            if c == "#":
                m = re.match(r"#([0-9A-Za-z_\u4e00-\u9fff]+)", line[i:])
                if m:
                    toks.append(("常量引用", li, i, m.group(0), fi, line_kind))
                    i += len(m.group(0))
                    continue
                unknown.append((li, i, c, line, fi, line_kind))
                i += 1
                continue
            if c in "“”\"":
                close = "”" if c in "“”" else '"'
                k = i + 1
                while k < code_end and line[k] != close:
                    k += 1
                if k < code_end:
                    toks.append(("文本字面量", li, i, line[i:k + 1], fi, line_kind))
                    i = k + 1
                    continue
                unknown.append((li, i, c, line, fi, line_kind))
                i += 1
                continue
            if DIGIT.match(c) or (c == "-" and i + 1 < code_end and DIGIT.match(line[i + 1])
                                  and (i == line_start or not ID_CHAR.match(line[i - 1]))):
                m = re.match(r"-?(0[xX][0-9A-Fa-f]+|[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?)", line[i:])
                toks.append(("数值字面量", li, i, m.group(0), fi, line_kind))
                i += len(m.group(0))
                continue
            if c in SPEC_OP:
                toks.append(("运算符", li, i, c, fi, line_kind))
                i += 1
                continue
            if c in SPEC_DELIM:
                toks.append(("界符", li, i, c, fi, line_kind))
                i += 1
                continue
            if ID_CHAR.match(c):
                k = i
                while k < code_end and ID_CHAR.match(line[k]):
                    k += 1
                word = line[i:k]
                if i == line_start and word in SPEC_KEYWORD_BARE:
                    toks.append(("关键字", li, i, word, fi, line_kind))
                else:
                    toks.append(("标识符", li, i, word, fi, line_kind))
                i = k
                continue
            unknown.append((li, i, c, line, fi, line_kind))
            i += 1
        if cut is not None:
            toks.append(("注释", li, cut, line[cut:], _field_idx(line, cut), line_kind))
        if terminated:
            toks.append(("换行", li, n, "\r\n" if crlf else "\n", 0, line_kind))
    toks.append(("文件结束", nlines, 0, "", 0, ""))
    return toks, unknown


def analyse(rows):
    """rows = [(样本名, 真文本原文(GBK bytes), 层级)]"""
    R = {
        "样本数": 0, "总字节": 0, "总字符": 0,
        "关键字_带点": Counter(), "关键字_不带点": Counter(),
        "运算符": Counter(), "界符": Counter(),
        "注释": 0, "注释行尾含CR": 0, "注释里有单引号": 0,
        "字面量_全角": 0, "字面量_半角": 0, "字面量_嵌套": 0, "字面量_跨行": 0, "字面量_未闭合": 0,
        "数值": Counter(), "数值_带符号": 0, "数值_小数": 0, "数值_十六进制": 0, "数值_科学计数": 0,
        "常量引用": Counter(),
        "缩进宽度": Counter(), "缩进非4": 0, "含TAB": 0,
        "换行_CRLF": 0, "换行_LF": 0, "换行_裸CR": 0,
        "空实参_位置": Counter(), "空实参_行数": 0, "空实参_单行最多": 0,
        "标识符字符": Counter(), "标识符首字符": Counter(),
        "未归类": Counter(), "未归类样本": defaultdict(Counter),
        "未归类字节": 0, "未归类行": Counter(), "未归类行样": {},
        "覆盖字符": 0, "样本明细": {},
        "关键字上下文": {}, "字面量样": Counter(), "常量名": Counter(),
        "运算符位": Counter(), "未归类位": Counter(), "字面量位": Counter(),
        "数值位": Counter(), "末行无换行": 0, "未归类位2": defaultdict(Counter),
        "未归类_备注位": 0, "未归类_代码位": 0, "未归类_代码位样": Counter(),
        "未归类_代码位字节": 0,
    }
    for name, raw, tier in rows:
        text = raw.decode("gbk")
        R["样本数"] += 1
        R["总字节"] += len(raw)
        R["总字符"] += len(text)
        R["换行_裸CR"] += len(re.findall(r"(?<!\r)\r(?!\n)", text))
        R["含TAB"] += text.count("\t")
        toks, unknown = tokenize(text)
        if not text.endswith(("\n", "\r")):
            R["末行无换行"] += 1
        covered = 0
        for kind, li, col, s, fi, lk in toks:
            covered += len(s)
            if kind == "关键字":
                if s.startswith("."):
                    R["关键字_带点"][s[1:]] += 1
                else:
                    R["关键字_不带点"][s] += 1
                R["关键字上下文"].setdefault(s, (name, text.split("\n")[li].rstrip()))
            elif kind == "运算符":
                R["运算符"][s] += 1
                R["运算符位"][(lk, fi)] += 1
            elif kind == "界符":
                R["界符"][s] += 1
            elif kind == "注释":
                R["注释"] += 1
                if "'" in s[1:]:
                    R["注释里有单引号"] += 1
            elif kind == "文本字面量":
                R["字面量位"][(lk, fi, "全角" if s[0] in "“”" else "半角")] += 1
                if s[0] in "“”":
                    R["字面量_全角"] += 1
                    if '"' in s:
                        R["字面量_嵌套"] += 1
                else:
                    R["字面量_半角"] += 1
                    if "“" in s or "”" in s:
                        R["字面量_嵌套"] += 1
            elif kind == "数值字面量":
                R["数值位"][(lk, fi)] += 1
                if s.startswith("-") or s.startswith("+"):
                    R["数值_带符号"] += 1
                if "." in s:
                    R["数值_小数"] += 1
                    R["数值"]["小数"] += 1
                elif s.lstrip("-+").lower().startswith("0x"):
                    R["数值_十六进制"] += 1
                    R["数值"]["十六进制"] += 1
                elif re.search(r"[eE]", s):
                    R["数值_科学计数"] += 1
                    R["数值"]["科学计数"] += 1
                else:
                    R["数值"]["十进制整数"] += 1
            elif kind == "常量引用":
                R["常量引用"][s] += 1
                R["常量名"][s] += 1
            elif kind == "标识符":
                for ch in s:
                    R["标识符字符"][ch] += 1
                R["标识符首字符"][s[0]] += 1
            elif kind == "换行":
                if s == "\r\n":
                    R["换行_CRLF"] += 1
                else:
                    R["换行_LF"] += 1
        for li, col, ch, line, fi, lk in unknown:
            R["未归类"][ch] += 1
            R["未归类样本"][ch][name] += 1
            R["未归类位"][(lk, fi)] += 1
            R["未归类位2"][ch][(lk, fi)] += 1
            if is_remark_field(line, fi):
                R["未归类_备注位"] += 1
            else:
                R["未归类_代码位"] += 1
                R["未归类_代码位样"][ch] += 1
                R["未归类_代码位字节"] += len(ch.encode("gbk"))
            R["未归类字节"] += len(ch.encode("gbk"))
            R["未归类行"][li] += 1
            R["未归类行样"].setdefault(li, (name, line))
        R["覆盖字符"] += covered
        R["样本明细"][name] = (len(raw), len(text), covered, len(unknown))
        # 空实参：`, ,` 与 `( ,` 与 `, )` 的零宽位
        for line in text.split("\n"):
            ln = line[:-1] if line.endswith("\r") else line
            args = ln[ln.find("(") + 1:ln.rfind(")")] if "(" in ln and ln.rfind(")") > ln.find("(") else ""
            if not args:
                continue
            parts = args.split(",")
            if len(parts) < 2:
                continue
            empt = sum(1 for p in parts if p.strip() == "")
            if empt:
                R["空实参_行数"] += 1
                R["空实参_位置"][empt] += 1
                R["空实参_单行最多"] = max(R["空实参_单行最多"], empt)
        # 缩进宽度（只统计列 0 为空格的行）
        for line in text.split("\n"):
            ln = line[:-1] if line.endswith("\r") else line
            if ln.startswith(" ") and ln.strip():
                w = len(ln) - len(ln.lstrip(" "))
                R["缩进宽度"][w] += 1
                if w != 4:
                    R["缩进非4"] += 1
    return R


def main():
    rows = []
    for f in sorted(os.listdir(DST)):
        if not f.endswith(".txt"):
            continue
        # newline="" 关掉通用换行翻译，否则 \r\n 会被悄悄折成 \n（换行读数就废了）
        with open(os.path.join(DST, f), encoding="utf-8", newline="") as fh:
            text = fh.read()
        tier = f.split("-")[0]
        rows.append((f, text.encode("gbk"), tier))
    R = analyse(rows)
    tier_bytes = Counter()
    for name, raw, tier in rows:
        tier_bytes[tier] += len(raw)

    print("=" * 96)
    print(f"样本 {R['样本数']} 份 · 真文本字节 {R['总字节']} · 字符 {R['总字符']}")
    print("  分层字节：", dict(tier_bytes))
    print("=" * 96)

    print("\n【关键字 · 以 . 开头】共 %d 种 / %d 次"
          % (len(R["关键字_带点"]), sum(R["关键字_带点"].values())))
    for w, c in R["关键字_带点"].most_common():
        mark = "" if w in SPEC_KEYWORD_DOTTED else ("  ← 规格未点名" if w in KNOWN_DOTTED else "  ← 规格未点名（且不在已知词表）")
        print(f"    .{w:<20} {c:>7}{mark}")

    print("\n【关键字 · 不带点】%s" % dict(R["关键字_不带点"]))

    print("\n【样本里出现、但规格 §二 没点名的关键字 · 各附一条上下文】")
    for w, c in R["关键字_带点"].most_common():
        if w in SPEC_KEYWORD_DOTTED:
            continue
        name, line = R["关键字上下文"].get("." + w, ("", ""))
        print(f"    .{w:<12} {c:>5} 次   {name[:34]:<36} | {line[:96]}")
    for w, c in R["关键字_不带点"].most_common():
        name, line = R["关键字上下文"].get(w, ("", ""))
        print(f"    {w:<13} {c:>5} 次   {name[:34]:<36} | {line[:96]}")

    print("\n【常量引用名字全表】%d 种" % len(R["常量名"]))
    print("    " + "  ".join(sorted(R["常量名"])))

    print("\n【运算符】共 %d 种" % len(R["运算符"]))
    for ch, c in R["运算符"].most_common():
        mark = "" if ch in SPEC_OP else "  ← 规格只列 ＝ ＋ ÷，这个没列"
        print(f"    {ch}  U+{ord(ch):04X}  {c:>7}{mark}")

    print("\n【界符】共 %d 种" % len(R["界符"]))
    for ch, c in R["界符"].most_common():
        mark = "" if ch in SPEC_DELIM else "  ← 规格只列 ( ) [ ] , . & { }，这个没列"
        print(f"    {ch!r:<6} {c:>7}{mark}")

    print("\n【注释】%d 条 · 内含第二个单引号 %d 条" % (R["注释"], R["注释里有单引号"]))
    print("【文本字面量】全角 %d · 半角 %d · 嵌套 %d · 未闭合 %d"
          % (R["字面量_全角"], R["字面量_半角"], R["字面量_嵌套"], R["字面量_未闭合"]))
    print("【数值字面量】%s · 带符号 %d · 小数 %d · 十六进制 %d · 科学计数 %d"
          % (dict(R["数值"]), R["数值_带符号"], R["数值_小数"], R["数值_十六进制"], R["数值_科学计数"]))
    print("【常量引用】%d 种 / %d 次 · 最长名字 %s"
          % (len(R["常量引用"]), sum(R["常量引用"].values()),
             max(R["常量引用"], key=len) if R["常量引用"] else "-"))
    print("【缩进】宽度分布 %s · 非 4 的 %d 行 · TAB %d 个"
          % (dict(sorted(R["缩进宽度"].items())), R["缩进非4"], R["含TAB"]))
    print("【换行】CRLF %d · LF %d · 裸 CR %d"
          % (R["换行_CRLF"], R["换行_LF"], R["换行_裸CR"]))
    print("【空实参】%d 行有空位 · 单行最多 %d 个空位 · 空位数分布 %s"
          % (R["空实参_行数"], R["空实参_单行最多"], dict(sorted(R["空实参_位置"].items()))))

    print("\n【标识符字符集】共 %d 种字符" % len(R["标识符字符"]))
    cats = Counter()
    for ch in R["标识符字符"]:
        if "\u4e00" <= ch <= "\u9fff":
            cats["汉字"] += 1
        elif ch == "_":
            cats["下划线"] += 1
        elif ch.isdigit():
            cats["数字"] += 1
        elif ch.isupper():
            cats["大写字母"] += 1
        elif ch.islower():
            cats["小写字母"] += 1
        else:
            cats["其他"] += 1
    print("    ", dict(cats))
    other = [c for c in R["标识符字符"]
             if not ("\u4e00" <= c <= "\u9fff") and c != "_" and not c.isalnum()]
    print("     非 汉字/下划线/字母数字 的标识符字符：", other)

    print("\n【运算符出现的位置】（行类, 字段序）—— 声明行第 3 字段起是**不加引号的备注文本**")
    for (lk, fi), c in sorted(R["运算符位"].items(), key=lambda kv: -kv[1]):
        print(f"    行类={lk:<4} 第{fi}字段  {c:>5} 次")

    print("\n【文本字面量出现的位置】（行类, 字段序, 定界符）")
    for (lk, fi, q), c in sorted(R["字面量位"].items(), key=lambda kv: -kv[1])[:18]:
        print(f"    行类={lk:<4} 第{fi}字段  {q}  {c:>5} 次")

    print("\n【数值字面量出现的位置】（行类, 字段序）")
    for (lk, fi), c in sorted(R["数值位"].items(), key=lambda kv: -kv[1])[:18]:
        print(f"    行类={lk:<4} 第{fi}字段  {c:>5} 次")

    print("\n【未归类字符出现的位置】（行类, 字段序）—— 这一栏就是缺口的定位")
    for (lk, fi), c in sorted(R["未归类位"].items(), key=lambda kv: -kv[1]):
        print(f"    行类={lk:<4} 第{fi}字段  {c:>6} 次")
    print("    末行无换行符的样本：%d / %d" % (R["末行无换行"], R["样本数"]))

    print("\n【未归类字符】（规格里归不进任何一类的字符）")
    if not R["未归类"]:
        print("    无")
    for ch, c in R["未归类"].most_common():
        who = [f"{k}×{v}" for k, v in R["未归类样本"][ch].most_common(2)]
        pos = " ".join(f"{lk}·第{fi}字段×{n}" for (lk, fi), n in R["未归类位2"][ch].most_common())
        print(f"    {ch!r} U+{ord(ch):04X}  {c:>7} 次   [{pos}]")
        print(f"          样本 {', '.join(who)}")
    print("\n【未归类字符的上下文】（每种取一条）")
    for ch, c in R["未归类"].most_common():
        for name, raw, tier in rows:
            if not R["未归类样本"][ch].get(name):
                continue
            t = raw.decode("gbk")
            for line in t.split("\n"):
                if ch in line:
                    print(f"    {ch!r}  {name[:38]:<40} | {line.rstrip()[:120]}")
                    break
            break

    print("\n【逐样本通过率】（只看未归类字符数）")
    for name in sorted(R["样本明细"], key=lambda n: -R["样本明细"][n][3]):
        by, ch_n, cov, unk = R["样本明细"][name]
        print(f"    {unk:>6} 未归类 / {ch_n:>7} 字符  {name}")

    print("\n【含未归类字符的行 · 逐条（去重）】共 %d 行" % len(R["未归类行样"]))
    for li in sorted(R["未归类行样"], key=lambda l: -R["未归类行"][l]):
        name, line = R["未归类行样"][li]
        print(f"    {R['未归类行'][li]:>4} 个未归类字符 | {name[:34]:<36} | {line.rstrip()[:118]}")

    print("\n【通过率】")
    tot = R["总字符"]
    cov = R["覆盖字符"]
    rk = R["未归类_备注位"]
    cd = R["未归类_代码位"]
    print("  口径甲（现有 11 种记号硬切，不含「备注文本」这一类）：")
    print("     通过 %d / %d = %.6f%%   未归类 %d 个字符（%.6f%%）"
          % (cov, tot, 100.0 * cov / tot, rk + cd, 100.0 * (rk + cd) / tot))
    print("  口径乙（把声明行的非结构字段整体归成一类「备注文本」后）：")
    print("     通过 %d / %d = %.6f%%   仅剩 %d 个代码位未归类字符（%.6f%%）"
          % (tot - cd, tot, 100.0 * (tot - cd) / tot, cd, 100.0 * cd / tot))
    print("     · 备注位未归类 %d 个 · 代码位未归类 %d 个：%s"
          % (rk, cd, dict(R["未归类_代码位样"])))
    print("     · 口径乙下仍未归类的**字节** %d / %d = %.6f%%"
          % (R["未归类_代码位字节"], R["总字节"],
             100.0 * R["未归类_代码位字节"] / R["总字节"]))
    print("     · 未归类字节 %d / %d = %.6f%%（按 GBK 原字节）"
          % (R["未归类字节"], R["总字节"], 100.0 * R["未归类字节"] / R["总字节"]))

    if "--json" in sys.argv:
        out = {
            "样本数": R["样本数"], "总字节": R["总字节"], "总字符": R["总字符"],
            "关键字_带点": dict(R["关键字_带点"]), "运算符": dict(R["运算符"]),
            "界符": dict(R["界符"]), "注释": R["注释"],
            "字面量_全角": R["字面量_全角"], "字面量_半角": R["字面量_半角"],
            "数值": dict(R["数值"]), "常量引用种数": len(R["常量引用"]),
            "缩进宽度": {str(k): v for k, v in R["缩进宽度"].items()},
            "换行_CRLF": R["换行_CRLF"], "换行_LF": R["换行_LF"],
            "空实参_单行最多": R["空实参_单行最多"], "空实参_行数": R["空实参_行数"],
            "未归类": {f"{c}|U+{ord(c):04X}": n for c, n in R["未归类"].items()},
            "覆盖字符": R["覆盖字符"], "未归类字节": R["未归类字节"],
            "分层字节": dict(tier_bytes),
        }
        json.dump(out, open(os.path.join(HERE, "_撞规格读数.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
