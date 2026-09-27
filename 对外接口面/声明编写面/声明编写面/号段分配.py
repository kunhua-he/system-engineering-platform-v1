# -*- coding: utf-8 -*-
"""编号自动分配 —— 只从**该层号段的空洞**里取。

**该层 = 该声明根自身声明的「占用」**（`格式说明.md` §二 ★：`平台声明.json` 的
`能力号段` / `通知号段` 是「本声明占哪几段」，扩展那份叫 `包声明.json`）。
`号段图.json` 是**全平台布局**，本模块只用它给出「这个号落在哪一层」的标签。

四条硬规则（`形状.md` §四）：不许从 0 顺排 · 不许复用已作废的号 · 不越层 · 错误码按段位取码区间。
"""

import json
from pathlib import Path

声明文件名 = ("平台声明.json", "包声明.json")

_类别到占用键 = {"能力": "能力号段", "通知号": "通知号段"}

_类别到布局键 = {"能力": "能力号段", "通知号": "通知号段", "错误码": "错误码段位图"}

# 类别 → 作废号表的「号空间」：作废行按号空间分账，面只排除**同空间**的号。
# 号空间互不相通（`契约声明/号段图.json` 的「四个号空间互不相通」＋ `字段名册与引用方式.md`
# §五 的「类型标签 … 与上面四个不通」）：数字相同不算同号（能力号 16 与错误码 16 是两回事）。
# ★ 值域是**五个**：能力 · 类型 · 通知 · 错误码 · 资源。类型标签虽不属号段制（无号段可依，
#   故 `该层号段` 对「类型」fail-closed），但它是独立空间 ⇒ 作废号表里可以有 `号空间: "类型"`
#   的行，面必须按「类型」空间排除它（否则那类作废号在面里等于没作废）。
_类别到号空间 = {"能力": "能力", "类型": "类型", "通知号": "通知", "错误码": "错误码"}


