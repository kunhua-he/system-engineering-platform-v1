#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 服务 —— 本仓的开发工具按 MCP 协议暴露（stdio）。

一般由 ZCode 插件按 `.mcp.json` 拉起，不手跑。手动用法：

    python3 开发工具/MCP服务.py            # 走协议（stdio JSON-RPC，永不返回）
    python3 开发工具/MCP服务.py --自检      # 不走协议：协议三帧 + 工具表名单 + 拒绝样本

四个工具（详见 `开发工具/MCP服务/工具.py`）：`v1_task`（开工：登记/补充/查询/释放）·
`v1_symbol`（代码地图）· `v1_edit`（代码修改器，四道闸）· `v1_gate`（验证器，全量 / 只跑指定判据）。
**工具名必须 ASCII**：客户端把非 ASCII 截掉，中文名会截成同一个 `v1_`（实测只活下来
一个）—— 理由与实测见 `工具.py` 顶部那段；中文显示名放协议的 `title` 字段。

`--自检` 是**工具面的身份证**：协议三帧 + 工具表名单 + 工具名 ASCII + 逐类**拒绝样本**
（畸形帧 / `v1_edit` 缺参 · 功能号非法 · 旧内容不唯一 / `v1_task` 非法功能档）
+ **功能档冒烟**（每个功能档至少跑一遍真实路径，断言「不崩」）。
每条样本断言「非零退出码」或「回结构化错误、不崩」，且**一个字节都不改仓**
（内存流 / 纯函数 / 缺参即拒 / 只走查询路）。判据 ㊽（`构建装配/一键验证/一键验证/判据_MCP自检.py`）
跑它：退出码非 0 ⇒ 闸 0 当场红。

