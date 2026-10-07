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
    """MCP 工具面自检 ⇒ 退出码（0 全过 · 1 有样本没过）。"""
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

    # ── ⑥ 工具面样本（动盘的那一类，临时夹具）+ 上下文正反样本 ──
    from .上下文样本 import 上下文样本
    样本表 += 批量改名样本(仓根, 工具表) + 终端样本(仓根, 工具表) + 上下文样本(仓根, 工具表)

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


def 批量改名样本(仓根, 工具表) -> list:
    """`v1_task` 批量改名的**正向 + 反向**两条样本 ⇒ 样本表（跑完把临时夹具删净）。

    正向：新名**已登记** ⇒ 退出码 0 · 源件里那个名**真的换掉了** · 回执说「改了 1/1 件」。
    反向：新名**没登记** ⇒ 闸 fail-closed（退出码 5）· 源件**一个字节没动**。
    """
    import shutil
    import sqlite3
    import tempfile

    from 代码地图 import 文件指纹
    from MCP服务 import 批量改名, 开工账本

    临时根 = Path(tempfile.mkdtemp(prefix="v1批量改名自检-"))
    try:
        输出表 = _跑夹具(临时根, 仓根, 工具表, 文件指纹, 批量改名, 开工账本)
        from .预检样本 import 扫一遍
        return 输出表 + 扫一遍(Path(仓根))
    finally:
        shutil.rmtree(临时根, ignore_errors=True)


