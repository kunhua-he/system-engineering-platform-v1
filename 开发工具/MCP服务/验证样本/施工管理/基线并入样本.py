# -*- coding: utf-8 -*-
r"""基线并入样本 —— `v1_task 登记` 的可选 `基线` 的正反样本（临时仓，跑完即删）。

**为何要它**：登记能把一条未合腿并进新工作树，是「省手工 merge + 二进制冲突处置」的那一步 ——
必须可复跑地证明：

  · 指定可合基线 ⇒ 新工作树**含基线成果**（干净并入）；
  · 基线不存在 ⇒ **清晰拒**（退出码 2 · 消息含「不存在」）；
  · 源码件冲突 ⇒ **清晰拒** 且 `merge --abort`（不留半合并现场）；
  · `登记` 参数面声明了 `基线`；`.db` 归**可重生二进制**（冲突时走取本支线侧那一路）。

★ 全程自建临时仓，跑完即删 ⇒ **真仓一个字节都不改**。
★ 夹具刻意压到最少 git 子进程（自检在五秒硬顶内）。
"""
from pathlib import Path


def _建样本仓(样本根: Path) -> Path:
    """建最小仓：主干（文.txt / 库.db）＋ 腿/v1-900001（改 文.txt）＋ 腿/v1-900002（加 新.txt）。

    主干在腿 1 分出去之后**又改了一次 文.txt** ⇒ 并腿 1 时 文.txt 两边都动过 = 源码件冲突；
    腿 2 从主干分出去、只加新件 ⇒ 干净并入。
    """
    import subprocess

    from ...集成管理.合主干有界跑 import 干净环境
    环境表 = 干净环境()
    仓根 = 样本根 / "样本仓"
    仓根.mkdir(parents=True)
    身份 = ["-c", "user.name=样本", "-c", "user.email=样本@例"]

    def 送命令(参数表: list):
        return subprocess.run(["git"] + 参数表, cwd=str(仓根), capture_output=True, text=True, env=环境表)

    (仓根 / "文.txt").write_text("主干\n", encoding="utf-8")
    (仓根 / "库.db").write_text("主干侧\n", encoding="utf-8")
    送命令(["init", "-q", "-b", "主干"])
    送命令(["add", "."])
    送命令(身份 + ["commit", "-q", "-m", "主干"])
    送命令(["checkout", "-q", "-b", "腿/v1-900001"])
    (仓根 / "文.txt").write_text("对侧改\n", encoding="utf-8")
    送命令(身份 + ["commit", "-q", "-a", "-m", "腿1"])
    送命令(["checkout", "-q", "主干"])
    (仓根 / "文.txt").write_text("本支线改\n", encoding="utf-8")
    送命令(身份 + ["commit", "-q", "-a", "-m", "主干再改"])
    送命令(["checkout", "-q", "-b", "腿/v1-900002"])
    (仓根 / "新.txt").write_text("新件\n", encoding="utf-8")
    送命令(["add", "."])
    送命令(身份 + ["commit", "-q", "-m", "腿2"])
    送命令(["checkout", "-q", "主干"])
    return 仓根


假信息核心源码 = (
    "import sqlite3, sys\n"
    "from pathlib import Path\n"
    "参表 = sys.argv[1:]\n"
    "子命令 = 参表[0] if 参表 else ''\n"
    "键值 = {}\n"
    "键 = None\n"
    "for 项 in 参表[1:]:\n"
    "    if 项.startswith('--'):\n"
    "        键 = 项[2:]\n"
    "        键值[键] = ''\n"
    "    elif 键:\n"
    "        键值[键] = 项\n"
    "连接 = sqlite3.connect(str(Path('开发工具/信息核心/信息核心.db')))\n"
    "if 子命令 == '登记':\n"
    "    连接.execute('insert or replace into 命名登记 (名字, 语义, 模式, 来源, 状态) values (?,?,?,?,?)',\n"
    "               (键值.get('名字',''), 键值.get('语义',''), 键值.get('模式',''), 键值.get('来源',''), 键值.get('状态','合格')))\n"
    "elif 子命令 == '记规则':\n"
    "    连接.execute('insert or replace into 规则 (编号, 类, 名, 内容, 依据) values (?,?,?,?,?)',\n"
    "               (int(键值.get('编号') or 0), 键值.get('类',''), 键值.get('名',''), 键值.get('内容',''), 键值.get('依据','')))\n"
    "elif 子命令 == '记条款':\n"
    "    pass\n"
    "elif 子命令 == '记未完成':\n"
    "    if '删' in 键值:\n"
    "        连接.execute('delete from 未完成 where 号 = ?', (int(键值.get('号') or 0),))\n"
    "    else:\n"
    "        连接.execute('insert or replace into 未完成(号, 缺什么, 落点, 验证命令) values(?,?,?,?)',\n"
    "                   (int(键值.get('号') or 0), 键值.get('缺什么',''), 键值.get('落点') or None,\n"
    "                    键值.get('验证命令') or None))\n"
    "else:\n"
    "    raise SystemExit(3)\n"
    "连接.commit()\n"
    "连接.close()\n"
    "print('ok')\n"
)


