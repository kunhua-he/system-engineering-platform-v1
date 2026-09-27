"""统计 —— 记号表 + 未归类字符表 → 一份读数 R。"""

import re
from collections import Counter, defaultdict

from .规格词表 import is_remark_field
from .按规格切 import tokenize

def analyse(rows):
    """rows = [(样本名, 真文本原文(GBK bytes), 层级)]"""
    读数 = {
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
        读数["样本数"] += 1
        读数["总字节"] += len(raw)
        读数["总字符"] += len(text)
        读数["换行_裸CR"] += len(re.findall(r"(?<!\r)\r(?!\n)", text))
        读数["含TAB"] += text.count("\t")
        toks, unknown = tokenize(text)
        if not text.endswith(("\n", "\r")):
            读数["末行无换行"] += 1
        covered = 0
        for kind, li, col, 记号, fi, lk in toks:
            covered += len(记号)
            if kind == "关键字":
                if 记号.startswith("."):
                    读数["关键字_带点"][记号[1:]] += 1
                else:
                    读数["关键字_不带点"][记号] += 1
                读数["关键字上下文"].setdefault(记号, (name, text.split("\n")[li].rstrip()))
            elif kind == "运算符":
                读数["运算符"][记号] += 1
                读数["运算符位"][(lk, fi)] += 1
            elif kind == "界符":
                读数["界符"][记号] += 1
            elif kind == "注释":
                读数["注释"] += 1
                if "'" in 记号[1:]:
                    读数["注释里有单引号"] += 1
            elif kind == "文本字面量":
                读数["字面量位"][(lk, fi, "全角" if 记号[0] in "“”" else "半角")] += 1
                if 记号[0] in "“”":
                    读数["字面量_全角"] += 1
                    if '"' in 记号:
                        读数["字面量_嵌套"] += 1
                else:
                    读数["字面量_半角"] += 1
                    if "“" in 记号 or "”" in 记号:
                        读数["字面量_嵌套"] += 1
            elif kind == "数值字面量":
                读数["数值位"][(lk, fi)] += 1
                if 记号.startswith("-") or 记号.startswith("+"):
                    读数["数值_带符号"] += 1
                if "." in 记号:
                    读数["数值_小数"] += 1
                    读数["数值"]["小数"] += 1
                elif 记号.lstrip("-+").lower().startswith("0x"):
                    读数["数值_十六进制"] += 1
                    读数["数值"]["十六进制"] += 1
                elif re.search(r"[eE]", 记号):
                    读数["数值_科学计数"] += 1
                    读数["数值"]["科学计数"] += 1
                else:
                    读数["数值"]["十进制整数"] += 1
            elif kind == "常量引用":
                读数["常量引用"][记号] += 1
                读数["常量名"][记号] += 1
            elif kind == "标识符":
                for ch in 记号:
                    读数["标识符字符"][ch] += 1
                读数["标识符首字符"][记号[0]] += 1
            elif kind == "换行":
                if 记号 == "\r\n":
                    读数["换行_CRLF"] += 1
                else:
                    读数["换行_LF"] += 1
        for li, col, ch, line, fi, lk in unknown:
            读数["未归类"][ch] += 1
            读数["未归类样本"][ch][name] += 1
            读数["未归类位"][(lk, fi)] += 1
            读数["未归类位2"][ch][(lk, fi)] += 1
            if is_remark_field(line, fi):
                读数["未归类_备注位"] += 1
            else:
                读数["未归类_代码位"] += 1
                读数["未归类_代码位样"][ch] += 1
                读数["未归类_代码位字节"] += len(ch.encode("gbk"))
            读数["未归类字节"] += len(ch.encode("gbk"))
            读数["未归类行"][li] += 1
            读数["未归类行样"].setdefault(li, (name, line))
        读数["覆盖字符"] += covered
        读数["样本明细"][name] = (len(raw), len(text), covered, len(unknown))
        # 空实参：`, ,` 与 `( ,` 与 `, )` 的零宽位
        for line in text.split("\n"):
            ln = line[:-1] if line.endswith("\r") else line
            args = ln[ln.find("(") + 1:ln.rfind(")")] if "(" in ln and ln.rfind(")") > ln.find("(") else ""
            if not args:
                continue
            parts = args.split(",")
            if len(parts) < 2:
                continue
            empt = sum(1 for 实参 in parts if 实参.strip() == "")
            if empt:
                读数["空实参_行数"] += 1
                读数["空实参_位置"][empt] += 1
                读数["空实参_单行最多"] = max(读数["空实参_单行最多"], empt)
        # 缩进宽度（只统计列 0 为空格的行）
        for line in text.split("\n"):
            ln = line[:-1] if line.endswith("\r") else line
            if ln.startswith(" ") and ln.strip():
                缩进宽 = len(ln) - len(ln.lstrip(" "))
                读数["缩进宽度"][缩进宽] += 1
                if 缩进宽 != 4:
                    读数["缩进非4"] += 1
    return 读数


def 分层字节(rows):
    """按层级累计字节数（原 main() 里那三行，逐字搬来）。"""
    tier_bytes = Counter()
    for name, raw, tier in rows:
        tier_bytes[tier] += len(raw)
    return tier_bytes
