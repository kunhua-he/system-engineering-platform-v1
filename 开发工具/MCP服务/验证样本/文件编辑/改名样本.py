# -*- coding: utf-8 -*-
r"""改名样本 —— `v1_task` 批量改名的正反样本（临时迷你工作树 + 迷你规则库 + 临时账本，跑完即删）。

**为何单开一件**（判据 ⑲ · 单源文件 ≤400 行）：`自检样本.py` 逼近 400 行硬数 ⇒ 把「要搭临时
夹具的那一大块」搬到这里（一个关注点一件）；`自检样本.py` 仍调 `改名样本.批量改名样本` 并再导出，
原有样本一个不删（判据面只看 `--自检` 退出码，行为逐字不变）。

**仓一个字节都不改**：夹具 = 一棵迷你工作树 + 一本临时账本（账本连口与索引器两处走替身）。
"""
from pathlib import Path


def 批量改名样本(仓根, 工具表) -> list:
    """`v1_task` 批量改名的**正向 + 反向**两条样本 ⇒ 样本表（跑完把临时夹具删净）。

    正向：新名**已登记** ⇒ 退出码 0 · 源件里那个名**真的换掉了** · 回执说「改了 1/1 件」。
    反向：新名**没登记** ⇒ 闸 fail-closed（退出码 5）· 源件**一个字节没动**。
    """
    import shutil
    import sqlite3
    import tempfile

    from 代码地图 import 文件指纹
    from MCP服务.文件编辑 import 批量改名
    from MCP服务 import 开工账本

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