def _建库样本仓(样本根, 场景: str):
    """建「规则库冲突」样本仓 ⇒ (仓根, 工作树)。

    主干：规则库（规则#1 + 命名登记） + 假 信息核心.py；分腿两条都改规则库 ⇒ 二进制冲突。
    `加行`：腿加 规则#2 + 命名登记腿名，主干加 命名登记主干名；
    `同键异值`：两侧把 规则#1 内容改成不同值 ⇒ 判冲突。
    """
    import sqlite3
    import subprocess

    from ...集成管理.合主干有界跑 import 干净环境
    from ...施工管理.基线并入 import 规则库相对路径

    环境表 = 干净环境()
    仓根 = 样本根 / ("库仓-" + 场景)
    仓根.mkdir(parents=True)
    库件 = 仓根 / 规则库相对路径
    库件.parent.mkdir(parents=True)
    with sqlite3.connect(库件) as 连接:
        连接.execute("create table 规则 (编号 integer primary key, 类 text, 名 text, 内容 text, 依据 text)")
        连接.execute("insert into 规则 values (1,'样本','基规则','基值','')")
        连接.execute("create table 命名登记 (名字 text primary key, 语义 text, 模式 text, 来源 text, 状态 text)")
        连接.execute("insert into 命名登记 values ('基名','基语义','对象+说明','新定义','合格')")
    库件.parent.joinpath("信息核心.py").write_text(假信息核心源码, encoding="utf-8")
    (仓根 / "样本.txt").write_text("主干\n", encoding="utf-8")
    身份 = ["-c", "user.name=样本", "-c", "user.email=样本@例"]

    def 送样本命令(参数表):
        return subprocess.run(["git"] + 参数表, cwd=str(仓根), capture_output=True, text=True, env=环境表)

    送样本命令(["init", "-q", "-b", "主干"])
    送样本命令(["add", "."])
    送样本命令(身份 + ["commit", "-q", "-m", "主干"])
    送样本命令(["checkout", "-q", "-b", "腿/v1-900003"])
    with sqlite3.connect(库件) as 连接:
        if 场景 == "加行":
            连接.execute("insert into 规则 values (2,'样本','腿规则','腿值','')")
            连接.execute("insert into 命名登记 values ('腿名','腿语义','对象+说明','新定义','合格')")
        else:
            连接.execute("update 规则 set 内容='腿值' where 编号=1")
    送样本命令(身份 + ["commit", "-q", "-a", "-m", "腿改库"])
    送样本命令(["checkout", "-q", "主干"])
    with sqlite3.connect(库件) as 连接:
        if 场景 == "加行":
            连接.execute("insert into 命名登记 values ('主干名','主语义','对象+说明','新定义','合格')")
        else:
            连接.execute("update 规则 set 内容='主干值' where 编号=1")
    送样本命令(身份 + ["commit", "-q", "-a", "-m", "主改库"])
    工作树 = 样本根 / ("库工作树-" + 场景)
    送样本命令(["worktree", "add", "-q", "--detach", str(工作树), "主干"])
    return 仓根, 工作树


