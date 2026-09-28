"""报表 —— 读数 R → 屏幕上的那份读数 + `_撞规格读数.json`。"""

import json
import os
from collections import Counter

from .规格词表 import 已知带点词, 规格界符, 规格带点关键字, 规格运算符

语料目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
真文本目录 = os.path.join(语料目录, "真文本")


def 打印报表读数(读数, rows, tier_bytes):
    """把读数逐栏打到屏幕上（原 main() 的打印段，逐字搬来）。"""
    print("=" * 96)
    print(f"样本 {读数['样本数']} 份 · 真文本字节 {读数['总字节']} · 字符 {读数['总字符']}")
    print("  分层字节：", dict(tier_bytes))
    print("=" * 96)

    print("\n【关键字 · 以 . 开头】共 %d 种 / %d 次"
          % (len(读数["关键字_带点"]), sum(读数["关键字_带点"].values())))
    for 关键字, 计数 in 读数["关键字_带点"].most_common():
        mark = "" if 关键字 in 规格带点关键字 else ("  ← 规格未点名" if 关键字 in 已知带点词 else "  ← 规格未点名（且不在已知词表）")
        print(f"    .{关键字:<20} {计数:>7}{mark}")

    print("\n【关键字 · 不带点】%s" % dict(读数["关键字_不带点"]))

    print("\n【样本里出现、但规格 §二 没点名的关键字 · 各附一条上下文】")
    for 关键字, 计数 in 读数["关键字_带点"].most_common():
        if 关键字 in 规格带点关键字:
            continue
        name, line = 读数["关键字上下文"].get("." + 关键字, ("", ""))
        print(f"    .{关键字:<12} {计数:>5} 次   {name[:34]:<36} | {line[:96]}")
    for 关键字, 计数 in 读数["关键字_不带点"].most_common():
        name, line = 读数["关键字上下文"].get(关键字, ("", ""))
        print(f"    {关键字:<13} {计数:>5} 次   {name[:34]:<36} | {line[:96]}")

    print("\n【常量引用名字全表】%d 种" % len(读数["常量名"]))
    print("    " + "  ".join(sorted(读数["常量名"])))

    print("\n【运算符】共 %d 种" % len(读数["运算符"]))
    for ch, 计数 in 读数["运算符"].most_common():
        mark = "" if ch in 规格运算符 else "  ← 规格只列 ＝ ＋ ÷，这个没列"
        print(f"    {ch}  U+{ord(ch):04X}  {计数:>7}{mark}")

    print("\n【界符】共 %d 种" % len(读数["界符"]))
    for ch, 计数 in 读数["界符"].most_common():
        mark = "" if ch in 规格界符 else "  ← 规格只列 ( ) [ ] , . & { }，这个没列"
        print(f"    {ch!r:<6} {计数:>7}{mark}")

    print("\n【注释】%d 条 · 内含第二个单引号 %d 条" % (读数["注释"], 读数["注释里有单引号"]))
    print("【文本字面量】全角 %d · 半角 %d · 嵌套 %d · 未闭合 %d"
          % (读数["字面量_全角"], 读数["字面量_半角"], 读数["字面量_嵌套"], 读数["字面量_未闭合"]))
    print("【数值字面量】%s · 带符号 %d · 小数 %d · 十六进制 %d · 科学计数 %d"
          % (dict(读数["数值"]), 读数["数值_带符号"], 读数["数值_小数"], 读数["数值_十六进制"], 读数["数值_科学计数"]))
    print("【常量引用】%d 种 / %d 次 · 最长名字 %s"
          % (len(读数["常量引用"]), sum(读数["常量引用"].values()),
             max(读数["常量引用"], key=len) if 读数["常量引用"] else "-"))
    print("【缩进】宽度分布 %s · 非 4 的 %d 行 · TAB %d 个"
          % (dict(sorted(读数["缩进宽度"].items())), 读数["缩进非4"], 读数["含TAB"]))
    print("【换行】CRLF %d · LF %d · 裸 CR %d"
          % (读数["换行_CRLF"], 读数["换行_LF"], 读数["换行_裸CR"]))
    print("【空实参】%d 行有空位 · 单行最多 %d 个空位 · 空位数分布 %s"
          % (读数["空实参_行数"], 读数["空实参_单行最多"], dict(sorted(读数["空实参_位置"].items()))))

    print("\n【标识符字符集】共 %d 种字符" % len(读数["标识符字符"]))
    cats = Counter()
    for ch in 读数["标识符字符"]:
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
    other = [字符 for 字符 in 读数["标识符字符"]
             if not ("\u4e00" <= 字符 <= "\u9fff") and 字符 != "_" and not 字符.isalnum()]
    print("     非 汉字/下划线/字母数字 的标识符字符：", other)

    print("\n【运算符出现的位置】（行类, 字段序）—— 声明行第 3 字段起是**不加引号的备注文本**")
    for (lk, fi), 计数 in sorted(读数["运算符位"].items(), key=lambda kv: -kv[1]):
        print(f"    行类={lk:<4} 第{fi}字段  {计数:>5} 次")

    print("\n【文本字面量出现的位置】（行类, 字段序, 定界符）")
    for (lk, fi, 定界符), 计数 in sorted(读数["字面量位"].items(), key=lambda kv: -kv[1])[:18]:
        print(f"    行类={lk:<4} 第{fi}字段  {定界符}  {计数:>5} 次")

    print("\n【数值字面量出现的位置】（行类, 字段序）")
    for (lk, fi), 计数 in sorted(读数["数值位"].items(), key=lambda kv: -kv[1])[:18]:
        print(f"    行类={lk:<4} 第{fi}字段  {计数:>5} 次")

    print("\n【未归类字符出现的位置】（行类, 字段序）—— 这一栏就是缺口的定位")
    for (lk, fi), 计数 in sorted(读数["未归类位"].items(), key=lambda kv: -kv[1]):
        print(f"    行类={lk:<4} 第{fi}字段  {计数:>6} 次")
    print("    末行无换行符的样本：%d / %d" % (读数["末行无换行"], 读数["样本数"]))

    print("\n【未归类字符】（规格里归不进任何一类的字符）")
    if not 读数["未归类"]:
        print("    无")
    for ch, 计数 in 读数["未归类"].most_common():
        who = [f"{样本名}×{次数}" for 样本名, 次数 in 读数["未归类样本"][ch].most_common(2)]
        pos = " ".join(f"{lk}·第{fi}字段×{次数}" for (lk, fi), 次数 in 读数["未归类位2"][ch].most_common())
        print(f"    {ch!r} U+{ord(ch):04X}  {计数:>7} 次   [{pos}]")
        print(f"          样本 {', '.join(who)}")
    print("\n【未归类字符的上下文】（每种取一条）")
    for ch, 计数 in 读数["未归类"].most_common():
        for name, raw, tier in rows:
            if not 读数["未归类样本"][ch].get(name):
                continue
            文本 = raw.decode("gbk")
            for line in 文本.split("\n"):
                if ch in line:
                    print(f"    {ch!r}  {name[:38]:<40} | {line.rstrip()[:120]}")
                    break
            break

    print("\n【逐样本通过率】（只看未归类字符数）")
    for name in sorted(读数["样本明细"], key=lambda 样本名: -读数["样本明细"][样本名][3]):
        by, ch_n, cov, unk = 读数["样本明细"][name]
        print(f"    {unk:>6} 未归类 / {ch_n:>7} 字符  {name}")

    print("\n【含未归类字符的行 · 逐条（去重）】共 %d 行" % len(读数["未归类行样"]))
    for li in sorted(读数["未归类行样"], key=lambda 行号: -读数["未归类行"][行号]):
        name, line = 读数["未归类行样"][li]
        print(f"    {读数['未归类行'][li]:>4} 个未归类字符 | {name[:34]:<36} | {line.rstrip()[:118]}")

    print("\n【通过率】")
    tot = 读数["总字符"]
    cov = 读数["覆盖字符"]
    rk = 读数["未归类_备注位"]
    cd = 读数["未归类_代码位"]
    print("  口径首（现有 11 种记号硬切，不含「备注文本」这一类）：")
    print("     通过 %d / %d = %.6f%%   未归类 %d 个字符（%.6f%%）"
          % (cov, tot, 100.0 * cov / tot, rk + cd, 100.0 * (rk + cd) / tot))
    print("  口径次（把声明行的非结构字段整体归成一类「备注文本」后）：")
    print("     通过 %d / %d = %.6f%%   仅剩 %d 个代码位未归类字符（%.6f%%）"
          % (tot - cd, tot, 100.0 * (tot - cd) / tot, cd, 100.0 * cd / tot))
    print("     · 备注位未归类 %d 个 · 代码位未归类 %d 个：%s"
          % (rk, cd, dict(读数["未归类_代码位样"])))
    print("     · 口径次下仍未归类的**字节** %d / %d = %.6f%%"
          % (读数["未归类_代码位字节"], 读数["总字节"],
             100.0 * 读数["未归类_代码位字节"] / 读数["总字节"]))
    print("     · 未归类字节 %d / %d = %.6f%%（按 GBK 原字节）"
          % (读数["未归类字节"], 读数["总字节"], 100.0 * 读数["未归类字节"] / 读数["总字节"]))


