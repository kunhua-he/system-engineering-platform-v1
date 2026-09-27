# -*- coding: utf-8 -*-
"""判据 M1/M2/M3 —— 判据自己的可信性（元判据 · 解析器自检 · 空集不算通过）。"""

from .夹具 import claim, query
from .核心 import P1, P3, T0, core


# ── 元判据 M：判据自己的可信性 ────────────────────────────────────────────────

def meta_check(cases):
    meta = {}
    for 用例 in cases:
        判据元 = meta.setdefault(用例["判据"], {"反向": 0, "正向": 0, "缺": []})
        判据元[用例["类型"]] += 1
    for 判据元 in meta.values():
        判据元["缺"] = [键 for 键 in ("反向", "正向") if 判据元[键] == 0]
        判据元["状态"] = "未验证" if 判据元["缺"] else "已验证"
    return meta


def m1_rev(账本路径):
    """反向样本：注入一条「只有正向样本」的判据，元判据必须报它。"""
    meta = meta_check([{"判据": "J9", "类型": "正向"}])
    ok = meta["J9"]["状态"] == "未验证" and meta["J9"]["缺"] == ["反向"]
    return ok, "注入只有正向样本的判据 J9 ⇒ 元判据报 %s（缺 %s）" % (
        meta["J9"]["状态"], meta["J9"]["缺"])


def m1_pos(账本路径):
    """正向样本：成对的判据 ⇒ 元判据报「已验证」（证明元判据不误报）。"""
    meta = meta_check([{"判据": "J9", "类型": "正向"}, {"判据": "J9", "类型": "反向"}])
    ok = meta["J9"]["状态"] == "已验证" and meta["J9"]["缺"] == []
    return ok, "成对样本的判据 J9 ⇒ 元判据报 %s" % meta["J9"]["状态"]


def m2_pos(账本路径):
    """正向样本：读入一份**已知答案**的账本 ⇒ 报出它读到了多少（判据可信性 §三 #5）。"""
    with core.Ledger(账本路径) as led:
        led.data["租约"] = [
            {"腿标识": "leg-a", "路径集": [P1], "认领时间": core.fmt_ts(T0),
             "到期时间": core.fmt_ts(T0 + 1800.0)},
            {"腿标识": "leg-b", "路径集": [P3], "认领时间": core.fmt_ts(T0),
             "到期时间": core.fmt_ts(T0 + 1800.0)},
        ]
        led.save()
    查询读数 = query(账本路径, now=T0 + 1)
    ok = (查询读数["账本读到总条数"] == 2 and 查询读数["返回条数"] == 2
          and {租约条["腿标识"] for 租约条 in 查询读数["租约"]} == {"leg-a", "leg-b"})
    return ok, "手写 2 条租约 ⇒ 读到总条数=%d · 返回=%d" % (
        查询读数["账本读到总条数"], 查询读数["返回条数"])


def m2_rev(账本路径):
    """反向样本：账本形状坏了必须**报错**，不许静默当空账本（静默空 ⇒ 把「判不了」算成「通过」）。"""
    with open(账本路径, "w", encoding="utf-8") as 柄:
        柄.write('{"格式版本": 1}\n')                 # 缺「租约」数组
    raised = None
    try:
        query(账本路径, now=T0)
    except Exception as 错:
        raised = 错
    ok = isinstance(raised, ValueError)
    return ok, "坏账本 ⇒ %s（若静默返回 0 条，就是假绿）" % (
        type(raised).__name__ if raised is not None else "没报错")


def m3_rev(账本路径):
    """反向样本：空集必须判「未判」，不许算通过（判据可信性 §二 · §三 #4）。"""
    查询读数 = query(账本路径, now=T0)
    ok = 查询读数["返回条数"] == 0 and 查询读数["读数"].startswith("未判")
    return ok, "空账本 ⇒ 返回 %d 条 · 读数「%s」（若算通过就是假绿）" % (查询读数["返回条数"], 查询读数["读数"])


def m3_pos(账本路径):
    """正向样本：非空账本 ⇒ 读数「判得了」。"""
    claim(账本路径, "leg-a", [P1])
    查询读数 = query(账本路径, now=T0 + 1)
    ok = 查询读数["返回条数"] == 1 and 查询读数["读数"] == "判得了"
    return ok, "非空账本 ⇒ 返回 %d 条 · 读数「%s」" % (查询读数["返回条数"], 查询读数["读数"])
