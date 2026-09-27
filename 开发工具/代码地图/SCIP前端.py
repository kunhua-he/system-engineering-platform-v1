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
三条腿表 = {
    "rs": ("rust-analyzer", "rustup component add rust-analyzer"),
    "py": ("scip-python", "npm i -g @sourcegraph/scip-python"),
    "js": ("scip-typescript", "npm i -g @sourcegraph/scip-typescript"),
}
读回工具名 = "scip"
读回工具装法 = ("从 https://github.com/scip-code/scip/releases 下 scip-darwin-arm64.tar.gz，"
                "解出的 `scip` 放进 PATH（或 ~/.local/bin）")

# SCIP `SymbolInformation.Kind` 枚举 → 中文（照 scip.proto 的编号，不猜）
符号种类表 = {
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
文档首词种类表 = {
    "function": "函数", "class": "类", "module": "模块", "var": "变量", "let": "变量",
    "const": "常量", "interface": "接口", "type": "类型别名", "enum": "枚举", "property": "属性",
    "method": "方法", "namespace": "命名空间", "constructor": "构造器",
    "(parameter)": "形参", "(module)": "模块", "(variable)": "变量", "(property)": "属性",
    "(function)": "函数", "(class)": "类",
}

# descriptor 的记号后缀 → 种类（SCIP 描述符语法：`名` 后跟 / # . (). : []）
记号后缀种类表 = {"方法": "方法", "类型": "类型", "命名空间": "模块", "类型参数": "类型参数"}

_文档首词 = re.compile(r"^\s*(\([a-z]+\)|[A-Za-z]+)")


def 找工具(工具名: str) -> str:
    """工具在不在 PATH 上；不在 ⇒ 空串（调用方据此报「哪条腿没跑」）。"""
    return shutil.which(工具名) or ""


def 缺哪些工具() -> list:
    """缺哪几件工具 ⇒ `[(语言键, 工具名, 装法)]`（空表 = 三条腿都能跑）。"""
    缺失工具表 = []
    for 语言键, (工具名, 装法说明) in 三条腿表.items():
        if not 找工具(工具名):
            缺失工具表.append((语言键, 工具名, 装法说明))
    if not 找工具(读回工具名):
        缺失工具表.append(("读回", 读回工具名, 读回工具装法))
    return 缺失工具表


def _跑命令(命令表: list, 仓根: Path) -> tuple:
    """跑一条索引器命令 ⇒ `(退出码, 标准输出文本)`。索引器把日志写 stderr，这里吞掉。

    **有意不设超时**（仓里 `cargo` / `nm` / 闸 0 起子进程同样不设）：索引器一趟就是它自身的
    时长（实测最慢那条 12.9 s），这是**环境步**、由 `报告环境步` 照实报墙钟。给它配一个
    >5 s 的容忍度，正是判据 ㊲ 禁的那种「把硬顶让给被调方」的假数字。
    """
    try:
        命令回执 = subprocess.run(命令表, cwd=str(仓根), capture_output=True, check=False)
    except OSError:
        return 1, ""
    return 命令回执.returncode, 命令回执.stdout.decode("utf-8", "replace")


def 拼索引命令(语言键: str, 仓根: Path, 原始索引路径: Path, js目录表: list) -> list:
    """按语言给命令行。JS 那条要把**有 JS 的目录**逐个点出来（`scip-typescript` 不扫全仓）。"""
    if 语言键 == "rs":
        return ["rust-analyzer", "scip", str(仓根), "--exclude-vendored-libraries",
                "--output", str(原始索引路径)]
    if 语言键 == "py":
        return ["scip-python", "index", ".", "--project-name=v1", "--output", str(原始索引路径)]
    return ["scip-typescript", "index", "--infer-tsconfig", "--output", str(原始索引路径)] + list(js目录表)


def 跑一条腿(语言键: str, 仓根: Path, 原始索引路径: Path, js目录表: list) -> dict:
    """跑一条腿的索引器 ⇒ `{"语言键","退出码","字节数","清理数"}`。**只报读数，不判顶**。

    **JS 那条腿有个副作用要收**：`scip-typescript` 没有 `--tsconfig` 选项，项目目录里没有
    `tsconfig.json` 时只能靠 `--infer-tsconfig` 让它**自身写一个进源码树**。跑完把
    「**原本没有、被它新建的**」删掉（判据 ⑳：运行数据不落源码树），删了几个如实报在 `清理数`。
    原本就有的**一个都不动**。
    """
    原始索引路径.parent.mkdir(parents=True, exist_ok=True)
    原本已有配置 = {目录: (仓根 / 目录 / "tsconfig.json").is_file() for 目录 in js目录表}
    退出码, _ = _跑命令(拼索引命令(语言键, 仓根, 原始索引路径, js目录表), 仓根)
    清理数 = 0
    for 目录, 本来就有 in 原本已有配置.items():
        配置路径 = 仓根 / 目录 / "tsconfig.json"
        if not 本来就有 and 配置路径.is_file():
            配置路径.unlink()
            清理数 += 1
    字节数 = 原始索引路径.stat().st_size if 原始索引路径.is_file() else 0
    if 退出码 != 0 or 字节数 == 0:
        原始索引路径.unlink(missing_ok=True)
    return {"语言键": 语言键, "退出码": 退出码, "字节数": 字节数, "清理数": 清理数}


def 读回索引(原始索引路径: Path) -> dict:
    """`scip print --json` ⇒ 一份 SCIP 索引（`{"metadata","documents","external_symbols"}`）。

    索引器自身的 JSON 已经在 `跑一条腿` 里落盘了 —— 这里只把 `.scip`（protobuf）翻成 JSON。
    """
    退出码, 标准输出 = _跑命令(
        [读回工具名, "print", "--json", str(原始索引路径)], 原始索引路径.parent)
    if 退出码 != 0 or not 标准输出.strip():
        return {}
    try:
        return json.loads(标准输出)
    except json.JSONDecodeError:
        return {}


def _拆名字段(描述串: str) -> list:
    """SCIP descriptor → `[(段名, 记号种类)]`。

    记号后缀照 SCIP 描述符语法：`/` 层级 · `.` 词项 · `()` `.` 方法 · `#` 类型 · `:` 命名空间 · `[]` 类型参数。
    **形参 `(名)` 也要留成一段**（不然 `` `建`().(`标签`) `` 与 `` `建`(). `` 会撞成同一个限定名）；
    `[...]` 是 Rust 的 impl/trait 括号（`impl#[…][…]Item#`），**整段跳过**（那是噪声，不是名字）。
    """
    名字段表 = []
    游标 = 0
    while 游标 < len(描述串):
        当前字符 = 描述串[游标]
        if 当前字符 == "(":
            配对右括号位 = 描述串.find(")", 游标 + 1)
            if 配对右括号位 < 0:
                break
            形参名 = 描述串[游标 + 1:配对右括号位].strip().strip("`")
            if 形参名:
                名字段表.append((形参名, "形参"))
            游标 = 配对右括号位 + 1
            continue
        if 当前字符 == "[":
            配对右方括号位 = 描述串.find("]", 游标 + 1)
            游标 = len(描述串) if 配对右方括号位 < 0 else 配对右方括号位 + 1
            continue
        if 当前字符 == "`":
            配对反引号位 = 描述串.find("`", 游标 + 1)
            if 配对反引号位 < 0:
                break
            段名, 游标 = 描述串[游标 + 1:配对反引号位], 配对反引号位 + 1
        elif 当前字符.isalnum() or 当前字符 == "_":
            名字末位 = 游标
            while 名字末位 < len(描述串) and (描述串[名字末位].isalnum() or 描述串[名字末位] == "_"):
                名字末位 += 1
            段名, 游标 = 描述串[游标:名字末位], 名字末位
        else:
            游标 += 1
            continue
        记号种类 = ""
        if 描述串.startswith("().", 游标):
            记号种类, 游标 = "方法", 游标 + 3
        elif 描述串.startswith(".", 游标):
            记号种类, 游标 = "词项", 游标 + 1
        elif 描述串.startswith("#", 游标):
            记号种类, 游标 = "类型", 游标 + 1
        elif 描述串.startswith(":", 游标):
            记号种类, 游标 = "命名空间", 游标 + 1
        elif 描述串.startswith("[]", 游标):
            记号种类, 游标 = "类型参数", 游标 + 2
        if 段名:
            名字段表.append((段名, 记号种类))
    return 名字段表


# `scip-typescript` 给匿名局部变量的记号：descriptor 是 `local <序号>`（全仓每个文件都从 1 起 ⇒ 会撞）
_匿名局部记号 = re.compile(r"^local (\d+)$")


def 拆符号串(符号串: str, 仓根名: str, 所属文件: str = "") -> dict:
    """SCIP 符号串 ⇒ `{"限定名","名字","记号种类"}`。

    `scip-typescript` 会把**绝对路径**塞进 descriptor（`Documents/Agent/PHP/<仓名>/…`）⇒
    按仓名裁掉它前面那段（不然打印出来全是噪声）。这是**纯函数**（只依赖符号串与仓名），
    所以同符号在任何文件里都得到同一根限定名 —— 下游按它做精确匹配。

    **例外**：`local <序号>` 不是纯函数能定的（它只在文件内唯一）⇒ 得把 `所属文件` 掺进来
    （`<路径>::局部<序号>`）。不掺就会把全仓所有文件的 1 号局部变量并成一个符号。
    """
    符号分段 = 符号串.split(" ", 4)
    描述串 = 符号分段[4] if len(符号分段) > 4 else 符号串
    匿名匹配 = _匿名局部记号.match(描述串)
    if 匿名匹配:
        return {"限定名": "%s::局部%s" % (所属文件, 匿名匹配.group(1)),
                "名字": "局部" + 匿名匹配.group(1), "记号种类": "变量"}
    名字段表 = _拆名字段(描述串)
    if 仓根名:
        for 段位, (段名, _) in enumerate(名字段表):
            if 段名 == 仓根名:
                名字段表 = 名字段表[段位 + 1:]
                break
    名字 = 名字段表[-1][0] if 名字段表 else ""
    记号种类 = 记号后缀种类表.get(名字段表[-1][1], "") if 名字段表 else ""
    return {"限定名": "::".join(段名 for 段名, _ in 名字段表), "名字": 名字, "记号种类": 记号种类}


def _取声明行(符号信息: dict) -> str:
    """取该符号的**声明行**：Rust 用 `signature_documentation`，另两条用 `documentation` 首段的代码块。"""
    签名字段 = (符号信息.get("signature_documentation") or {}).get("text")
    if 签名字段:
        return 签名字段.strip().split("\n")[0][:200]
    for 文档文本 in (符号信息.get("documentation") or []):
        反引号分段 = 文档文本.split("```")
        if len(反引号分段) >= 3:
            return 反引号分段[1].strip().split("\n")[0][:200]
        if 文档文本.strip():
            return 文档文本.strip().split("\n")[0][:200]
    return ""


def _判符号种类(符号信息: dict, 记号种类: str) -> str:
    """种类：Rust 用 SCIP 的 `kind`（权威）；另两条从文档领头词推，推不出就退记号种类，
    再推不出就**空着**（未判）。"""
    种类编号 = 符号信息.get("kind")
    if isinstance(种类编号, int) and 种类编号 in 符号种类表:
        return 符号种类表[种类编号]
    文档首词匹配 = _文档首词.match(_取声明行(符号信息))
    if 文档首词匹配 and 文档首词匹配.group(1) in 文档首词种类表:
        return 文档首词种类表[文档首词匹配.group(1)]
    return 记号种类


def _取起止(范围: list) -> tuple:
    """SCIP range ⇒ `(行 1 基, 列 0 基)`。4 段是跨行 `[起行,起列,末行,末列]`，3 段是同行。"""
    if not 范围:
        return 0, 0
    return 范围[0] + 1, 范围[1]


def 转统一形状(索引: dict, 语言键: str, 仓根名: str) -> dict:
    """一份 SCIP 索引 ⇒ 统一形状 `{"定义": [...], "出现": [...], "文档数": n, "符号数": n}`。

    **定义 = 带 `SymbolRole.Definition`（位 1）的出现** —— 没有这一位的符号**不进定义表**：
    它是**外部符号**（标准库/依赖）或**宏生成的**（如 `#[derive(Default)]` 出来的 `default`），
    本仓里只有读、没有源定义。以前把它挂在「第一次读它的地方」当定义，那是**假定义**
    （`查 sys` 会答「`sys` 定义在某个只是 import 了它的文件里」）⇒ 已改掉。
    出现 = **全部**出现（定义处也算一次）。
    """
    定义表, 出现表 = [], []
    符号信息表: dict = {}
    for 文档 in (索引.get("documents") or []):
        for 符号信息 in (文档.get("symbols") or []):
            if 符号信息.get("symbol"):
                符号信息表[符号信息["symbol"]] = 符号信息

    出现位表: dict = {}
    for 文档 in (索引.get("documents") or []):
        相对路径 = 文档.get("relative_path", "")
        for 出现 in (文档.get("occurrences") or []):
            符号串 = 出现.get("symbol")
            if not 符号串:
                continue
            行号, 列号 = _取起止(出现.get("range") or [])
            出现位表.setdefault(符号串, []).append(
                (相对路径, 行号, 列号, bool(出现.get("symbol_roles", 0) & 1)))

    for 符号串, 该符号出现位表 in 出现位表.items():
        符号信息 = 符号信息表.get(符号串, {})
        定义位置表 = [位点 for 位点 in 该符号出现位表 if 位点[3]]
        首次出现 = 该符号出现位表[0]
        拆解结果 = 拆符号串(符号串, 仓根名, 首次出现[0])
        名字 = 符号信息.get("display_name") or 拆解结果["名字"]
        限定名 = 拆解结果["限定名"]
        for 相对路径, 行号, 列号, _ in 该符号出现位表:
            出现表.append({"语言": 语言键, "路径": 相对路径, "名字": 名字,
                          "限定名": 限定名, "行": 行号, "列": 列号})
        if not 定义位置表:
            continue
        首个定义位置 = 定义位置表[0]
        定义表.append({
            "语言": 语言键, "路径": 首个定义位置[0], "名字": 名字, "限定名": 限定名,
            "种类": _判符号种类(符号信息, 拆解结果["记号种类"]),
            "行": 首个定义位置[1], "列": 首个定义位置[2],
            "声明": _取声明行(符号信息), "出现数": len(该符号出现位表),
            "定义处数": len(定义位置表), "符号": 符号串,
        })

    定义表.sort(key=lambda 定义记录: (定义记录["路径"], 定义记录["行"], 定义记录["限定名"]))
    出现表.sort(key=lambda 出现记录: (出现记录["路径"], 出现记录["行"], 出现记录["列"]))
    return {"定义": 定义表, "出现": 出现表,
            "文档数": len(索引.get("documents") or []), "符号数": len(出现位表)}


def 跑三条腿(仓根: Path, 取原始路径, js目录表: list) -> tuple:
    """**并发**跑三条索引器（子进程 ⇒ 不吃 GIL）⇒ `(腿读数表, 读回结果表)`。

    并发在这里是**安全的**：三条腿各写各的 `.scip`，互不相干；读数只进环境步的回执。
    """
    待跑腿表 = [(语言键, 取原始路径(语言键)) for 语言键 in 三条腿表 if 找工具(三条腿表[语言键][0])]
    if not 待跑腿表:
        return [], []
    with ThreadPoolExecutor(max_workers=len(待跑腿表)) as 线程池:
        腿读数表 = list(线程池.map(
            lambda 一条腿: 跑一条腿(一条腿[0], 仓根, 一条腿[1], js目录表), 待跑腿表))
    可读腿表 = [(一条腿[0], 一条腿[1])
              for 一条腿, 读数 in zip(待跑腿表, 腿读数表) if 读数["退出码"] == 0]
    if not 可读腿表:
        return 腿读数表, []
    with ThreadPoolExecutor(max_workers=len(可读腿表)) as 线程池:
        读回结果表 = list(线程池.map(lambda 一条腿: (一条腿[0], 读回索引(一条腿[1])), 可读腿表))
    return 腿读数表, 读回结果表
