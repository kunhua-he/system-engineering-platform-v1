"""报表 —— 读数 R → 屏幕上的那份读数 + `_撞规格读数.json`。"""

import json
import os
from collections import Counter

from .规格词表 import KNOWN_DOTTED, SPEC_DELIM, SPEC_KEYWORD_DOTTED, SPEC_OP

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(HERE, "真文本")


def 打印(R, rows, tier_bytes):
    """把读数逐栏打到屏幕上（原 main() 的打印段，逐字搬来）。"""
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


def 导出(R, tier_bytes):
    """落 `语料/_撞规格读数.json`（原 main() 的 --json 段，逐字搬来）。"""
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