def _库场景样本(临时根) -> list:
    """规则库冲突场景正反样本 ⇒ 样本表。"""
    import sqlite3
    import subprocess

    from ...集成管理.合主干有界跑 import 干净环境
    from ...施工管理.基线并入 import 并入基线, 规则库相对路径

    样本表 = []
    _, 工作树 = _建库样本仓(临时根, "加行")
    退出码, 文本载荷 = 并入基线(工作树, "腿/v1-900003")
    with sqlite3.connect(工作树 / 规则库相对路径) as 连接:
        规则集 = {数据行[0] for 数据行 in 连接.execute("select 编号 from 规则")}
        名集 = {数据行[0] for 数据行 in 连接.execute("select 名字 from 命名登记")}
    样本表.append(("规则库冲突按主键三方重放 ⇒ 保两侧正式增量（腿 规则#2 在 %s · 主干 命名登记在 %s）"
              % (2 in 规则集, "主干名" in 名集),
              退出码 == 0 and 2 in 规则集 and {"基名", "腿名", "主干名"} <= 名集))
    _, 副本工作树 = _建库样本仓(临时根, "同键异值")
    退出码, 文本载荷 = 并入基线(副本工作树, "腿/v1-900003")
    半合并 = subprocess.run(["git", "-C", str(副本工作树), "rev-parse", "--verify", "--quiet", "MERGE_HEAD"],
                        capture_output=True, text=True, env=干净环境()).returncode == 0
    样本表.append(("规则库同键异值 ⇒ 判冲突拒并入且无半合并现场：%s"
              % ("是" if (退出码 != 0 and "不可自动并入" in 文本载荷 and not 半合并) else "否"),
              退出码 != 0 and "不可自动并入" in 文本载荷 and not 半合并))
    return 样本表


def 基线并入样本(仓根, 工具表) -> list:
    """⇒ 样本表（`(说明, 通过?)`）；临时仓 + 临时工作树，跑完即删。"""
    import json
    import shutil
    import subprocess
    import tempfile

    from ...集成管理.合主干有界跑 import 干净环境
    from ...施工管理.基线并入 import 可重生二进制, 并入基线

    样本表 = []
    临时根 = Path(tempfile.mkdtemp(prefix="v1基线并入样本-"))
    环境表 = 干净环境()
    try:
        样本仓 = _建样本仓(临时根 / "仓")
        工作树 = 临时根 / "工作树"
        subprocess.run(["git", "-C", str(样本仓), "worktree", "add", "-q", "--detach", str(工作树), "主干"],
                   capture_output=True, text=True, env=环境表)
        读数 = 工具表["v1_task"][0]({}, 仓根)
        登记可选 = ((json.loads(读数[1]).get("结果") or {}).get("操作目录") or {}).get("登记", {}).get("可选", [])
        样本表.append(("`登记` 参数面声明了 `基线`：%s" % ("是" if "基线" in 登记可选 else "否"),
                 "基线" in 登记可选))
        样本表.append(("`.db` 归可重生二进制（冲突时走取本支线侧那一路）：库.db=%s · 源码件=%s"
                 % (可重生二进制("开发工具/信息核心/信息核心.db"), 可重生二进制("开发工具/MCP服务/施工管理/开工.py")),
                 可重生二进制("开发工具/信息核心/信息核心.db")
                 and not 可重生二进制("开发工具/MCP服务/施工管理/开工.py")))
        退出码, 输出文本 = 并入基线(工作树, "腿/v1-999999")
        样本表.append(("基线不存在 ⇒ 清晰拒（退出码 %d · 含「不存在」）：%s"
                 % (退出码, "是" if "不存在" in 输出文本 else "否"),
                 退出码 == 2 and "不存在" in 输出文本))
        退出码, 输出文本 = 并入基线(工作树, "腿/v1-900001")
        半合并 = subprocess.run(["git", "-C", str(工作树), "rev-parse", "--verify", "--quiet", "MERGE_HEAD"],
                         capture_output=True, text=True, env=环境表).returncode == 0
        样本表.append(("源码件冲突 ⇒ 清晰拒（退出码 %d · 含「不可自动并入」）且无半合并现场：%s"
                 % (退出码, "是" if (退出码 == 2 and "不可自动并入" in 输出文本 and not 半合并) else "否"),
                 退出码 == 2 and "不可自动并入" in 输出文本 and not 半合并))
        退出码, 输出文本 = 并入基线(工作树, "腿/v1-900002")
        样本表.append(("指定可合基线 ⇒ 新工作树含基线成果（新.txt）：退出码 %d"
                 % 退出码, 退出码 == 0 and (工作树 / "新.txt").is_file()))
        退出码, 输出文本 = 并入基线(工作树, "瞎基线")
        样本表.append(("基线形状非法 ⇒ 退出码 %d（期望 2）" % 退出码, 退出码 == 2))
        样本表 += _库场景样本(临时根)     # 规则库冲突：按主键三方重放，保两侧源表正式增量
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表
