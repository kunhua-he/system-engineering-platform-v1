# -*- coding: utf-8 -*-
r"""自检样本 —— MCP 工具面自检：协议三帧 · 工具表形状 · 拒绝样本 · 只读发现 · 冒烟。

`MCP服务.py --自检` 调本件的 `跑自检`（判据 ㊽ 跑它，退出码非 0 ⇒ 闸 0 当场红）。

**为什么要有强谓词**（判据 ㊽ 只看退出码 ⇒ 自检弱 = 闸 0 弱）：协议三帧必须**断言**形状并计入
样本表；畸形帧必须**判失败**（不是 PASS）；冒烟取不到开工号**不许静默跳过**，要记「未判非通过」；
逐工具断言 `inputSchema` 形状（三字段同形 / `additionalProperties=false` / 无 `required`）。

**要动盘的那一类样本**（批量改名 · 终端）走临时夹具：一棵迷你工作树 + 一本临时账本，
跑完即删 —— **仓一个字节都不改**（账本连口与索引器两处走替身）。
"""
from pathlib import Path


def _读信封(输出文本: str):
    """底层 / 网关回执是 JSON 信封 ⇒ 解析；否则 `None`。"""
    import json
    try:
        return json.loads(输出文本)
    except (TypeError, ValueError):
        return None


def _有种类(输出文本: str, 种类: str) -> bool:
    """信封 `错误.种类` 是否等于 `种类`（参数面拒绝的分类断言）。"""
    读数 = _读信封(输出文本)
    return bool(读数) and (读数.get("错误") or {}).get("种类") == 种类


def 跑自检(仓根, 工具表) -> int:
    """MCP 工具面自检 ⇒ 退出码（0 全过 · 1 有样本没过）。

    全程开**取树快照**（同一稳定仓连发多条信封 ⇒ 复用现读读数），作用域结束即还原。
    动盘的重样本（改名 / 上下文 / 跨树 / 账本差集 / 基线并入）各走独立子进程**真并行** ——
    串行把它们堆在一条 `--自检` 里会把判据 ㊽ 的墙钟逼近五秒硬顶（口径同 `合主干` 提速）。
    """
    from .参数规范 import 开树快照, 关树快照
    from .隔离样本 import 并行样本结果
    旧快照 = 开树快照()
    try:
        隔离结果 = 并行样本结果(仓根)
        return 自检主体(仓根, 工具表, 隔离结果)
    finally:
        关树快照(旧快照)


