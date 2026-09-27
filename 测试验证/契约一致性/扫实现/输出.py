# -*- coding: utf-8 -*-
"""输出 —— 打印（三元读数 + 失败/未判逐条）与 打印读数（扫描面 · 读数 · 样本状态）。"""
from __future__ import annotations

import sys


def 打印(结果: list, 耗时毫秒=None, 流=None) -> None:
    流 = 流 or sys.stdout
    通过 = [r for r in 结果 if r["判定"] == "通过"]
    失败 = [r for r in 结果 if r["判定"] == "失败"]
    未判 = [r for r in 结果 if r["判定"] == "未判"]
    未验 = [r for r in 结果 if not r["已验证"]]
    尾 = f" · 耗时 {耗时毫秒} ms" if 耗时毫秒 is not None else ""
    print(
        f"通过 {len(通过)} 项 · 失败 {len(失败)} 项 · 未判 {len(未判)} 项{尾}",
        file=流,
    )
    if 未验:
        print(
            f"（其中 {len(未验)} 条判据**未验证**：缺正向或反向样本，其「通过」不计入通过数）",
            file=流,
        )
    if 失败:
        print("", file=流)
        print("失败逐条：", file=流)
        for r in 失败:
            for d in r["明细"]:
                if d["判定"] != "失败":
                    continue
                print(
                    f"- {r['项']} ｜ {d['位置']} ｜ 缺什么：{d['缺什么']} ｜ "
                    f"为什么不能自愈：{d['为什么不能自愈']} ｜ 红类：{d['红类'] or '源码错'}",
                    file=流,
                )
    if 未判:
        print("", file=流)
        print("未判逐条（空集与判不了都不算通过）：", file=流)
        for r in 未判:
            for d in r["明细"]:
                if d["判定"] != "未判":
                    continue
                print(
                    f"- {r['项']} ｜ {d['位置']} ｜ {d['缺什么']} ｜ 为什么不能自愈：{d['为什么不能自愈']}",
                    file=流,
                )


def 打印读数(结果: list) -> None:
    print("每条判据的扫描面 · 实际读数 · 样本状态（元判据用）：")
    for r in 结果:
        print(f"· {r['项']}")
        print(f"  判定：{r['判定']}{'（未验证）' if not r['已验证'] else ''} · 红类：{r['红类'] or '—'} · 已判 {r['已判']} 项")
        print(f"  扫描面：{r['扫描面']}")
        print(f"  扫描读数：{r['扫描读数']}")
        print(f"  样本：正向={r['样本']['正向']} 反向={r['样本']['反向']}")