def 读json(路径):
    """读一个 JSON；读不动 / 解析不了 ⇒ None（判不了就说判不了，不猜）。"""
    try:
        return json.loads(Path(路径).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _是整数(值) -> bool:
    return isinstance(值, int) and not isinstance(值, bool)


def 声明文件(声明根):
    """平台声明.json（扩展那份叫 包声明.json，同形状，二者取其一）。"""
    for 名 in 声明文件名:
        路径 = Path(声明根) / 名
        if 路径.is_file():
            return 路径
    return None


def 该层号段(声明根, 类别):
    """→ (段表, 来源说明)。段表 = [(起, 止), …]；判不了时段表为 None、来源说明写缺什么。"""
    声 = 声明文件(声明根)
    if 声 is None:
        return None, "找不到 %s（该层占哪几段没有来源）" % " / ".join(声明文件名)
    数据 = 读json(声)
    if not isinstance(数据, dict):
        return None, "%s 读不动或不是对象" % 声.name

    if 类别 == "错误码":
        # 段位 d ⇒ 码区间 d*1000+1 … d*1000+999（§五：码 = <段位 1 位><序 3 位>；码 0 不是合法码）
        段位表 = 数据.get("错误段位表")
        if not isinstance(段位表, list) or not 段位表:
            return None, "%s 的 错误段位表 缺失或为空（错误码占哪几个段位没有来源）" % 声.name
        段 = []
        for 位 in 段位表:
            if not _是整数(位) or not (0 <= 位 <= 9):
                return None, "%s 的 错误段位表 里有非 0–9 的整数：%r" % (声.name, 位)
            段.append((位 * 1000 + 1, 位 * 1000 + 999))
        return sorted(段), "%s 的 错误段位表 %s（码 = <段位><序 3 位>，序 1–999）" % (声.name, 段位表)

    if 类别 == "类型":
        return None, (
            "§十 待裁第 3 条：类型标签的起始值与分配未裁，类型**不在号段制内**"
            "（有号空间「类型」，但没有号段可依）⇒ "
            "面不猜一个起始值（猜出来的就是第二个事实源），请显式给 编号"
        )

    键 = _类别到占用键.get(类别)
    if 键 is None:
        return None, "未知类别 %r" % (类别,)
    占用 = 数据.get(键)
    if not isinstance(占用, list) or not 占用:
        return None, "%s 的 %s 缺失或为空（该层占哪几段没有来源）" % (声.name, 键)
    段 = []
    for 条 in 占用:
        if not isinstance(条, dict) or not (_是整数(条.get("起")) and _是整数(条.get("止"))):
            return None, "%s 的 %s 形状不对（每段要 {起, 止}）" % (声.name, 键)
        if 条["起"] > 条["止"]:
            return None, "%s 的 %s 有一段 起 > 止：%r" % (声.name, 键, 条)
        段.append((条["起"], 条["止"]))
    return sorted(段), "%s 的 %s %s" % (声.name, 键, 占用)


def 已用号(声明根, 目录, 字段):
    """该目录下已用的号：文件名（= 编号）与 JSON 字段值，两者都收（判据 ① 要求二者一致）。"""
    出 = set()
    根 = Path(声明根) / 目录
    if not 根.is_dir():
        return 出
    for 路径 in sorted(根.glob("*.json")):
        杆 = 路径.name[: -len(".json")]
        if 杆.isdigit():
            出.add(int(杆))
        数据 = 读json(路径)
        if isinstance(数据, dict) and _是整数(数据.get(字段)):
            出.add(int(数据[字段]))
    return 出


def 作废号(声明根, 类别):
    """作废号表.json 里**本类别所属号空间**的号（§七）。

    判据 ③ 是**同空间**口径：作废行带 `号空间`，只排除同一空间里的号 —— 号空间
    互不相通（`契约声明/号段图.json`「四个号空间互不相通」＋ `字段名册与引用方式.md` §五
    的「类型标签 … 与上面四个不通」），数字相同不算同号（错误码 16 与能力号 16 是两回事；
    全局排除会让错误码 16 去封能力号 16，是假冲突）。
    类型有号空间（第五个空间 `类型`）但不在号段制内：本函数照「类型」空间排除，
    而调用方在 `该层号段` 处已先 fail-closed（类型无号段可依，§十 待裁第 3 条）。
    """
    空间 = _类别到号空间.get(类别)
    if 空间 is None:
        return set()
    数据 = 读json(Path(声明根) / "作废号表.json")
    条目 = 数据.get("作废") if isinstance(数据, dict) else None
    出 = set()
    if isinstance(条目, list):
        for 条 in 条目:
            if (
                isinstance(条, dict)
                and 条.get("号空间") == 空间
                and _是整数(条.get("编号"))
            ):
                出.add(int(条["编号"]))
    return 出


def 分配(段表, 已用, 作废):
    """该层号段内第一个空洞；占满 ⇒ None。**不是** 0 起顺排计数器。"""
    for 起, 止 in sorted(段表):
        号 = 起
        while 号 <= 止:
            if 号 not in 已用 and 号 not in 作废:
                return 号
            号 += 1
    return None


def 层标签(声明根, 类别, 编号):
    """这个号落在 `号段图.json` 的哪一层（只做标注，不做归属裁决）。"""
    图 = 读json(Path(声明根) / "号段图.json")
    if not isinstance(图, dict):
        return ""
    键 = _类别到布局键.get(类别)
    if 键 is None:
        return ""
    表 = 图.get(键)
    if not isinstance(表, list):
        return ""
    if 类别 == "错误码":
        位 = 编号 // 1000
        for 条 in 表:
            if isinstance(条, dict) and 条.get("段位") == 位:
                return str(条.get("归属", ""))
        return ""
    for 条 in 表:
        if isinstance(条, dict) and _是整数(条.get("起")) and _是整数(条.get("止")):
            if 条["起"] <= 编号 <= 条["止"]:
                return str(条.get("归属", ""))
    return ""


def 文件名(编号):
    """文件名 = 编号，4 位补零（§一：一个号一个文件）。"""
    return "%04d.json" % 编号