def 自检主体(仓根, 工具表, 隔离结果) -> int:
    """自检实现主体（取树快照作用域由 `跑自检` 管；`隔离结果` = 并行重样本的成品表）。"""
    import io
    import json
    import re

    from .参数规范 import 载入操作表
    from .协议 import 派发, 跑主循环, 协议版本

    样本表 = []
    # ── ① 协议三帧（断言形状，计入样本表）──
    读数, 错误 = 派发("initialize", {"protocolVersion": "试"}, 仓根, 工具表)
    样本表.append(("initialize 回 protocolVersion=%s 与 serverInfo / instructions"
              % ((读数 or {}).get("protocolVersion")),
             错误 is None and (读数 or {}).get("protocolVersion") == 协议版本
             and isinstance((读数 or {}).get("serverInfo"), dict)
             and isinstance((读数 or {}).get("instructions"), str)))
    读数, 错误 = 派发("tools/list", {}, 仓根, 工具表)
    工具项表 = (读数 or {}).get("tools") or []
    样本表.append(("tools/list 回 tools 列表（%d 项）" % len(工具项表),
             错误 is None and isinstance((读数 or {}).get("tools"), list) and bool(工具项表)))
    读数, 错误 = 派发("没有这个方法", {}, 仓根, 工具表)
    样本表.append(("未知方法 ⇒ -32601", 错误 is not None and 错误.get("code") == -32601))

    # ── ② 工具名（六合同名都在，新工具可自声明追加）+ ASCII + inputSchema 形状 ──
    名表 = sorted(工具表)
    期望名表 = sorted(["v1_task", "v1_symbol", "v1_edit", "v1_gate", "v1_context", "v1_shell"])
    样本表.append(("六合同工具名都在（新工具可自声明追加）：%s" % 名表, set(期望名表) <= set(名表)))
    非ASCII = [名称 for 名称 in 名表 if not 名称.isascii()]
    样本表.append(("工具名全 ASCII", not 非ASCII))
    期望字段 = {"开工ID", "操作", "参数"}
    for 名称 in 名表:
        模式 = 工具表[名称][3]
        属性表 = 模式.get("properties") or {}
        样本表.append(("%s inputSchema 三字段同形 + additionalProperties=false + 无 required" % 名称,
                模式.get("additionalProperties") is False and set(属性表) == 期望字段
                and "required" not in 模式))

    # ── ③ 畸形帧（必须判失败：不抛异常、不回假成功）──
    for 源文本 in ("123", "null", "[1,2]", '"x"',
               '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":"x"}',
               '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"v1_symbol","arguments":"x"}}'):
        输入流, 输出流, 抛了 = io.StringIO(源文本 + "\n"), io.StringIO(), False
        try:
            跑主循环(仓根, 工具表, 输入流=输入流, 输出=输出流)
        except Exception:
            抛了 = True
        应答 = None
        try:
            应答 = json.loads(输出流.getvalue().splitlines()[0])
        except (ValueError, IndexError):
            应答 = None
        合规 = (not 抛了) and isinstance(应答, dict) and (
            "error" in 应答 or bool((应答.get("result") or {}).get("isError")))
        样本表.append(("畸形帧 %s：不抛异常且回结构化拒绝（无假成功）" % 源文本, 合规))

    # ── ④ 拒绝样本（新统一合同：未知操作 / 缺参 / 未知键 / 带参无操作 / 非法改动操作）──
    退出码, 输出文本 = 工具表["v1_edit"][0](
        {"操作": "改", "参数": {"改动表": [{"路径": "AGENTS.md", "操作": "修改", "旧内容": "旧", "新内容": "新"}]}}, 仓根)
    样本表.append(("v1_edit 改：缺 `开工ID` ⇒ 退出码 %d（期望 2 · 缺参）" % 退出码,
             退出码 == 2 and _有种类(输出文本, "缺参")))
    退出码, 输出文本 = 工具表["v1_edit"][0]({"开工ID": "v1-000000", "操作": "瞎操作"}, 仓根)
    样本表.append(("v1_edit 未知操作 ⇒ 退出码 %d（期望 2）" % 退出码,
             退出码 == 2 and _有种类(输出文本, "未知操作")))
    退出码, 输出文本 = 工具表["v1_shell"][0](
        {"操作": "执行", "参数": {"命令": "echo x", "乱键": 1}}, 仓根)
    样本表.append(("v1_shell 未知参数键 ⇒ 退出码 %d（期望 2）· 不执行" % 退出码,
             退出码 == 2 and _有种类(输出文本, "参数错误")))
    退出码, 输出文本 = 工具表["v1_shell"][0]({"参数": {"命令": "echo 不该执行"}}, 仓根)
    样本表.append(("v1_shell 带参数而无操作 ⇒ 退出码 %d（期望 2）· 未执行" % 退出码,
             退出码 == 2 and "不该执行" not in 输出文本 and _有种类(输出文本, "参数错误")))
    退出码, 输出文本 = 工具表["v1_edit"][0](
        {"开工ID": "v1-000000", "操作": "改",
         "参数": {"改动表": [{"路径": "AGENTS.md", "操作": "瞎写", "旧内容": "x", "新内容": "y"}]}}, 仓根)
    样本表.append(("v1_edit 改动操作非法 ⇒ 退出码 %d（非 0）" % 退出码, 退出码 != 0))
    退出码, 输出文本 = 工具表["v1_task"][0]({"操作": "瞎操作"}, 仓根)
    样本表.append(("v1_task 未知操作 ⇒ 退出码 %d（期望 2）" % 退出码,
             退出码 == 2 and _有种类(输出文本, "未知操作")))

    # ── ⑤ 只读发现调用：每工具 `{}` 回操作目录（有操作表者目录非空且最短例齐）──
    规范表 = 载入操作表()
    for 名称 in 名表:
        退出码, 输出文本 = 工具表[名称][0]({}, 仓根)
        读数 = _读信封(输出文本)
        目录 = ((读数 or {}).get("结果") or {}).get("操作目录") or {}
        最短例齐 = all("最短例" in 操作条 for 操作条 in 目录.values()) if 目录 else True
        样本表.append(("%s `{}` 发现调用 ⇒ 操作目录 %d 个（最短例齐 %s）"
                 % (名称, len(目录), "是" if 最短例齐 else "否"),
                 退出码 == 0 and 读数 is not None and 最短例齐
                 and (bool(目录) if 名称 in 规范表 else True)))

    # ── ⑥ 工具面样本（动盘的那一类）+ 上下文正反样本（重样本走并行隔离结果）──
    from . import http传输样本
    from .作业样本 import 作业样本
    from .冲突样本 import 冲突回执样本
    from . import 裸仓回执样本
    样本表 += (隔离结果["改名样本"] + 终端样本(仓根, 工具表) + 隔离结果["上下文样本"]
            + 自愈样本(仓根, 工具表) + 冲突回执样本(仓根, 工具表)
            + http传输样本.样本列表(仓根, 工具表) + 裸仓回执样本.样本列表(仓根, 工具表)
            + 隔离结果["跨树样本"] + 隔离结果["账本差集样本"] + 隔离结果["基线并入样本"])
    from unittest.mock import patch
    from . import 参数规范
    with patch.object(参数规范, "取树", return_value={}):
        样本表 += 作业样本(仓根, 工具表)

    # ── ⑦ 功能档冒烟（只读：只走查询路，一个字节都不改仓）──
    退出码, 输出文本 = 工具表["v1_task"][0]({"操作": "查询"}, 仓根)
    样本表.append(("v1_task 查询：不崩（退出码 %d）" % 退出码,
             退出码 == 0 and "Traceback" not in 输出文本))
    号表 = re.findall(r"v1-\d{6}", 输出文本)
    if not 号表:
        样本表.append(("v1_task 查询带 `开工ID`：回执里没有开工号 ⇒ **未判（不是通过）**", False))
    else:
        退出码, 输出文本 = 工具表["v1_task"][0]({"开工ID": 号表[0], "操作": "查询"}, 仓根)
        样本表.append(("v1_task 查询带 `开工ID`（%s）：不崩（退出码 %d）" % (号表[0], 退出码),
                 退出码 == 0 and "Traceback" not in 输出文本))

    # ── 汇总 ──
    失败 = []
    for 说明, 通过 in 样本表:
        print("  %s %s" % ("✓" if 通过 else "✗", 说明))
        if not 通过:
            失败.append(说明)
    if 失败:
        print("★ 拒绝样本没过 %d 条" % len(失败))
    return 0 if not 失败 else 1


