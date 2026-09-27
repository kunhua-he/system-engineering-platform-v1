# -*- coding: utf-8 -*-
"""代码地图 · 前端 —— 调 **SCIP** 索引器（Sourcegraph 开源，业界标准），读回 JSON，转**统一形状**。

**为什么是 SCIP，不是自研解析器**：自研只做得到「名字级」——同一模块内精确，跨模块靠猜。
SCIP 是**带作用域**的：每个符号有一根**全局唯一的符号串**（`scheme manager package version
descriptor`）。三条腿都能给，于是「谁是定义、谁在引用它」答得**精确**，且三种语言**同一套口径**
（不许像自研版那样把 Rust 一条腿做精确、另两条做成名字级）。

索引器（三条腿，都是**环境依赖**，不是底座能力 —— 见 `决策记录/2026-09-27_代码地图.md` §三）：
  · `.rs` → `rust-analyzer scip`（Rust 官方组件）
  · `.py` → `scip-python`（`npm i -g @sourcegraph/scip-python`）
  · `.js` → `scip-typescript`（`npm i -g @sourcegraph/scip-typescript`）
读回：`scip print --json`（Sourcegraph 的 `scip` CLI，Go 单文件二进制）。

**位置口径**：SCIP 的 `range` 是 **UTF-16 列**（`position_encoding`），与 LSIF 一致 ⇒ 沿用
「**行 1 基 · 列 0 基**」的老口径，下游（符号级替换）不用改。
"""

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 三条腿：语言键 → (索引器可执行名, 装法)。语言键与 `落点.原始路径` 的键同一套。
腿表 = {
    "rs": ("rust-analyzer", "rustup component add rust-analyzer"),
    "py": ("scip-python", "npm i -g @sourcegraph/scip-python"),
    "js": ("scip-typescript", "npm i -g @sourcegraph/scip-typescript"),
}
读回工具 = "scip"
读回装法 = ("从 https://github.com/scip-code/scip/releases 下 scip-darwin-arm64.tar.gz，"
            "解出的 `scip` 放进 PATH（或 ~/.local/bin）")

# SCIP `SymbolInformation.Kind` 枚举 → 中文（照 scip.proto 的编号，不猜）
种类表 = {
    1: "数组", 2: "断言", 3: "关联类型", 4: "注解属性", 5: "公理", 6: "布尔", 7: "类", 8: "常量",
    9: "构造器", 10: "数据族", 11: "枚举", 12: "枚举成员", 13: "事件", 14: "事实", 15: "字段",
    16: "文件", 17: "函数", 18: "取值器", 19: "文法", 20: "实例", 21: "接口", 22: "键", 23: "语言",
    24: "引理", 25: "宏", 26: "方法", 27: "方法接收者", 28: "消息", 29: "模块", 30: "命名空间",
    31: "空", 32: "数", 33: "对象", 34: "运算符", 35: "包", 36: "包对象", 37: "形参",
    38: "形参标签", 39: "模式", 40: "谓词", 41: "属性", 42: "协议", 43: "准引用", 44: "自身形参",
    45: "设值器", 46: "签名", 49: "结构体", 53: "特征", 55: "类型别名", 58: "类型参数",
    61: "变量", 62: "合约", 63: "错误", 64: "库", 65: "修饰符", 66: "抽象方法", 67: "方法规格",
    68: "协议方法", 69: "纯虚方法", 70: "特征方法", 72: "访问器", 73: "委托", 74: "方法别名",
    75: "单例类", 76: "单例方法", 80: "静态方法", 82: "静态变量", 84: "扩展", 85: "混入",
    86: "概念",
}

# 文档首行是 `(parameter) 标签: any` / `function 建(...)` 这种 ⇒ 领头词给种类（Python/JS 没有 kind 字段）
文档种类表 = {
    "function": "函数", "class": "类", "module": "模块", "var": "变量", "let": "变量",
    "const": "常量", "interface": "接口", "type": "类型别名", "enum": "枚举", "property": "属性",
    "method": "方法", "namespace": "命名空间", "constructor": "构造器",
    "(parameter)": "形参", "(module)": "模块", "(variable)": "变量", "(property)": "属性",
    "(function)": "函数", "(class)": "类",
}

