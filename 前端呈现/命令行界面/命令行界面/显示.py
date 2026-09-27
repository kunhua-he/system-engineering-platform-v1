"""显示 —— 只格式化，不判断（判断全在后端；这里只把它的判断摆清楚）。"""

import json


def 显示真假(值) -> str:
    return "是" if 值 is True else ("否" if 值 is False else str(值))


def 漂亮(值) -> str:
    return json.dumps(值, ensure_ascii=False, indent=2)


def 印应答(状态: int, 体文本: str) -> int:
    """打印一条应答。返回退出码。**只按后端给的判定分支**，不自行判成功失败。"""
    状态行 = "HTTP {}".format(状态)
    try:
        体 = json.loads(体文本)
    except ValueError:
        print(状态行 + " —— 应答不是合法 JSON，原样贴出：")
        print(体文本)
        return 3
    if isinstance(体, dict) and 体.get("成功") is False:
        return 印失败(状态行, 体)
    if 状态 >= 400:
        print(状态行 + " —— 请求本身不合法（协议层，不是业务失败）")
    else:
        print(状态行)
    print(漂亮(体))
    return 0


def 印失败(状态行: str, 体: dict) -> int:
    """失败显示 —— `接口面形状.md` §三：`成功:false` + 错误码 + 三项业务判断。"""
    print(状态行 + "  成功：否")
    if isinstance(体.get("错误"), dict):
        错误 = 体["错误"]
        print("  错误码：{}".format(错误.get("码")))
        print("  段位  ：{}".format(错误.get("段位")))
        print("  名称  ：{}".format(错误.get("名称") or "（未登记，后端没编名字）"))
        print("  可重试：{}".format(显示真假(错误.get("可重试"))))
        print("  可自愈：{}".format(显示真假(错误.get("可自愈"))))
        print("  需人工：{}".format(显示真假(错误.get("需人工"))))
        if "已登记" in 错误:
            print("  已登记：{}（旁路项；否 = 这个码在已装载声明里查不到，是一条缺陷证据）"
                  .format(显示真假(错误.get("已登记"))))
    elif isinstance(体.get("校验"), list):
        # `POST /接口/声明` 的失败形状（§四）：逐条「项 · 缺什么 · 为什么不能自愈」。
        print("  校验（{} 条）：".format(len(体["校验"])))
        for 序号, 条 in enumerate(体["校验"], 1):
            print("   {}. 项：{}".format(序号, 条.get("项")))
            print("      缺什么：{}".format(条.get("缺什么")))
            print("      为什么不能自愈：{}".format(条.get("为什么不能自愈")))
    elif "协议错误" in 体:
        print("  协议错误：{}".format(体["协议错误"]))
    else:
        print("  返回体：")
        print(漂亮(体))
    if "耗时微秒" in 体:
        print("  耗时微秒：{}".format(体["耗时微秒"]))
    return 1


def 印调用成功(状态: int, 体: dict) -> int:
    """成功显示 —— `接口面形状.md` §三：`成功: true` + `值`（每项自带 `类型标签`）+ `耗时微秒`。
    槽里若还有旁路项（实测有 `引用` · `长度`），一并摆出来：**不吞后端给的事实**。"""
    print("HTTP {}  成功：是".format(状态))
    for 序号, 槽 in enumerate(体.get("值") or []):
        if not isinstance(槽, dict):
            print("  值[{}]：{}".format(序号, 槽))
            continue
        原值 = 槽.get("值")
        标注 = ""
        if 槽.get("类型标签") == 5 and isinstance(原值, str):
            标注 = "（base64，{} 字符）".format(len(原值))
        旁路 = "".join(
            "  {}={}".format(键, json.dumps(值, ensure_ascii=False))
            for 键, 值 in 槽.items() if 键 not in ("类型标签", "值")
        )
        print("  值[{}]  类型标签={}{}{}".format(序号, 槽.get("类型标签"), 标注, 旁路))
        print("        {}".format(原值))
    for 键 in 体:
        if 键 not in ("成功", "值"):
            print("  {}：{}".format(键, json.dumps(体[键], ensure_ascii=False)))
    return 0
