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

隔离样本组 = {"改名样本": 34, "上下文样本": 76, "跨树样本": 18, "重叠样本": 4}
隔离入口文本 = (
    "import json,sys; from pathlib import Path; "
    "sys.path.insert(0,str(Path.cwd()/'开发工具')); "
    "from MCP服务.自检样本 import 隔离样本入口; "
    "print(json.dumps(隔离样本入口(sys.argv[1],Path.cwd()),ensure_ascii=False))"
)


def 隔离样本入口(样本组名, 仓根):
    """每组在独立进程运行一次，沿用全部正式样本与有限取树快照。"""
    from .工具 import 工具表
    from .参数规范 import 开树快照, 关树快照
    from .改名样本 import 批量改名样本
    from .上下文样本 import 上下文样本
    from .跨树样本 import 跨树样本
    from . import 合主干重叠样本
    旧快照 = 开树快照()
    try:
        样本表 = {"改名样本": 批量改名样本, "上下文样本": 上下文样本,
                 "跨树样本": 跨树样本, "重叠样本": 合主干重叠样本.样本列表}[样本组名](仓根, 工具表)
        return {"组": 样本组名, "样本": [(说明, bool(通过)) for 说明, 通过 in 样本表]}
    finally:
        关树快照(旧快照)


def 跑隔离样本(样本组名, 仓根):
    """真实子进程有界收敛；失败、超时、缺组或畸形输出都保留为失败样本。"""
    import json
    import subprocess
    import sys
    from .合主干有界跑 import 干净环境
    try:
        回执 = subprocess.run([sys.executable, "-B", "-c", 隔离入口文本, 样本组名],
                            cwd=仓根, env=干净环境(), capture_output=True, text=True, timeout=5)
        if 回执.returncode != 0:
            raise ValueError("退出码 %d：%s" % (回执.returncode, 回执.stderr[-500:]))
        子组读数 = json.loads(回执.stdout)
        样本表 = 子组读数["样本"]
        if (子组读数["组"] != 样本组名 or not isinstance(样本表, list)
                or len(样本表) != 隔离样本组[样本组名]
                or not all(isinstance(明细条, list) and len(明细条) == 2
                           and isinstance(明细条[0], str) and type(明细条[1]) is bool
                           for 明细条 in 样本表)):
            raise ValueError("样本组或完整样本数/形状不齐")
        return [tuple(明细条) for 明细条 in 样本表]
    except Exception as 错误:
        return [("隔离样本 %s 未完整完成：%r" % (样本组名, 错误), False)]


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
    """
    from .参数规范 import 开树快照, 关树快照
    import concurrent.futures
    旧快照 = 开树快照()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as 隔离进程池:
            样本作业表 = {样本组名: 隔离进程池.submit(跑隔离样本, 样本组名, 仓根)
                      for 样本组名 in 隔离样本组}
            return 自检主体(仓根, 工具表, 样本作业表)
    finally:
        关树快照(旧快照)


def 自检主体(仓根, 工具表, 样本作业表) -> int:
    """自检实现主体（取树快照作用域由 `跑自检` 管）。"""
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

    # ── ④b 跑命令**剔 Git 重定向键**（541 缺陷的机制身份证）：注入 GIT_DIR ⇒ 子进程看不到 ──
    import os
    from unittest.mock import patch
    from .仓操作 import 跑命令
    with patch.dict(os.environ, {"GIT_DIR": "/哨兵/不许出现在子进程"}):
        退出码, 输出文本 = 跑命令(["sh", "-c", "printf '%s' \"${GIT_DIR:-EMPTY}\""], cwd=仓根)
    样本表.append(("`仓操作.跑命令` 剔 Git 重定向键：注入 GIT_DIR 后子进程读到 %r（期望 EMPTY）"
             % 输出文本.strip(), 退出码 == 0 and 输出文本.strip() == "EMPTY"))

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

    # ── ⑤b 长样本入口的**发现/接口**（只验入口与场景表在；重场景由提交长路 `--长样本` 跑）──
    from .认领样本 import 场景表
    样本表.append(("长样本入口 `MCP服务.py --长样本` 声明 %d 个事务场景（≥7 · 名非空）" % len(场景表),
             len(场景表) >= 7 and all(场景名.strip() for 场景名 in 场景表)))

    # ── ⑥ 工具面样本（动盘的那一类，临时夹具）+ 上下文正反样本 ──
    from . import http传输样本
    from .库快照样本 import 库快照样本
    from .符号样本 import 符号样本
    from .作业样本 import 作业样本
    from .冲突样本 import 冲突回执样本
    from . import 裸仓回执样本, 写盘样本
    from .名册僵尸样本 import 名册僵尸样本
    from .查询样本 import 查询样本
    from .开工记忆样本 import 开工记忆样本
    from .诊断样本 import 诊断样本
    from .易用样本 import 样本列表 as 易用样本表
    from . import 合主干重叠样本
    样本表 += (样本作业表["改名样本"].result() + 终端样本(仓根, 工具表)
            + 样本作业表["上下文样本"].result() + 符号样本(仓根, 工具表)
            + 自愈样本(仓根, 工具表) + 冲突回执样本(仓根, 工具表) + 查询样本(仓根, 工具表)
            + 库快照样本(仓根, 工具表)
            + http传输样本.样本列表(仓根, 工具表) + 裸仓回执样本.样本列表(仓根, 工具表)
            + 样本作业表["跨树样本"].result() + 开工记忆样本(仓根, 工具表)
            + 写盘样本.样本列表(仓根, 工具表) + 诊断样本(仓根, 工具表) + 易用样本表(仓根, 工具表) + 样本作业表["重叠样本"].result() + 名册僵尸样本(仓根, 工具表))
    from unittest.mock import patch
    from . import 参数规范
    with patch.object(参数规范, "取树", return_value={}):
        样本表 += 作业样本(仓根, 工具表)

    样本表 += 自检_隔离边界(仓根)

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


def 自检_隔离边界(仓根):
    """采样完成后故障注入，完整组、失败组及异常缺失均不能假绿。"""
    import json
    import subprocess
    from unittest.mock import patch
    样本表 = []
    子组读数 = {"组": "跨树样本", "样本": [["样本%02d" % 序号, True] for 序号 in range(18)]}
    for 说明, 故障读数, 期望码 in (
        ("完整组原顺序内容", 子组读数, 0),
        ("子组失败保留", {"组": "跨树样本", "样本": [["失败", False]] + 子组读数["样本"][1:]}, 1),
        ("空结果拒绝", {"组": "跨树样本", "样本": []}, 1),
        ("组数不齐拒绝", {"组": "跨树样本", "样本": 子组读数["样本"][:-1]}, 1),
        ("错组拒绝", {"组": "上下文样本", "样本": 子组读数["样本"]}, 1),
        ("字段缺失拒绝", {}, 1),
    ):
        返回替身 = subprocess.CompletedProcess([], 0, json.dumps(故障读数), "")
        with patch.object(subprocess, "run", return_value=返回替身) as 启动替身:
            结果表 = 跑隔离样本("跨树样本", 仓根)
        合规 = (结果表 == [tuple(明细条) for 明细条 in 子组读数["样本"]]
              if 期望码 == 0 else bool(结果表) and not all(通过 for _, 通过 in 结果表))
        样本表.append(("隔离边界·" + 说明, 合规 and 启动替身.call_count == 1))
    for 说明, 返回替身 in (
        ("非零退出拒绝", subprocess.CompletedProcess([], 3, "", "真实异常")),
        ("非JSON拒绝", subprocess.CompletedProcess([], 0, "bad", "")),
        ("超时拒绝", subprocess.TimeoutExpired("样本", 5)),
        ("启动异常拒绝", OSError("样本起不来")),
    ):
        with patch.object(subprocess, "run", **({"side_effect": 返回替身} if isinstance(返回替身, Exception)
                                               else {"return_value": 返回替身})):
            结果表 = 跑隔离样本("跨树样本", 仓根)
        样本表.append(("隔离边界·" + 说明, bool(结果表) and not all(通过 for _, 通过 in 结果表)))
    子组读数 = {"组": "上下文样本", "样本": [["上下文%02d" % 序号, True] for 序号 in range(76)]}
    for 故障读数 in (
        {"组": "上下文样本", "样本": 子组读数["样本"][:-1]},
        {"组": "上下文样本", "样本": [["失败", False]] + 子组读数["样本"][1:]},
    ):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(故障读数), "")):
            结果表 = 跑隔离样本("上下文样本", 仓根)
        样本表.append(("隔离边界·上下文76条（原66及551与566各5）缺1或失败1拒绝", bool(结果表) and not all(通过 for _, 通过 in 结果表)))
    import os
    from .仓操作 import 跑命令
    from .合主干有界跑 import 继承定位变量
    with patch.dict(os.environ, {键名: "外仓样本" for 键名 in 继承定位变量}), patch.object(
            subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as 启动替身:
        跑命令(["git", "status"], cwd=仓根)
        合规 = not any(键名 in 启动替身.call_args.kwargs["env"] for 键名 in 继承定位变量)
        跑命令(["git", "status"], cwd=仓根, 子进程环境={"GIT_DIR": "显式目标"})
        合规 = 合规 and 启动替身.call_args.kwargs["env"]["GIT_DIR"] == "显式目标"
    样本表[-1] = (样本表[-1][0] + "·Git继承定位剔除且显式覆盖保留", 样本表[-1][1] and 合规)
    子组读数 = {"组": "重叠样本", "样本": [["重叠%02d" % 序号, True] for 序号 in range(4)]}
    for 故障读数 in (子组读数, {"组": "重叠样本", "样本": 子组读数["样本"][:-1]},
                 {"组": "重叠样本", "样本": [["失败", False]] + 子组读数["样本"][1:]}):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(故障读数), "")) as 启动替身:
            结果表 = 跑隔离样本("重叠样本", 仓根)
        合规 = (结果表 == [tuple(明细条) for 明细条 in 子组读数["样本"]] if 故障读数 is 子组读数
              else bool(结果表) and not all(通过 for _, 通过 in 结果表))
        样本表.append(("隔离边界·重叠4条同序完整或缺1失败1拒且恰一次", 合规 and 启动替身.call_count == 1))
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