def 导出(读数, tier_bytes):
    """落 `语料/_撞规格读数.json`（原 main() 的 --json 段，逐字搬来）。"""
    out = {
        # ★ 头标（判据 ⑩ 的口径）：生成物要自称「生成物 · 禁手改 · 生成器 = 谁」——
        # 少了它，`v1_task` 功能=5 拒绝记账（实测：这件因为没头标，一直只能靠手改）。
        # ★ 路径必须是**那一行的末一个值**：记账器取「`生成器：` 之后整段」再剥引号/逗号，
        # 后面再跟别的字（哪怕一个 `` ` ``）就与真生成器路径对不上 ⇒ 记账恒被拒（实测撞过）。
        "说明": "生成物：**禁手改** —— 53 份真文本的逐类读数，供 `说明/真文本覆盖.md` 与词法腿对读。"
                "复跑：python3 撞规格.py --json · 生成器：扩展根目录/原子支持库/编译器支持库/语料/撞规格.py",
        "样本数": 读数["样本数"], "总字节": 读数["总字节"], "总字符": 读数["总字符"],
        "关键字_带点": dict(读数["关键字_带点"]), "运算符": dict(读数["运算符"]),
        "界符": dict(读数["界符"]), "注释": 读数["注释"],
        "字面量_全角": 读数["字面量_全角"], "字面量_半角": 读数["字面量_半角"],
        "数值": dict(读数["数值"]), "常量引用种数": len(读数["常量引用"]),
        "缩进宽度": {str(宽度): 次数 for 宽度, 次数 in 读数["缩进宽度"].items()},
        "换行_CRLF": 读数["换行_CRLF"], "换行_LF": 读数["换行_LF"],
        "空实参_单行最多": 读数["空实参_单行最多"], "空实参_行数": 读数["空实参_行数"],
        "未归类": {f"{字符}|U+{ord(字符):04X}": 次数 for 字符, 次数 in 读数["未归类"].items()},
        "覆盖字符": 读数["覆盖字符"], "未归类字节": 读数["未归类字节"],
        "分层字节": dict(tier_bytes),
    }
    json.dump(out, open(os.path.join(语料目录, "_撞规格读数.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
