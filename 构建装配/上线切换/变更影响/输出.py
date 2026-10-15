"""输出 —— 变更影响评估的**唯一打印口**：四栏一张表 + 越界汇总。"""


def 打印四栏(基线引用: str, 比对结果: dict) -> None:
    变更行清单 = 比对结果["变更行表"]
    print(f"冻结面变更影响评估（基线 {基线引用[:12]} → 当前盘上那份）", flush=True)
    if not 变更行清单:
        print("  无变更：冻结面与基线逐字一致。", flush=True)
        return
    print(f"  变更项 {len(变更行清单)} 条 · 其中越界 {len(比对结果['越界条目'])} 条", flush=True)
    for 位次, 变更行 in enumerate(变更行清单):
        越界标记 = "【越界】" if 变更行["越界"] else ""
        print(f"  [{位次}]{越界标记} 变更项：{变更行['变更项']}", flush=True)
        print(f"      影响面：{变更行['影响面']}", flush=True)
        print(f"      责任归属：{变更行['责任归属']}", flush=True)
        print(f"      兼容证据：{变更行['兼容证据']}", flush=True)
    if 比对结果["越界条目"]:
        print("  结论：有机制变更没有兼容证据（上面标【越界】的那几条）⇒ 非零退出。", flush=True)