# descriptor 的记号后缀 → 种类（SCIP 描述符语法：`名` 后跟 / # . (). : []）
记号种类 = {"方法": "方法", "类型": "类型", "命名空间": "模块", "类型参数": "类型参数"}

_文档首行 = re.compile(r"^\s*(\([a-z]+\)|[A-Za-z]+)")


def 找工具(名: str) -> str:
    """工具在不在 PATH 上；不在 ⇒ 空串（调用方据此报「哪条腿没跑」）。"""
    return shutil.which(名) or ""


def 缺什么() -> list:
    """缺哪几件工具 ⇒ `[(语言键, 工具名, 装法)]`（空表 = 三条腿都能跑）。"""
    出 = []
    for 键, (工具, 装法) in 腿表.items():
        if not 找工具(工具):
            出.append((键, 工具, 装法))
    if not 找工具(读回工具):
        出.append(("读回", 读回工具, 读回装法))
    return 出


def _跑(命令: list, 仓根: Path) -> tuple:
    """跑一条索引器命令 ⇒ `(退出码, 标准输出文本)`。索引器把日志写 stderr，这里吞掉。

    **有意不设超时**（仓里 `cargo` / `nm` / 闸 0 起子进程同样不设）：索引器一趟就是它自己的
    时长（实测最慢那条 12.9 s），这是**环境步**、由 `报告环境步` 照实报墙钟。给它配一个
    >5 s 的容忍度，正是判据 ㊲ 禁的那种「把硬顶让给被调方」的假数字。
    """
    try:
        果 = subprocess.run(命令, cwd=str(仓根), capture_output=True, check=False)
    except OSError:
        return 1, ""
    return 果.returncode, 果.stdout.decode("utf-8", "replace")


def 索引命令(语言键: str, 仓根: Path, 出路径: Path, js目录表: list) -> list:
    """按语言给命令行。JS 那条要把**有 JS 的目录**逐个点出来（`scip-typescript` 不扫全仓）。"""
    if 语言键 == "rs":
        return ["rust-analyzer", "scip", str(仓根), "--exclude-vendored-libraries",
                "--output", str(出路径)]
    if 语言键 == "py":
        return ["scip-python", "index", ".", "--project-name=v1", "--output", str(出路径)]
    return ["scip-typescript", "index", "--infer-tsconfig", "--output", str(出路径)] + list(js目录表)


def 建腿(语言键: str, 仓根: Path, 出路径: Path, js目录表: list) -> dict:
    """跑一条腿的索引器 ⇒ `{"键","码","字节","清理"}`。**只报读数，不判顶**（调用方按环境步报）。

    **JS 那条腿有个副作用要收**：`scip-typescript` 没有 `--tsconfig` 选项，项目目录里没有
    `tsconfig.json` 时只能靠 `--infer-tsconfig` 让它**自己写一个进源码树**。跑完把
    「**原本没有、被它新建的**」删掉（判据 ⑳：运行数据不落源码树），删了几个如实报在 `清理`。
    原本就有的**一个都不动**。
    """
    出路径.parent.mkdir(parents=True, exist_ok=True)
    原有 = {目录: (仓根 / 目录 / "tsconfig.json").is_file() for 目录 in js目录表}
    码, _ = _跑(索引命令(语言键, 仓根, 出路径, js目录表), 仓根)
    清理 = 0
    for 目录, 本有 in 原有.items():
        路 = 仓根 / 目录 / "tsconfig.json"
        if not 本有 and 路.is_file():
            路.unlink()
            清理 += 1
    字节 = 出路径.stat().st_size if 出路径.is_file() else 0
    if 码 != 0 or 字节 == 0:
        出路径.unlink(missing_ok=True)
    return {"键": 语言键, "码": 码, "字节": 字节, "清理": 清理}


def 读索引(出路径: Path) -> dict:
    """`scip print --json` ⇒ 一份 SCIP 索引（`{"metadata","documents","external_symbols"}`）。

    索引器自己的 JSON 已经在 `建腿` 里落盘了 —— 这里只把 `.scip`（protobuf）翻成 JSON。
    """
    码, 文本 = _跑([读回工具, "print", "--json", str(出路径)], 出路径.parent)
    if 码 != 0 or not 文本.strip():
        return {}
    try:
        return json.loads(文本)
    except json.JSONDecodeError:
        return {}


