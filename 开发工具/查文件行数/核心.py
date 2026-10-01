"""核心 —— 第六节硬数的机器判据：扫描 · 判定 · 报读数 · 自测。

几条行模式各管一种写法（名字自明）：`顶层项行模式` = Rust 顶层项 · `定义行模式` = `def`/`class` ·
`赋值行模式` = 模块级赋值 · `主入口行模式` = 脚本主入口。

★ `读文本` 的错误策略是**有意的（`errors="replace"` 且不吞：`OSError` 原样抛）** —— 扫全仓
源码要「任何字节都读得动」（不让一个坏字节毁掉整轮读数），但**读不动要当场报**。与别处同名
读器（`代码地图/形参面.py` 的 `读文本` 用 `replace` 且吞 `OSError` 返空串）**不是同一事实，勿合并**。
"""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 开发工具：取段形态主人
from 代码地图.落点 import 排除目录  # noqa: E402

行数上限 = 400
入口行数上限 = 120
# 扫描面 = **仓内源码**。第六节点名「Rust 与 Python 同一条」是「同一条口径」，
# 不是「只管这两种语言」—— 规则要管的是「改一处时能不能把整个文件读进来」，
# 这件事与语言无关。故前端（`.js` / `.css` / `.html`）与脚本（`.sh` / `.swift`）一并进。
# 依据：`项目文档/决策记录/2026-09-27_行数硬数与拆分面裁决.md` §二③（**不给前端开后门**：
# 开后门就是「同一件事两套口径」）。实测这一步不改变任何既有读数（前端现无一件超限），
# 只堵住将来。
源码后缀 = (".rs", ".py", ".js", ".css", ".html", ".sh", ".swift")
# 跳过目录 = **段形态主人**（`开发工具/代码地图/落点.py::排除目录`）± 本面增量：本面扫全仓源码，
# 但**不排** `只读参考`（只收参考件，无源码后缀）与 `.codegraph`（只放索引库）⇒ 减掉；增量 = `__pycache__`。
跳过目录 = set(排除目录) - {"只读参考", ".codegraph"} | {"__pycache__"}
入口件名 = {"lib.rs", "main.rs", "mod.rs"}

# Rust 语法的顶层项定义（含 `pub` / `pub(crate)` / `unsafe` / `extern "C"` 前缀）——
# 名字不带「Rust」二字：与它并列的那几条是 Python 语法，各由注释与本名自明。
顶层项行模式 = re.compile(
    r"^(?:pub(?:\s*\([^)]*\))?\s+)?(?:unsafe\s+)?(?:extern\s+\"[^\"]*\"\s+)?"
    r"(fn|struct|enum|trait|impl|const|static|type|union|macro_rules!)\b"
)
定义行模式 = re.compile(r"^(?:async\s+)?(?:def|class)\s+([0-9A-Za-z_\u4e00-\u9fff]+)")
赋值行模式 = re.compile(r"^([0-9A-Za-z_\u4e00-\u9fff]+)\s*(?::[^=]+)?=(?!=)")
主入口行模式 = re.compile(r"^if __name__ == ['\"]__main__['\"]:", re.M)


def 是源码(名称):
    return 名称.endswith(源码后缀)


def 收集源码(仓根):
    命中表 = []
    for 当前, 目录表, 文件表 in os.walk(仓根):
        目录表[:] = [目录 for 目录 in 目录表 if 目录 not in 跳过目录]
        for 名称 in sorted(文件表):
            if 是源码(名称):
                命中表.append(os.path.relpath(os.path.join(当前, 名称), 仓根))
    return sorted(命中表)


def 读文本(路径):
    with open(路径, encoding="utf-8", errors="replace") as 文件句柄:
        return 文件句柄.read()


def 入口类别(相对路, 文本):
    """返回入口类别；不是入口给 None。"""
    名称 = os.path.basename(相对路)
    if 名称 in 入口件名:
        return "rust"
    if 名称 == "__init__.py":
        return "py-init"
    if 名称.endswith(".py") and 主入口行模式.search(文本):
        return "py-script"
    return None


def 入口实现项(类别, 相对路, 文本):
    """入口文件里「不该有」的顶层实现项清单（逐条给原文，便于定位）。"""
    命中表 = []
    if 类别 == "rust":
        # 二进制入口 `main.rs` 的 `fn main` 是语言强制，不是「实现」——唯一豁免。
        豁免主函数 = os.path.basename(相对路) == "main.rs"
        for 序号, 源码行 in enumerate(文本.splitlines(), 1):
            匹配 = 顶层项行模式.match(源码行.strip())
            if 匹配:
                if 豁免主函数 and 匹配.group(1) == "fn" and 源码行.strip().startswith(("fn main(", "pub fn main(")):
                    continue
                命中表.append((序号, 匹配.group(1), 源码行.strip()))
    elif 类别 == "py-init":
        for 序号, 源码行 in enumerate(文本.splitlines(), 1):
            匹配 = 定义行模式.match(源码行)
            if 匹配:
                命中表.append((序号, "def/class " + 匹配.group(1), 源码行.strip()))
                continue
            匹配 = 赋值行模式.match(源码行)
            if 匹配 and 匹配.group(1) != "__all__":
                命中表.append((序号, "赋值 " + 匹配.group(1), 源码行.strip()))
    else:  # py-script：只许一个入口函数
        定义 = []
        for 序号, 源码行 in enumerate(文本.splitlines(), 1):
            匹配 = 定义行模式.match(源码行)
            if 匹配:
                定义.append((序号, 匹配.group(1), 源码行.strip()))
        if len(定义) > 1:
            命中表 = 定义[1:]
    return 命中表