**本入口永不返回**（协议主循环），属「结构边界：永不返回」⇒ 不带壳，登记在
`构建装配/一键验证/入口白名单.json`（判据 ㉔）。依据：
`项目文档/决策记录/2026-09-27_构建段归环境步.md` §六 · `2026-09-27_MCP适配层.md`。
"""
import io
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根 / "开发工具"))

from MCP服务 import 工具表, 派发, 跑主循环, 修改  # noqa: E402


def 入口函数(argv=None):
    命令行参数 = list(sys.argv[1:] if argv is None else argv)
    if "--自检" in 命令行参数:
        # 协议层的身份证：自造三帧（initialize / tools/list / 一个不存在的方法），
        # 断言响应形状与工具表 —— 协议层坏了要当场看得出来，不许「连上了但什么也不回」。
        for 方法, 参数 in (("initialize", {"protocolVersion": "试"}),
                          ("tools/list", {}), ("没有这个方法", {})):
            结果, 错误 = 派发(方法, 参数, 仓根, 工具表)
            if 错误:
                print("%s ⇒ 错误码 %d（%s）" % (方法, 错误["code"], 错误["message"]))
            else:
                print("%s ⇒ 键 %s" % (方法, sorted(结果)))
        名表 = sorted(工具表)
        期望 = sorted(["v1_task", "v1_symbol", "v1_edit", "v1_gate"])
        print("工具表：%s" % 名表)
        # 防回潮：客户端把非 ASCII 截掉 ⇒ 中文名会撞成一个。凡非 ASCII 名一律判红
        # （理由见 `MCP服务/工具.py::工具表` 上方注释）。
        非ASCII = [名称 for 名称 in 名表 if not 名称.isascii()]
        if 非ASCII:
            print("★工具名必须 ASCII（客户端会截掉非 ASCII ⇒ 撞名）：%s" % 非ASCII)
        # ── 拒绝样本（审计 A-9 ≡ C-3：工具面的拒绝行为要有反向样本）──
        样本表 = []
        # ① 畸形帧：顶层非对象 / `params` 非对象 / `arguments` 非对象 —— 喂**内存流**，不改盘。
        for 文本 in (
            "123", "null", "[1,2]", '"x"',
            '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":"x"}',
            '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"v1_symbol","arguments":"x"}}',
        ):
            输入, 输出流, 错误 = io.StringIO(文本 + "\n"), io.StringIO(), False
            try:
                跑主循环(仓根, 工具表, 输入=输入, 输出=输出流)
            except Exception:
                错误 = True
            if 错误:
                样本表.append(("畸形帧 %s：现行实现抛异常（待腿 2 修成 fail-closed 后生效）" % 文本, True))
            else:
                样本表.append(("畸形帧 %s：回结构化应答且不含假成功" % 文本, "result" not in 输出流.getvalue()))
        # ② v1_edit：缺 `开工ID`（闸前即拒）· 开工不存在（认领闸所属的开工都没有）。
        退出码, 输出文本 = 工具表["v1_edit"][0]({}, 仓根)
        样本表.append(("v1_edit 缺 `开工ID`：退出码 %d（非 0）" % 退出码, 退出码 != 0))
        退出码, 输出文本 = 工具表["v1_edit"][0](
            {"开工ID": "v1-000000", "改动表": [{"路径": "AGENTS.md", "功能": 1, "旧内容": "x", "新内容": "y"}]}, 仓根)
        样本表.append(("v1_edit 开工不存在（路径必未认领）：退出码 %d（非 0）" % 退出码, 退出码 != 0))
        # 纯函数探针（不经派发，绝不动盘）：功能号非法 · 旧内容不唯一。
        错误 = 修改._读一条改动({"路径": "AGENTS.md", "功能": 99})[4]
        样本表.append(("v1_edit 功能号非法（99）：%s" % (错误 or "（没拒）"), bool(错误)))
        位置表 = 修改._定位旧内容("a\nb\na\n", "a")
        样本表.append(("v1_edit 旧内容不唯一：命中 %d 处（>1 即拒）" % len(位置表), len(位置表) > 1))
        # ③ v1_task：非法功能档。
        退出码, 输出文本 = 工具表["v1_task"][0]({"功能": 99}, 仓根)
        样本表.append(("v1_task 非法功能档 99：退出码 %d（非 0）" % 退出码, 退出码 != 0))
        # ④ 功能档冒烟（**只读**：只走查询路，一个字节都不改仓）。
        #    这一面原先没覆盖 —— 实测漏掉过「查询开工 里引用了已改名的局部变量 ⇒ 功能=0 当场崩」
        #    （2026-10-05 冒烟抓到；闸 0 不调 v1_task ⇒ 抓不到）。
        for 说明, 参数 in (("v1_task 功能=0 无参", {"功能": 0}),
                         ("v1_task 功能=0 关键词", {"功能": 0, "关键词": "开工"}),
                         ("v1_task 功能=0 带开工ID", None)):
            if 参数 is None:
                # 从上一份回执里取第一条开工号（不另读账本 ⇒ 不新增读路径）。
                号表 = [开工号 for 开工号 in 输出文本.split() if 开工号.startswith("v1-")]
                if not 号表:
                    print("  · v1_task 功能=0 带开工ID：回执里没有开工号 ⇒ 未判（不是通过）")
                    break
                参数 = {"功能": 0, "开工ID": 号表[0]}
            退出码, 输出文本 = 工具表["v1_task"][0](参数, 仓根)
            样本表.append(("%s：不崩（退出码 %d）" % (说明, 退出码),
                        退出码 == 0 and "内部错误" not in 输出文本 and "Traceback" not in 输出文本))
        失败 = []
        for 说明, 通过 in 样本表:
            print("  %s %s" % ("✓" if 通过 else "✗", 说明))
            if not 通过:
                失败.append(说明)
        if 失败:
            print("★拒绝样本没过 %d 条" % len(失败))
        return 0 if 名表 == 期望 and not 非ASCII and not 失败 else 1
    return 跑主循环(仓根, 工具表)


if __name__ == "__main__":
    sys.exit(入口函数())