def _名段(描: str) -> list:
    """SCIP descriptor → `[(名, 记号种类)]`。

    记号后缀照 SCIP 描述符语法：`/` 层级 · `.` 词项 · `()` `.` 方法 · `#` 类型 · `:` 命名空间 · `[]` 类型参数。
    **形参 `(名)` 也要留成一段**（不然 `` `建`().(`标签`) `` 与 `` `建`(). `` 会撞成同一个限定名）；
    `[...]` 是 Rust 的 impl/trait 括号（`impl#[…][…]Item#`），**整段跳过**（那是噪声，不是名字）。
    """
    出 = []
    号 = 0
    while 号 < len(描):
        字 = 描[号]
        if 字 == "(":
            末 = 描.find(")", 号 + 1)
            if 末 < 0:
                break
            内名 = 描[号 + 1:末].strip().strip("`")
            if 内名:
                出.append((内名, "形参"))
            号 = 末 + 1
            continue
        if 字 == "[":
            末 = 描.find("]", 号 + 1)
            号 = len(描) if 末 < 0 else 末 + 1
            continue
        if 字 == "`":
            末 = 描.find("`", 号 + 1)
            if 末 < 0:
                break
            名, 号 = 描[号 + 1:末], 末 + 1
        elif 字.isalnum() or 字 == "_":
            末 = 号
            while 末 < len(描) and (描[末].isalnum() or 描[末] == "_"):
                末 += 1
            名, 号 = 描[号:末], 末
        else:
            号 += 1
            continue
        类 = ""
        if 描.startswith("().", 号):
            类, 号 = "方法", 号 + 3
        elif 描.startswith(".", 号):
            类, 号 = "词项", 号 + 1
        elif 描.startswith("#", 号):
            类, 号 = "类型", 号 + 1
        elif 描.startswith(":", 号):
            类, 号 = "命名空间", 号 + 1
        elif 描.startswith("[]", 号):
            类, 号 = "类型参数", 号 + 2
        if 名:
            出.append((名, 类))
    return 出


# `scip-typescript` 给匿名局部变量的记号：descriptor 是 `local <序号>`（全仓每个文件都从 1 起 ⇒ 会撞）
_局部 = re.compile(r"^local (\d+)$")


def 拆符号(符号: str, 仓根名: str, 路: str = "") -> dict:
    """SCIP 符号串 ⇒ `{"限定名","名字","记号类"}`。

    `scip-typescript` 会把**绝对路径**塞进 descriptor（`Documents/Agent/PHP/<仓名>/…`）⇒
    按仓名裁掉它前面那段（不然打印出来全是噪声）。这是**纯函数**（只依赖符号串与仓名），
    所以同符号在任何文件里都得到同一根限定名 —— 下游按它做精确匹配。

    **例外**：`local <序号>` 不是纯函数能定的（它只在文件内唯一）⇒ 得把 `路` 掺进来
    （`<路>::局部<序号>`）。不掺就会把全仓所有文件的 1 号局部变量并成一个符号。
    """
    段 = 符号.split(" ", 4)
    描 = 段[4] if len(段) > 4 else 符号
    命 = _局部.match(描)
    if 命:
        return {"限定名": "%s::局部%s" % (路, 命.group(1)), "名字": "局部" + 命.group(1),
                "记号类": "变量"}
    名段 = _名段(描)
    if 仓根名:
        for 号, (名, _) in enumerate(名段):
            if 名 == 仓根名:
                名段 = 名段[号 + 1:]
                break
    名字 = 名段[-1][0] if 名段 else ""
    记号类 = 记号种类.get(名段[-1][1], "") if 名段 else ""
    return {"限定名": "::".join(名 for 名, _ in 名段), "名字": 名字, "记号类": 记号类}


def _文档文本(条: dict) -> str:
    """取该符号的**声明行**：Rust 用 `signature_documentation`，另两条用 `documentation` 首段的代码块。"""
    签 = (条.get("signature_documentation") or {}).get("text")
    if 签:
        return 签.strip().split("\n")[0][:200]
    for 文 in (条.get("documentation") or []):
        段 = 文.split("```")
        if len(段) >= 3:
            return 段[1].strip().split("\n")[0][:200]
        if 文.strip():
            return 文.strip().split("\n")[0][:200]
    return ""