def 终端样本(仓根, 工具表) -> list:
    """`v1_shell` 的正向 + 反向样本 ⇒ 样本表（只跑系统自带命令，不落仓、不碰真索引）。

    正向：`echo` 安全命令 ⇒ 退出码 0 · 回显固定词 · 回执带「工作目录」行。
    反向：命令非零 ⇒ 退出码 1 且回执带原退出码；未知键 / 非法开工 ⇒ 退出码 2、**不执行**。
    """
    出口 = 工具表["v1_shell"][0]
    样本表 = []
    退出码, 回执 = 出口({"操作": "执行", "参数": {"命令": "echo v1_shell_固定词"}}, 仓根)
    样本表.append(("v1_shell 正向（echo）：退出码 %d · 回显固定词 %s · 回执带工作目录 %s"
              % (退出码, "是" if "v1_shell_固定词" in 回执 else "否",
                 "是" if "工作目录：" in 回执 else "否"),
            退出码 == 0 and "v1_shell_固定词" in 回执 and "工作目录：" in 回执
            and "Traceback" not in 回执))
    退出码, 回执 = 出口({"操作": "执行", "参数": {"命令": "exit 7"}}, 仓根)
    样本表.append(("v1_shell 反向（命令非零 exit 7）：退出码 %d（期望 1）· 回执带原退出码 7 %s"
              % (退出码, "是" if "退出码：7" in 回执 else "否"),
            退出码 == 1 and "退出码：7" in 回执))
    退出码, 回执 = 出口({"操作": "执行", "参数": {"命令": "echo x", "乱键": 1}}, 仓根)
    样本表.append(("v1_shell 反向（未知参数键）：退出码 %d（期望 2）· 说「未知参数键」%s"
              % (退出码, "是" if "未知参数键" in 回执 else "否"),
            退出码 == 2 and "未知参数键" in 回执))
    退出码, 回执 = 出口({"开工ID": "v1-999999", "操作": "执行", "参数": {"命令": "echo x"}}, 仓根)
    样本表.append(("v1_shell 反向（非法开工）：退出码 %d（期望 2）· 说「工作树不在」%s"
              % (退出码, "是" if "工作树不在" in 回执 else "否"),
            退出码 == 2 and "工作树不在" in 回执))
    return 样本表