def _跑夹具(临时根: Path, 仓根, 工具表, 文件指纹, 批量改名, 开工账本) -> list:
    """夹具本体：搭迷你工作树 + 迷你规则库 + 临时账本 ⇒ 跑正反两条样本。"""
    import sqlite3

    工作树 = 临时根 / "工作树"
    (工作树 / "临时区").mkdir(parents=True)
    文件条目 = 工作树 / "临时区" / "样例.py"
    内容值 = "旧样例名 = 1\nprint(旧样例名)\n"
    文件条目.write_text(内容值, encoding="utf-8")
    字段件 = 工作树 / "临时区" / "字段样例.js"
    字段内容 = "const 对象 = { 旧字段名: 1 };\nconsole.log(对象.旧字段名);\n"
    字段件.write_text(字段内容, encoding="utf-8")
    形状件 = 工作树 / "临时区" / "形状.rs"
    形状内容 = "pub struct 样形状 {\n    旧冻名: u32,\n}\n"
    形状件.write_text(形状内容, encoding="utf-8")
    用冻名件 = 工作树 / "临时区" / "用冻名.js"
    用冻名内容 = "const a = 对象.旧冻名;\nconst b = 对象.get();\n"
    用冻名件.write_text(用冻名内容, encoding="utf-8")
    撞名件 = 工作树 / "临时区" / "撞名样例.py"
    撞名内容 = "旧样例名 = 1\n新样例名 = 2\nprint(旧样例名, 新样例名)\n"
    撞名件.write_text(撞名内容, encoding="utf-8")
    (工作树 / "契约声明").mkdir(parents=True)
    (工作树 / "契约声明" / "冻结登记.json").write_text(
        '{"冻结项": [{"名称": "样形状", "落点": "临时区/形状.rs::样形状"}]}', encoding="utf-8")
    规则库路径 = 工作树 / "开发工具" / "信息核心" / "信息核心.db"
    规则库路径.parent.mkdir(parents=True)
    规则 = sqlite3.connect(str(规则库路径))
    规则.execute("create table 命名登记(名字 text primary key, 语义 text, 模式 text, 来源 text, 状态 text)")
    规则.execute("create table 命名例外(名字 text primary key, 说明 text)")
    规则.executemany("insert into 命名登记 values (?,?,?,?,?)",
                 [(标识符, 标识符, "对象+说明", "新定义", "合格")
                  for 标识符 in ("旧样例名", "新样例名", "旧字段名", "新字段名", "旧冻名", "新冻名")])
    规则.commit()
    规则.close()
    账本路径 = 临时根 / "账本.db"
    账本连接 = sqlite3.connect(str(账本路径))
    for 建表行 in 开工账本.建表语句:
        账本连接.execute(建表行)
    账本连接.execute("insert into 开工 (开工号, 工作内容, 分支名, 工作树, 状态, 开工时间) "
             "values (?,?,?,?,?,?)",
             ("v1-自检样本", "自检", "自检", str(工作树), 开工账本.状态_进行中, "2026-10-06"))
    账本连接.executemany("insert into 认领 (开工号, 路径, 指纹) values (?,?,?)",
              [("v1-自检样本", "临时区/样例.py", 文件指纹(str(文件条目))),
               ("v1-自检样本", "临时区/字段样例.js", 文件指纹(str(字段件))),
               ("v1-自检样本", "临时区/形状.rs", 文件指纹(str(形状件))),
               ("v1-自检样本", "临时区/用冻名.js", 文件指纹(str(用冻名件))),
               ("v1-自检样本", "临时区/撞名样例.py", 文件指纹(str(撞名件)))])
    账本连接.commit()
    账本连接.close()

    def 开账():
        """每次调用开**一条新连接**（`派发` 用完会 close ⇒ 不能给同一条）。"""
        连接 = sqlite3.connect(str(账本路径))
        连接.row_factory = sqlite3.Row
        return 连接

    真连, 真索引 = 开工账本.连账本, 批量改名.同步索引
    开工账本.连账本 = 开账
    批量改名.同步索引 = lambda _根: (0, "自检样本：索引器跳过")
    输出表 = []
    try:
        邻件原样 = 文件条目.read_text(encoding="utf-8")
        退出码, 回执 = 工具表["v1_task"][0](
            {"开工ID": "v1-自检样本", "操作": "批量改名",
             "参数": {"路径范围": ["临时区"], "改名对": [{"旧名": "旧样例名", "新名": "新样例名"}]}}, 仓根)
        撞名未动 = 撞名件.read_text(encoding="utf-8") == 撞名内容
        邻件也未动 = 文件条目.read_text(encoding="utf-8") == 邻件原样
        输出表.append(("v1_task 批量改名 反向（撞名预检）：退出码 %d（期望 3）· 撞名件%s动 · 邻件%s动 · 回执说「撞名预检」%s"
                % (退出码, "没" if 撞名未动 else "****", "也没" if 邻件也未动 else "**被",
                   "是" if "撞名预检" in 回执 else "否"),
                退出码 == 3 and 撞名未动 and 邻件也未动 and "撞名预检" in 回执))
        for 说明, 新名, 期望码 in (("正向（新名已登记）", "新样例名", 0),
                                ("反向（新名没登记）", "没登记的名", 5)):
            文件条目.write_text(内容值, encoding="utf-8")
            退出码, 回执 = 工具表["v1_task"][0](
                {"开工ID": "v1-自检样本", "操作": "批量改名",
                 "参数": {"路径范围": ["临时区"], "文件范围": ["临时区/样例.py"],
                        "改名对": [{"旧名": "旧样例名", "新名": 新名}]}}, 仓根)
            if 期望码 == 0:
                改成 = 文件条目.read_text(encoding="utf-8") == 内容值.replace("旧样例名", "新样例名")
                输出表.append(("v1_task 批量改名 %s：退出码 %d · 改名%s生效 · 回执说「改了 1/1 件」%s"
                        % (说明, 退出码, "" if 改成 else "**没**",
                           "是" if "改了 1/1 件" in 回执 else "否"),
                        退出码 == 期望码 and 改成 and "改了 1/1 件" in 回执
                        and "Traceback" not in 回执))
            else:
                没改 = 文件条目.read_text(encoding="utf-8") == 内容值
                输出表.append(("v1_task 批量改名 %s：退出码 %d（期望 %d，闸 fail-closed）· 件%s被动"
                        % (说明, 退出码, 期望码, "没" if 没改 else "****"),
                        退出码 == 期望码 and 没改))
        字段件.write_text(字段内容, encoding="utf-8")
        退出码, 回执 = 工具表["v1_task"][0](
            {"开工ID": "v1-自检样本", "操作": "批量改名",
             "参数": {"路径范围": ["临时区"], "改名对": [{"旧名": "旧字段名", "新名": "新字段名"}]}}, 仓根)
        改后 = 字段件.read_text(encoding="utf-8")
        键同步 = "{ 新字段名: 1 }" in 改后
        读同步 = "对象.新字段名" in 改后
        无残留 = "旧字段名" not in 改后
        输出表.append(("v1_task 批量改名 正向（含 `.名` 读取的字段）：退出码 %d · 键%s同步 · 读取%s同步 · 旧名%s残留"
                % (退出码, "" if 键同步 else "**没**", "" if 读同步 else "**没**",
                   "" if 无残留 else "**有**"),
                退出码 == 0 and 键同步 and 读同步 and 无残留 and "Traceback" not in 回执))
        形状件.write_text(形状内容, encoding="utf-8")
        用冻名件.write_text(用冻名内容, encoding="utf-8")
        退出码, 回执 = 工具表["v1_task"][0](
            {"开工ID": "v1-自检样本", "操作": "批量改名",
             "参数": {"路径范围": ["临时区"], "改名对": [{"旧名": "旧冻名", "新名": "新冻名"}]}}, 仓根)
        冻改后 = 用冻名件.read_text(encoding="utf-8")
        跨件同步 = "对象.新冻名" in 冻改后
        标准库未动 = "对象.get()" in 冻改后
        冻无残留 = "旧冻名" not in 冻改后
        输出表.append(("v1_task 批量改名 正向（冻结字段的跨件 `.名`）：退出码 %d · 跨件读取%s同步 · 标准库方法%s · 旧名%s残留"
                % (退出码, "" if 跨件同步 else "**没**",
                   "未误改" if 标准库未动 else "**被误改**",
                   "" if 冻无残留 else "**有**"),
                退出码 == 0 and 跨件同步 and 标准库未动 and 冻无残留 and "Traceback" not in 回执))
    finally:
        开工账本.连账本, 批量改名.同步索引 = 真连, 真索引
    return 输出表


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
