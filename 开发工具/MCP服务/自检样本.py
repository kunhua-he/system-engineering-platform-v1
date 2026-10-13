# -*- coding: utf-8 -*-
"""MCP 工具面自检：正式隔离样本、协议及拒绝断言。"""
from pathlib import Path

from . import 自检池宽  # 隔离池宽口径与身份证的主人（件头记 517/313 实测）
# ★ 唯一有序声明：`(隔离组名, 该组**完整样本数**)` —— **提交**（`跑自检` 建池）与**收集**
#   （`自检主体` 照 `隔离收齐.收集位次`）都从它派生；三面（声明 / 提交 / 已收）按**组名**核对
#   （`隔离收齐.核收齐`），漏一组即红。`跑隔离样本` 逐组核 len == 此数；少一条即判失败，不静默。
隔离组声明 = (
    ("改名样本", 35), ("上下文样本", 79), ("跨树样本", 18), ("重叠样本", 4), ("库快照样本", 16),
    ("账本差集样本", 5), ("基线并入样本", 8), ("易用样本一", 17), ("易用样本二", 37),
    ("已记账恢复样本", 23), ("只读缓存样本", 24), ("记账隔离样本", 4), ("清理样本", 40),
    ("记条款样本", 2), ("恢复归属样本", 9),
)
# 例外表：与 616 侧核对时 `易用样本一` 按**真值 19**（616 该组 19 条）。单一声明 + 一张例外表 ——
# 不再「先写一份原型、再由下一行整体覆盖」（那是合并残留死代码，每合一次多一行）。
隔离样本例外 = {"易用样本一": 19}
隔离样本组 = {**dict(隔离组声明), **隔离样本例外}
隔离组声明 = tuple((组名, 隔离样本组[组名]) for 组名, _ in 隔离组声明)
隔离入口文本 = (
    "import json,sys; from pathlib import Path; "
    "sys.path.insert(0,str(Path.cwd()/'开发工具')); "
    "from MCP服务.自检样本 import 隔离样本入口; "
    "print(json.dumps(隔离样本入口(sys.argv[1],Path.cwd()),ensure_ascii=False))"
)
def 重样本表() -> dict:
    """动盘重样本组 → `f(仓根, 工具表)`（`已记账恢复样本` 的入口是单参形，在此包一层）。"""
    from .改名样本 import 批量改名样本
    from .上下文样本 import 上下文样本
    from .跨树样本 import 跨树样本
    from . import 合主干重叠样本, 清理样本, 记账隔离样本, 已记账恢复样本, 只读缓存样本
    from .库快照样本 import 库快照样本
    from .账本差集样本 import 账本差集样本
    from .基线并入样本 import 基线并入样本
    from .易用样本 import 样本列表, 易用样本
    from . import 记条款样本 as 记条款样本件
    from .恢复归属 import 样本列表 as 恢复归属样本

    def 取恢复样本(仓根, 工具表):
        return 已记账恢复样本.样本列表(仓根)

    def 取缓存样本(仓根, 工具表):
        return 只读缓存样本.样本列表(仓根)

    def 取记条款样本(仓根, 工具表):
        return 记条款样本件.记条款样本()

    return {"改名样本": 批量改名样本, "上下文样本": 上下文样本, "跨树样本": 跨树样本,
            "重叠样本": 合主干重叠样本.样本列表, "库快照样本": 库快照样本,
            "账本差集样本": 账本差集样本, "基线并入样本": 基线并入样本,
            "易用样本一": 样本列表, "易用样本二": 易用样本,
            "已记账恢复样本": 取恢复样本, "只读缓存样本": 取缓存样本,
            "记账隔离样本": 记账隔离样本.样本列表, "清理样本": 清理样本.样本列表,
            "记条款样本": 取记条款样本, "恢复归属样本": 恢复归属样本}


def 隔离样本入口(样本组名, 仓根):
    """每组在独立进程运行一次，沿用全部正式样本与有限取树快照。

    本进程进**临时记账域**（域内工具流水的落点是本进程私有的临时库，不串写生产账本）。
    """
    from .工具 import 工具表
    from .参数规范 import 开树快照, 关树快照
    from .工具流水 import 临时记账库
    旧快照 = 开树快照()
    try:
        with 临时记账库():
            取样 = 重样本表().get(样本组名)
            if 取样 is None:
                raise ValueError("未知隔离样本组：%s" % 样本组名)
            样本表 = 取样(仓根, 工具表)
            return {"组": 样本组名, "样本": [(说明, bool(通过)) for 说明, 通过 in 样本表]}
    finally:
        关树快照(旧快照)