def 扫一遍(仓根):
    超行数 = []
    入口超行数 = []
    入口有实现 = []
    for 相对路 in 收集源码(仓根):
        文本 = 读文本(os.path.join(仓根, 相对路))
        行数 = len(文本.splitlines())
        if 行数 > 行数上限:
            超行数.append((行数, 相对路))
        类别 = 入口类别(相对路, 文本)
        if 类别 is None:
            continue
        if 行数 > 入口行数上限:
            入口超行数.append((行数, 相对路))
        实现 = 入口实现项(类别, 相对路, 文本)
        if 实现:
            入口有实现.append((相对路, 实现))
    return 超行数, 入口超行数, 入口有实现


def 报读数(仓根, 结果):
    超行数, 入口超行数, 入口有实现 = 结果
    print("=" * 96)
    print(f"仓根 {仓根} · 源码后缀 {源码后缀} · 跳过 {sorted(跳过目录)}")
    print(f"判据：单文件 ≤ {行数上限} 行 · 入口 ≤ {入口行数上限} 行 · 入口零实现")
    print("=" * 96)
    print(f"\n【① 超 {行数上限} 行的文件】共 {len(超行数)} 个")
    for 行数, 路径 in sorted(超行数, reverse=True):
        print(f"    {行数:>6} 行  {路径}")
    if not 超行数:
        print("    无")
    print(f"\n【② 入口文件超 {入口行数上限} 行】共 {len(入口超行数)} 个")
    for 行数, 路径 in sorted(入口超行数, reverse=True):
        print(f"    {行数:>6} 行  {路径}")
    if not 入口超行数:
        print("    无")
    print(f"\n【③ 入口文件含实现】共 {len(入口有实现)} 个")
    for 路径, 实现 in 入口有实现:
        print(f"    {路径}（{len(实现)} 处）")
        for 序号, 类别, 原文 in 实现[:6]:
            print(f"        第 {序号} 行  {类别}  | {原文[:88]}")
        if len(实现) > 6:
            print(f"        …还有 {len(实现) - 6} 处")
    if not 入口有实现:
        print("    无")
    print("\n" + "=" * 96)
    print(f"汇总：① {len(超行数)} 个 · ② {len(入口超行数)} 个 · ③ {len(入口有实现)} 个")


def 自测():
    """反向样本：造超限文件，断言判据抓得住；再造合规文件，断言不误报。"""
    with tempfile.TemporaryDirectory(prefix="查行数自测_") as 临时:
        def 造文件(相对路, 内容):
            路径 = os.path.join(临时, 相对路)
            os.makedirs(os.path.dirname(路径), exist_ok=True)
            with open(路径, "w", encoding="utf-8") as 文件句柄:
                文件句柄.write(内容)
        造文件("超限.rs", "\n".join(f"// 第 {行序} 行" for 行序 in range(行数上限 + 1)) + "\n")
        造文件("入口超行数/lib.rs", "\n".join("// 占位" for _ in range(入口行数上限 + 1)) + "\n")
        造文件("入口含实现/lib.rs", "pub mod 首个;\npub use 首个::次个;\n\nfn 实现() {}\n")
        造文件("入口含实现/__init__.py", '"""包。"""\n\n\ndef 实现():\n    pass\n')
        造文件("入口含实现/脚本.py", 'def 主():\n    pass\n\n\ndef 另一个():\n    pass\n\n\nif __name__ == "__main__":\n    主()\n')
        造文件("合规/lib.rs", "//! 路由。\n\n#[path = \"首个.rs\"]\npub mod 首个;\npub use 首个::次个;\n")
        造文件("合规/脚本.py", 'if __name__ == "__main__":\n    print(1)\n')

        超行数, 入口超行数, 入口有实现 = 扫一遍(临时)
        抓超 = [路径 for _, 路径 in 超行数]
        抓口 = [路径 for _, 路径 in 入口超行数]
        抓实 = [路径 for 路径, _ in 入口有实现]
        断言 = [
            ("①抓得住超 400 行", "超限.rs" in 抓超),
            ("①不误报合规件", "合规/lib.rs" not in 抓超),
            ("②抓得住入口超 120 行", "入口超行数/lib.rs" in 抓口),
            ("③抓得住 rust 入口含 fn", "入口含实现/lib.rs" in 抓实),
            ("③抓得住 __init__.py 含 def", "入口含实现/__init__.py" in 抓实),
            ("③抓得住 py 入口多一个函数", "入口含实现/脚本.py" in 抓实),
            ("③不误报纯路由 lib.rs", "合规/lib.rs" not in 抓实),
            ("③不误报单函数入口脚本", "合规/脚本.py" not in 抓实),
        ]
        失败 = 0
        for 名称, 通过 in 断言:
            print(f"    {'通过' if 通过 else '失败'}  {名称}")
            失败 += 0 if 通过 else 1
        print(f"\n自测：{len(断言) - 失败} / {len(断言)} 通过")
        return 1 if 失败 else 0


def 跑一遍(仓根):
    """扫一遍并报读数（入口只调这一个）。"""
    报读数(仓根, 扫一遍(仓根))
    return 0