def 自愈样本(仓根, 工具表) -> list:
    """自愈预检的正反样本 ⇒ 样本表（真入口 + 临时坏件 + 替身决策；不动仓、不 exec）。

    正向：真入口 `--启动预检` ⇒ 可启动（真入口 / 真工作目录 / 真 import 全图）。
    反向：临时件带冲突标记 ⇒ 预检判「不可启动」，说明带 SyntaxError。
    决策：坏指纹只预检一次（替身计数 = 1）· 同指纹再判不重复预检 · 指纹变 + 预检过 ⇒ 放行。
    """
    import shutil
    import tempfile

    from . import 自愈预检

    样本表 = []
    入口路径 = Path(仓根) / "开发工具" / "MCP服务.py"
    入口可启, 预检说明 = 自愈预检.预检入口(入口路径, Path(仓根))
    样本表.append(("自愈预检：真入口 --启动预检 ⇒ 可启动=%s（%s）"
              % (入口可启, 预检说明 or "无说明"), 入口可启))

    临时根 = Path(tempfile.mkdtemp(prefix="v1自愈预检-"))
    try:
        坏件 = 临时根 / "MCP服务.py"
        坏件.write_text("<<<<<<< HEAD\nimport sys\n>>>>>>> 支线\n", encoding="utf-8")
        能启动, 冲突说明 = 自愈预检.预检入口(坏件, 临时根)
        样本表.append(("自愈预检：冲突标记件 ⇒ 不可启动（能启动=%s）· 说明带 SyntaxError=%s"
                 % (能启动, "是" if "SyntaxError" in 冲突说明 else "否"),
                 (not 能启动) and "SyntaxError" in 冲突说明))
    finally:
        shutil.rmtree(临时根, ignore_errors=True)

    调用计数 = {"次": 0}

    def 假预检():
        调用计数["次"] += 1
        return False, "替身：预检不过"

    原判定 = 自愈预检.判定重启
    自愈预检._已拒指纹, 自愈预检._拒因 = None, ""
    首判放行, _, 首记坏版 = 原判定("指纹旧版", 预检替身=假预检)
    再判放行, _, 再记坏版 = 原判定("指纹旧版", 预检替身=假预检)
    提示文本 = 自愈预检.拒绝提示行()
    样本表.append(("自愈决策：坏指纹不放行（%s/%s）· 只预检 %d 次（期望 1）· 首记坏版=%s · "
              "再记坏版=%s · 提示带「预检不通过」=%s"
              % (首判放行, 再判放行, 调用计数["次"], 首记坏版, 再记坏版,
                 "是" if "预检不通过" in 提示文本 else "否"),
             (not 首判放行) and (not 再判放行) and 调用计数["次"] == 1
             and 首记坏版 and (not 再记坏版) and "预检不通过" in 提示文本))
    变后放行, _, _ = 原判定("指纹新版", 预检替身=lambda: (True, ""))
    样本表.append(("自愈决策：指纹变 + 预检过 ⇒ 放行=%s" % 变后放行, 变后放行))
    自愈预检._已拒指纹, 自愈预检._拒因 = None, ""
    return 样本表