def 跑隔离样本(样本组名, 仓根):
    """真实子进程有界收敛；失败、超时、缺组或畸形输出都保留为失败样本。"""
    import json, subprocess, sys
    from .合主干有界跑 import 干净环境
    from .门禁预算 import 硬顶秒
    try:
        回执 = subprocess.run([sys.executable, "-B", "-c", 隔离入口文本, 样本组名],
                            cwd=仓根, env=干净环境(), capture_output=True, text=True, timeout=硬顶秒())
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
    动盘的重样本（改名 / 上下文 / 跨树 / 账本差集 / 基线并入）各走独立子进程**真并行** ——
    串行把它们堆在一条 `--自检` 里会把判据 ㊽ 的墙钟逼近五秒硬顶（口径同 `合主干` 提速）。

    全程进**临时记账域**（`工具流水.临时记账库`）：自检的工具流水落进程私有的临时库，**不串写
    生产账本**（生产默认路径与行为逐字不变）；隔离样本子进程各进各的域（`ContextVar` 不过进程
    边界，线程池 worker 起手是空上下文 —— 当前 worker 只起子进程，故无生产写）。
    """
    from .参数规范 import 开树快照, 关树快照
    from .工具流水 import 临时记账库
    import concurrent.futures
    旧快照 = 开树快照()
    try:
        with 临时记账库():
            # ★ 池宽**自适应**（债务 517 / 313 · 2026-10-13 实测）：固定 `len(隔离样本组)`（15）
            #   在多路并发下必超 5 秒硬顶（2 路 6.07 s · 4 路 13.94 s ⇒ 判据 ㊽ 硬红），
            #   病根与 `常量_池宽.判据池宽()` 记的逐字相同（固定值两头不讨好）⇒ 走同一口径，
            #   按机器在跑的**自检进程数**分份额。口径与身份证住 `自检池宽.py`。
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=自检池宽.隔离池宽(len(隔离样本组))) as 隔离进程池:
                样本作业表 = {样本组名: 隔离进程池.submit(跑隔离样本, 样本组名, 仓根)
                          for 样本组名 in 隔离样本组}
                return 自检主体(仓根, 工具表, 样本作业表)
    finally:
        关树快照(旧快照)

def 自检主体(仓根, 工具表, 样本作业表) -> int:
    """自检实现主体（取树快照作用域由 `跑自检` 管）。"""
    import json, re

    from .参数规范 import 载入操作表
    from .协议 import 派发, 协议版本

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

    恢复样本位置 = len(样本表)

    # ── ③ 拒绝样本（新统一合同：未知操作 / 缺参 / 未知键 / 带参无操作 / 非法改动操作）──
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

    # ── ④b 跑命令**剔 Git 重定向键 + 配置注入键**（541 / 677 缺陷的机制身份证）──
    #   真起子进程：注入 GIT_DIR 与 GIT_CONFIG_PARAMETERS 后，子进程**既**读不到 GIT_DIR，
    #   **也**读不到注入的配置（子进程里的 git `config --get` 取不到注入键）。实测 v1-100675：
    #   夹具 commit 继承 GIT_CONFIG_PARAMETERS ⇒ 跑外层钩子 ⇒ `ROOT` 解析成临时仓 ⇒ 闸 0 红。
    import os; from unittest.mock import patch
    from .仓操作 import 跑命令
    注入表 = {"GIT_DIR": "/哨兵/不许出现在子进程",
            "GIT_CONFIG_PARAMETERS": "'core.hooksPath=/哨兵/外层钩子' 'v1probe.injectedkey=/哨兵/注入值'",
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": "/哨兵/外层钩子"}
    with patch.dict(os.environ, 注入表):
        退出码, 输出文本 = 跑命令(
            ["sh", "-c", "printf '%s|%s' \"${GIT_DIR:-EMPTY}\" "
                       "\"$(git config --get v1probe.injectedkey || printf EMPTY)\""], cwd=仓根)
    样本表.append(("`仓操作.跑命令` 剔 Git 重定向键与配置注入键：注入 GIT_DIR 与 GIT_CONFIG_PARAMETERS "
             "后子进程读到 %r（期望 EMPTY|EMPTY）" % 输出文本.strip(),
             退出码 == 0 and 输出文本.strip() == "EMPTY|EMPTY"))

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
    #   ★ 2026-10-08 实测：把这 12 组搬进隔离池（池内 22 组并发）**更慢**（2.4–2.9 s vs 2.3 s）——
    #     池里每个作业还会再 fork git / python，超订把总墙钟顶长 ⇒ 保持**父进程顺序跑**；
    #     只把它们的**定义**搬到 `工具面样本.py`（给本件腾 400 行空间）。
    from . import http传输样本
    from .符号样本 import 符号样本
    from .作业样本 import 作业样本
    from .冲突样本 import 冲突回执样本
    from . import 裸仓回执样本, 写盘样本, 数字操作样本, 信封样本
    from .名册僵尸样本 import 名册僵尸样本
    from .查询样本 import 查询样本
    from .开工记忆样本 import 开工记忆样本
    from .诊断样本 import 诊断样本
    from .工具面样本 import 终端样本, 自愈样本
    from . import 隔离收齐
    输出缓冲 = ([终端样本(仓根, 工具表)] +
                 [符号样本(仓根, 工具表)] +
                 [自愈样本(仓根, 工具表)] +
                 [冲突回执样本(仓根, 工具表)] +
                 [查询样本(仓根, 工具表)] +
                 [http传输样本.样本列表(仓根, 工具表)] +
                 [裸仓回执样本.样本列表(仓根, 工具表)] +
                 [开工记忆样本(仓根, 工具表)] +
                 [写盘样本.样本列表(仓根, 工具表)] +
                 [诊断样本(仓根, 工具表)] +
                 [名册僵尸样本(仓根, 工具表)] +
                 [隔离收齐.样本列表(仓根, 工具表)])
    # 收集**只照唯一有序声明走**（`隔离收齐.收集位次`）⇒ 不再手写拼接表达式：漏一组 / 换组名 /
    # 缺映射 / 重复收集 / 取结果失败 / 父进程样本批漏收 ⇒ 当场落一条**失败样本**（整体非零）。
    收集结果, 已收组表 = 隔离收齐.收集样本(样本作业表, 输出缓冲, 隔离收齐.收集位次, 恢复样本位置,
                                 lambda 作业: 作业.result())
    样本表 += 收集结果
    from unittest.mock import patch
    from . import 参数规范
    with patch.object(参数规范, "取树", return_value={}):
        样本表 += 作业样本(仓根, 工具表)
    收齐说明 = 隔离收齐.核收齐(隔离组声明, 样本作业表, 已收组表, 隔离收齐.收集位次, len(输出缓冲))
    if 收齐说明:
        样本表.append((收齐说明, False))
    样本表 += 自检_隔离边界(仓根) + 自检池宽.自检池宽身份证()
    样本表[恢复样本位置:恢复样本位置] = 样本作业表["已记账恢复样本"].result(); 样本表 += 自检_隔离边界(仓根) + 数字操作样本.样本列表(仓根, 工具表) + 信封样本.样本列表(仓根, 工具表)

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

    # ── 汇总（含数字操作面样本）──
    失败 = []
    for 说明, 通过 in 样本表:
        print("  %s %s" % ("✓" if 通过 else "✗", 说明))
        if not 通过:
            失败.append(说明)
    if 失败:
        print("★ 拒绝样本没过 %d 条" % len(失败))
    return 0 if not 失败 else 1

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
    子组读数 = {"组": "上下文样本", "样本": [["上下文%02d" % 序号, True] for 序号 in range(79)]}
    for 故障读数 in (
        {"组": "上下文样本", "样本": 子组读数["样本"][:-1]},
        {"组": "上下文样本", "样本": [["失败", False]] + 子组读数["样本"][1:]},
    ):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(故障读数), "")):
            结果表 = 跑隔离样本("上下文样本", 仓根)
        样本表.append(("隔离边界·上下文79条（原66及551与566各5及560增4 · 2026-10-13 台账改库减1）缺1或失败1拒绝", bool(结果表) and not all(通过 for _, 通过 in 结果表)))
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
    子组读数 = {"组": "库快照样本", "样本": [["快照%02d" % 序号, True] for 序号 in range(16)]}
    for 故障读数 in (子组读数, {"组": "库快照样本", "样本": 子组读数["样本"][:-1]},
                 {"组": "库快照样本", "样本": [["失败", False]] + 子组读数["样本"][1:]}):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(故障读数), "")) as 启动替身:
            结果表 = 跑隔离样本("库快照样本", 仓根)
        合规 = (结果表 == [tuple(明细条) for 明细条 in 子组读数["样本"]] if 故障读数 is 子组读数
              else bool(结果表) and not all(通过 for _, 通过 in 结果表))
        样本表.append(("隔离边界·库快照16条同序完整或缺1失败1拒且恰一次", 合规 and 启动替身.call_count == 1))
    for 样本组名 in ("易用样本一", "易用样本二", "已记账恢复样本"):
        子组读数 = {"组": 样本组名, "样本": [["易用%02d" % 序号, True]
                   for 序号 in range(隔离样本组[样本组名])]}
        for 故障读数 in (子组读数, dict(子组读数, 样本=子组读数["样本"][:-1]),
                     dict(子组读数, 样本=[["失败", False]] + 子组读数["样本"][1:])):
            with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, json.dumps(故障读数), "")) as 启动替身:
                结果表 = 跑隔离样本(样本组名, 仓根)
            合规 = (结果表 == [tuple(明细条) for 明细条 in 子组读数["样本"]]
                  if 故障读数 is 子组读数 else bool(结果表) and not all(通过 for _, 通过 in 结果表))
            样本表.append(("隔离边界·" + 样本组名 + "完整同序或缺1失败1拒且恰一次", 合规 and 启动替身.call_count == 1))
    return 样本表

# ★ 本件原有一个**模块级** `自愈样本`（626 已把定义搬到 `工具面样本.py`，`自检主体` 从那里
#   导入）—— 合并时那份旧副本没删干净 ⇒ **第二实现**（僵尸代码）。2026-10-08 删（行数硬顶
#   ⑲ 也正好撞上：本件加了记账域与回归组之后必须腾地方）。