def _种类(条: dict, 记号类: str) -> str:
    """种类：Rust 用 SCIP 的 `kind`（权威）；另两条从文档领头词推，推不出就退记号类，再推不出就**空着**（未判）。"""
    号 = 条.get("kind")
    if isinstance(号, int) and 号 in 种类表:
        return 种类表[号]
    文 = _文档文本(条)
    命 = _文档首行.match(文)
    if 命 and 命.group(1) in 文档种类表:
        return 文档种类表[命.group(1)]
    return 记号类


def _起(范围: list) -> tuple:
    """SCIP range ⇒ `(行 1 基, 列 0 基)`。4 段是跨行 `[起行,起列,末行,末列]`，3 段是同行。"""
    if not 范围:
        return 0, 0
    return 范围[0] + 1, 范围[1]


def 转统一(索引: dict, 语言键: str, 仓根名: str) -> dict:
    """一份 SCIP 索引 ⇒ 统一形状 `{"定义": [...], "出现": [...], "文档数": n, "符号数": n}`。

    **定义 = 带 `SymbolRole.Definition`（位 1）的出现** —— 没有这一位的符号**不进定义表**：
    它是**外部符号**（标准库/依赖）或**宏生成的**（如 `#[derive(Default)]` 出来的 `default`），
    本仓里只有读、没有源定义。以前把它挂在「第一次读它的地方」当定义，那是**假定义**
    （`查 sys` 会答「`sys` 定义在某个只是 import 了它的文件里」）⇒ 已改掉。
    出现 = **全部**出现（定义处也算一次）。
    """
    定义, 出现 = [], []
    符表: dict = {}
    for 文 in (索引.get("documents") or []):
        for 条 in (文.get("symbols") or []):
            if 条.get("symbol"):
                符表[条["symbol"]] = 条

    位表: dict = {}
    for 文 in (索引.get("documents") or []):
        路 = 文.get("relative_path", "")
        for 出 in (文.get("occurrences") or []):
            符 = 出.get("symbol")
            if not 符:
                continue
            行, 列 = _起(出.get("range") or [])
            位表.setdefault(符, []).append((路, 行, 列, bool(出.get("symbol_roles", 0) & 1)))

    for 符, 位 in 位表.items():
        条 = 符表.get(符, {})
        定处 = [位点 for 位点 in 位 if 位点[3]]
        首现 = 位[0]
        拆 = 拆符号(符, 仓根名, 首现[0])
        名 = 条.get("display_name") or 拆["名字"]
        限 = 拆["限定名"]
        for 路, 行, 列, _ in 位:
            出现.append({"语言": 语言键, "路径": 路, "名字": 名,
                         "限定名": 限, "行": 行, "列": 列})
        if not 定处:
            continue
        首 = 定处[0]
        定义.append({
            "语言": 语言键, "路径": 首[0], "名字": 名, "限定名": 限,
            "种类": _种类(条, 拆["记号类"]), "行": 首[1], "列": 首[2],
            "声明": _文档文本(条), "出现数": len(位), "定义处数": len(定处),
            "符号": 符,
        })

    定义.sort(key=lambda 条: (条["路径"], 条["行"], 条["限定名"]))
    出现.sort(key=lambda 条: (条["路径"], 条["行"], 条["列"]))
    return {"定义": 定义, "出现": 出现,
            "文档数": len(索引.get("documents") or []), "符号数": len(位表)}


def 跑三条腿(仓根: Path, 原始路径函数, js目录表: list) -> tuple:
    """**并发**跑三条索引器（子进程 ⇒ 不吃 GIL）⇒ `([腿读数…], [读回果…])`。

    并发在这里是**安全的**：三条腿各写各的 `.scip`，互不相干；读数只进环境步的回执。
    """
    任务 = [(键, 原始路径函数(键)) for 键 in 腿表 if 找工具(腿表[键][0])]
    if not 任务:
        return [], []
    with ThreadPoolExecutor(max_workers=len(任务)) as 池:
        腿读数 = list(池.map(lambda 项: 建腿(项[0], 仓根, 项[1], js目录表), 任务))
    能读 = [(项[0], 项[1]) for 项, 读 in zip(任务, 腿读数) if 读["码"] == 0]
    if not 能读:
        return 腿读数, []
    with ThreadPoolExecutor(max_workers=len(能读)) as 池:
        读回果 = list(池.map(lambda 项: (项[0], 读索引(项[1])), 能读))
    return 腿读数, 读回果
