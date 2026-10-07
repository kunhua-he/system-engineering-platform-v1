# -*- coding: utf-8 -*-
"""操作_批量登记 —— `v1_name` 工具的挂载描述（W3 加载器 glob `操作_*.py` 合并）。

契约（与加载器约定，本件零业务逻辑、只转发仓内正式命令）：
  · `工具名`（str，ASCII）· `工具说明`（str）· `模式`（JSON schema，**不设 required**）；
  · `操作表`：操作名 → `(必需参数元组, 可选参数元组, 最短例字符串)`；
  · `派发`：`(参数表, 仓根) -> (退出码, 输出文本)`，认 `参数表["操作"]`；
    **操作留空 = 只读发现调用**（回操作目录）。

实现全在 `开发工具/信息核心/批量登记.py`（走 `信息核心.py 登记 --批`）—— 本件不抄第二份，
也不手写 SQL。所有操作以**子进程**跑仓内命令（cwd = 仓根 ⇒ 库落点跟树走）。

为何要有它（多路代理实测）：命名闸是当前最大摩擦点 —— 新建一个件时**所有绑定名**
（形参 · 局部 · 函数名 · JS 的 `const` / 解构名）都要在库 `命名登记`（状态=合格），否则
`v1_edit` 写入前整批拒。逐名一次子进程：一条腿为 5 个新件登记 98 次、另一条为 39 个名
登记 39 次还被 5 秒硬顶杀掉 —— 纯机械往返。本工具一次做完，且一次给全读数。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 开发工具/

工具名 = "v1_name"
工具说明 = ("命名登记：一次登记多个名（走仓内正式命令 + 落库，幂等）。新建件时所有绑定名都要在库 "
        "`命名登记`（状态=合格），否则 v1_edit 写入前整批拒 —— 逐名一次子进程是纯机械往返。"
        "`批量登记` 一次给全：成功登记 / 已存在跳过 / 需改名（禁止形状）逐条列名字与理由；"
        "`预检` 只判不写；`落库` 只刷名册（判据 55 名册新鲜度）。")

操作表 = {
    "批量登记": ((), ("表文件", "名单", "落库"),
            '{"操作":"批量登记","参数":{"名单":[["读配置","读配置","动作+对象","新定义"]]}}'),
    "预检": ((), ("表文件", "名单"),
           '{"操作":"预检","参数":{"名单":[["读配置"]]}}'),
    "落库": ((), (), '{"操作":"落库"}'),
}

模式 = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "开工ID": {"type": "string", "description": "给了就在那条开工的工作树里登记（库落点跟树走）"},
        "操作": {"type": "string", "enum": ["批量登记", "预检", "落库"],
               "description": "批量登记=登记并落库；预检=只判不写；落库=只刷名册。"},
        "参数": {"type": "object", "additionalProperties": False, "properties": {
            "表文件": {"type": "string", "description":
                    "批表文件（仓内相对或绝对路径）。JSON（对象/数组/行字符串）或每行 "
                    "`名字<TAB>语义<TAB>模式<TAB>来源`。与 `名单` 二选一。"},
            "名单": {"type": "array", "items": {"type": ["string", "array", "object"]},
                   "description": "行内名单：每条 = {名字,语义,模式,来源} 或 [名字,语义,模式,来源] "
                                "或 \"名字\\t语义\\t模式\\t来源\"。与 `表文件` 二选一。"},
            "落库": {"type": "boolean", "default": True,
                   "description": "批量登记 用：登记完顺带落库（默认真）。大名单可设 false 分批。"},
        }},
    },
}


def 跑信息核心(仓根, 命令表: list) -> tuple:
    """在 `仓根` 里跑一条仓内命令（**子进程** ⇒ 库落点跟树走）；5 秒硬顶。"""
    from .仓操作 import 跑命令
    return 跑命令([sys.executable, "开发工具/信息核心/信息核心.py"] + 命令表,
                cwd=仓根, 超时秒数=5)


def 写名单临时件(名单: list) -> str:
    """把行内名单落成一个临时 JSON 文件 ⇒ 路径（调用方负责删）。"""
    句柄, 临时件 = tempfile.mkstemp(prefix="v1批表_", suffix=".json")
    with os.fdopen(句柄, "w", encoding="utf-8") as 文件句柄:
        文件句柄.write(json.dumps({"名单": 名单}, ensure_ascii=False))
    return 临时件


def 取批表路径(参数表: dict) -> tuple:
    """⇒ `(临时件路径 或 None, 命令用表文件, 错误或空串)`。`名单` 落临时件；`表文件` 直接用。"""
    表文件 = 参数表.get("表文件")
    名单 = 参数表.get("名单")
    if 表文件 and 名单:
        return None, "", "参数拒绝：`表文件` 与 `名单` 只能给一个"
    if 名单 is not None:
        if not isinstance(名单, list):
            return None, "", "参数拒绝：`名单` 要是数组"
        临时件 = 写名单临时件(名单)
        return 临时件, 临时件, ""
    if not 表文件:
        return None, "", "参数拒绝：要给 `表文件`（仓内相对/绝对路径）或 `名单`"
    if not isinstance(表文件, str):
        return None, "", "参数拒绝：`表文件` 要是字符串"
    if 表文件.strip() in ("", "-"):
        return None, "", "参数拒绝：MCP 口不支持标准输入（`-`）；请给 `表文件` 路径或 `名单`"
    return None, 表文件.strip(), ""


def 跑批操作(仓根, 参数表: dict, 干跑: bool) -> tuple:
    """转发一条 `登记 --批`（`干跑` ⇒ 只判不写、不落库）。"""
    临时件, 表文件, 错误 = 取批表路径(参数表)
    if 错误:
        return 2, 错误
    命令表 = ["登记", "--批", 表文件]
    if 干跑:
        命令表 += ["--干跑", "--不落库"]
    elif 参数表.get("落库") is False:
        命令表.append("--不落库")
    try:
        return 跑信息核心(仓根, 命令表)
    finally:
        if 临时件:
            try:
                os.unlink(临时件)
            except OSError:
                pass


def 落库操作(仓根, 参数表: dict) -> tuple:
    """转发一条 `落库`（只刷名册：`命名出现` 全量重写 + `命名登记` 重判状态）。"""
    return 跑信息核心(仓根, ["落库"])


def 操作目录() -> str:
    """只读发现调用（操作留空）的回执：操作名 → 必需 / 可选 / 最短例。"""
    行表 = ["%s 操作目录：%d 个操作" % (工具名, len(操作表))]
    for 操作名 in 操作表:
        必需, 可选, 最短例 = 操作表[操作名]
        行表.append("  %s  必需=%s 可选=%s  例：%s"
                 % (操作名, "、".join(必需) or "（无）", "、".join(可选) or "（无）", 最短例))
    return "\n".join(行表)


def 派发(参数表, 仓根) -> tuple:
    """`v1_name` 入口 ⇒ `(退出码, 输出文本)`。缺 `操作` = 发现；未知 `操作` / 未知键一次拒。

    `参数表` = 整个 `arguments`（`开工ID` / `操作` / `参数` 三字段）。操作参数既可嵌在
    `参数` 下（统一三字段形态），也兼容平铺在顶层（旧加载器）—— 两形都收。
    """
    if not isinstance(参数表, dict):
        return 2, "参数拒绝：arguments 要是对象"
    操作名 = str(参数表.get("操作") or "").strip()
    if not 操作名:
        return 0, 操作目录()
    if 操作名 not in 操作表:
        return 2, "未知 `操作`：%r；可选：%s" % (操作名, "、".join(操作表))
    实参 = 参数表.get("参数")
    if 实参 is None:
        实参 = {键名: 值 for 键名, 值 in 参数表.items() if 键名 not in ("操作", "开工ID")}
    if not isinstance(实参, dict):
        return 2, "参数拒绝：`参数` 要是对象"
    必需, 可选, 最短例 = 操作表[操作名]
    未知键 = sorted(set(实参) - set(必需) - set(可选))
    if 未知键:
        return 2, "未知参数键：%s；本操作只认 %s\n最短例：%s" % (
            "、".join(未知键), "、".join(list(必需) + list(可选)), 最短例)
    if 操作名 == "落库":
        return 落库操作(仓根, 实参)
    return 跑批操作(仓根, 实参, 干跑=(操作名 == "预检"))
