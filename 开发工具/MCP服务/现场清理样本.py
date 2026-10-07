# -*- coding: utf-8 -*-
"""现场清理样本 —— 失败集成现场「恢复/清理」的**正反**样本（临时真仓 + 真 git）。

四条（收口方 v1-100533 实测的两条缺口）：
  ① DB-only UU 现场 ⇒ `--恢复现场` 收敛（源库取主干版 + 重放腿值，代码无冲突不算冲突）；
  ② 旧主干基现场（主干已推进过它）⇒ `--清理现场` 成功；
  ③ 真未解决的**代码**冲突 ⇒ `--恢复现场` 仍拒（不自动解冲突）；
  ④ 没有已知现场 / 陌生路径 ⇒ `--清理现场` 仍拒（只认本服务登记的集成树）。

仓一个字节都不改：夹具是系统临时目录里的真仓，跑完删净；所有子进程一律走仓内 `干净环境()`。
"""
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from . import 合主干编排 as 编排, 合主干集成树 as 集成, 集成接管, 开工账本
from .合主干有界跑 import 干净环境
from .合主干现场清理 import 未解决代码冲突, 清现场, 库相对路径

假信息核心源码 = (
    "import sqlite3, sys\n"
    "from pathlib import Path\n"
    "参表 = sys.argv[1:]\n"
    "键值 = {}\n"
    "键 = None\n"
    "for 项 in 参表[1:]:\n"
    "    if 项.startswith('--'):\n"
    "        键 = 项[2:]\n"
    "        键值[键] = ''\n"
    "    elif 键:\n"
    "        键值[键] = 项\n"
    "if 参表[0] != '登记':\n"
    "    raise SystemExit(3)\n"
    "连接 = sqlite3.connect(str(Path('开发工具/信息核心/信息核心.db')))\n"
    "连接.execute('insert or replace into 命名登记 (名字, 语义, 模式, 来源, 状态) values (?,?,?,?,?)',\n"
    "           (键值.get('名字', ''), 键值.get('语义', ''), 键值.get('模式', '对象+说明'),\n"
    "            键值.get('来源', '新定义'), 键值.get('状态', '合格')))\n"
    "连接.commit()\n"
    "连接.close()\n"
    "print('登记 ok')\n"
)


def _跑git(仓根, *参数表):
    回执 = subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                       env=干净环境(), timeout=5)
    assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
    return 回执.stdout.strip()


def _建库(库路径):
    库路径.parent.mkdir(parents=True, exist_ok=True)
    连接 = sqlite3.connect(str(库路径))
    连接.execute("create table 规则 (编号 integer primary key, 类 text, 名 text, 内容 text, 依据 text)")
    连接.execute("insert into 规则 values (1, '样本', '语义', '基值', '')")
    连接.execute("create table 命名登记 (名字 text primary key, 语义 text, 模式 text, 来源 text, "
             "状态 text, 出现次数 integer, 创建时间 text)")
    连接.execute("insert into 命名登记 values ('样本名', '基语义', '对象+说明', '新定义', '合格', 0, '')")
    连接.commit()
    连接.close()


def _搭基座(临时根):
    主目录 = 临时根 / "主目录"
    主目录.mkdir()
    for 参数表 in (("init", "-b", "主干"), ("config", "user.name", "样本"),
               ("config", "user.email", "fixture@example.invalid")):
        _跑git(主目录, *参数表)
    (主目录 / "README.md").write_text("系统工程平台 V1\n", encoding="utf-8")
    (主目录 / "AGENTS.md").write_text("样本\n", encoding="utf-8")
    (主目录 / "样本.txt").write_text("基线\n", encoding="utf-8")
    门禁件 = 主目录 / "构建装配/一键验证/闸0.py"
    门禁件.parent.mkdir(parents=True)
    门禁件.write_text("print('腿闸通过')\n", encoding="utf-8")
    信息核心件 = 主目录 / "开发工具/信息核心/信息核心.py"
    信息核心件.parent.mkdir(parents=True)
    信息核心件.write_text(假信息核心源码, encoding="utf-8")
    _建库(主目录 / 库相对路径)
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "基线")
    钩子 = 主目录 / ".git/hooks/pre-commit"
    钩子.write_text("#!/bin/sh\nexit 0\n")
    钩子.chmod(0o755)
    return 主目录


def _建腿树(主目录, 开工号):
    腿树 = 主目录.parent / ("腿目录-" + 开工号)
    _跑git(主目录, "worktree", "add", "-b", "腿/" + 开工号, str(腿树))
    return 腿树


def _造现场(主目录, 开工号):
    """在主干上建隔离集成树并合腿 ⇒ 留下真冲突现场（`git merge --no-commit --no-ff`）。"""
    集成树 = 主目录.parent / ("集成目录-" + 开工号)
    _跑git(主目录, "worktree", "add", "-b", "集成/" + 开工号, str(集成树), "主干")
    回执 = subprocess.run(["git", "merge", "--no-commit", "--no-ff", "腿/" + 开工号],
                       cwd=str(集成树), capture_output=True, text=True, env=干净环境(), timeout=5)
    assert "CONFLICT" in (回执.stdout + 回执.stderr), (回执.stdout, 回执.stderr)
    return 集成树


def _改库(树根, 语句):
    with sqlite3.connect(str(树根 / 库相对路径)) as 连接:
        连接.execute(语句)


def _读库值(库路径, 语句):
    连接 = sqlite3.connect("file:%s?mode=ro" % 库路径, uri=True)
    try:
        return 连接.execute(语句).fetchone()[0]
    finally:
        连接.close()


def _建空账本(账本件):
    连接 = sqlite3.connect(str(账本件))
    for 建表行 in 开工账本.建表语句:
        连接.execute(建表行)
    连接.commit()
    连接.close()


def _开账(账本件):
    连接 = sqlite3.connect(str(账本件))
    连接.row_factory = sqlite3.Row
    return 连接


def _开工记录(腿树, 开工号):
    return {"状态": "已释放", "工作树": str(腿树), "分支名": "腿/" + 开工号}


def _场一(临时根):
    """① DB-only UU：腿改命名登记、主干改规则 ⇒ 库二进制冲突，但三方分类可收敛。"""
    临时根.mkdir(parents=True, exist_ok=True)
    开工号 = "v1-999001"
    主目录 = _搭基座(临时根)
    腿树 = _建腿树(主目录, 开工号)
    (腿树 / "新增.txt").write_text("腿成果\n", encoding="utf-8")
    _改库(腿树, "update 命名登记 set 语义='腿语义' where 名字='样本名'")
    _跑git(腿树, "add", ".")
    _跑git(腿树, "commit", "-m", "腿成果")
    _改库(主目录, "update 规则 set 内容='主干值' where 编号=1")
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "主改源库")
    _造现场(主目录, 开工号)
    with mock.patch.object(编排, "_读开工记录", return_value=_开工记录(腿树, 开工号)), \
         mock.patch.object(集成接管, "解除接管", return_value=(0, "样本：解除接管跳过")):
        退出码, 报告 = 编排.派发(开工号, False, 主目录, 操作="恢复现场")
    树在 = 集成.找集成树(主目录, 开工号)
    库件 = 主目录 / 库相对路径
    语义 = _读库值(库件, "select 语义 from 命名登记 where 名字='样本名'")
    规则 = _读库值(库件, "select 内容 from 规则 where 编号=1")
    新增在 = (主目录 / "新增.txt").is_file()
    return [("① DB-only UU 现场 --恢复现场：退出码 %d（期望 0）· 集成树已清 %s · 源库收敛（命名登记=%s · 规则=%s · 新增.txt %s）"
             % (退出码, "是" if not 树在 else "否", 语义, 规则, "在" if 新增在 else "缺"),
             退出码 == 0 and not 树在 and 语义 == "腿语义" and 规则 == "主干值" and 新增在)]


def _场二(临时根):
    """② 旧主干基：腿只改库（现场除源库外无成果），造现场后另起提交推进主干。"""
    临时根.mkdir(parents=True, exist_ok=True)
    开工号 = "v1-999002"
    主目录 = _搭基座(临时根)
    腿树 = _建腿树(主目录, 开工号)
    _改库(腿树, "update 命名登记 set 语义='腿语义' where 名字='样本名'")
    _跑git(腿树, "add", ".")
    _跑git(腿树, "commit", "-m", "腿成果")
    _改库(主目录, "update 规则 set 内容='主干值' where 编号=1")
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "主改源库")
    _造现场(主目录, 开工号)
    (主目录 / "推进.txt").write_text("主干推进\n", encoding="utf-8")
    _跑git(主目录, "add", "推进.txt")
    _跑git(主目录, "commit", "-m", "主干推进")
    退出码, 报告 = 编排.派发(开工号, False, 主目录, 操作="清理现场")
    树在 = 集成.找集成树(主目录, 开工号)
    支线在 = _跑git(主目录, "branch", "--list", "集成/" + 开工号)
    return [("② 旧主干基现场 --清理现场：退出码 %d（期望 0）· 集成树已清 %s · 集成支线已删 %s · 报告说「旧主干基」%s"
             % (退出码, "是" if not 树在 else "否", "是" if not 支线在 else "否",
                "是" if "旧主干基" in 报告 else "否"),
             退出码 == 0 and not 树在 and not 支线在 and "旧主干基" in 报告)]


def _场三四(临时根):
    """③④ 同一夹具：真代码冲突现场（恢复仍拒）＋ 陌生开工号 / 陌生路径（清理仍拒）。"""
    临时根.mkdir(parents=True, exist_ok=True)
    开工号 = "v1-999003"
    主目录 = _搭基座(临时根)
    腿树 = _建腿树(主目录, 开工号)
    (腿树 / "样本.txt").write_text("腿改\n", encoding="utf-8")
    _改库(腿树, "update 命名登记 set 语义='腿语义' where 名字='样本名'")
    _跑git(腿树, "add", ".")
    _跑git(腿树, "commit", "-m", "腿成果")
    (主目录 / "样本.txt").write_text("主改\n", encoding="utf-8")
    _改库(主目录, "update 规则 set 内容='主干值' where 编号=1")
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "主改")
    集成树 = _造现场(主目录, 开工号)
    判定码, 冲突项 = 未解决代码冲突(集成树)
    with mock.patch.object(编排, "_读开工记录", return_value=_开工记录(腿树, 开工号)):
        退出码, 报告 = 编排.派发(开工号, False, 主目录, 操作="恢复现场")
    树在 = 集成.找集成树(主目录, 开工号)
    无号码, 无号报告 = 编排.派发("v1-999777", False, 主目录, 操作="清理现场")
    陌生路径 = 主目录.parent / "陌生目录"
    陌生路径.mkdir()
    目标码, 目标说明 = 清现场(主目录, 陌生路径, 开工号)
    return [
        ("③ 未解决代码冲突（单元）：未解决代码冲突(集成树) = %r（期望 ['样本.txt']，源库不算）" % (冲突项,),
         判定码 == 0 and 冲突项 == ["样本.txt"]),
        ("③ 未解决代码冲突 --恢复现场：退出码 %d（期望非 0）· 现场保留 %s · 报告提冲突或接管 %s"
         % (退出码, "是" if 树在 else "否", "是" if ("冲突" in 报告 or "接管" in 报告) else "否"),
         退出码 != 0 and bool(树在) and ("冲突" in 报告 or "接管" in 报告)),
        ("④ 陌生开工号 --清理现场：退出码 %d（期望非 0）· 说「不清未知目录」%s"
         % (无号码, "是" if "不清未知目录" in 无号报告 else "否"),
         无号码 != 0 and "不清未知目录" in 无号报告),
        ("④ 陌生路径 清现场：退出码 %d（期望非 0）· 说「集成目标不符」%s · 现场未动 %s"
         % (目标码, "是" if "集成目标不符" in 目标说明 else "否", "是" if 树在 else "否"),
         目标码 != 0 and "集成目标不符" in 目标说明 and bool(树在)),
    ]


def 现场清理样本(仓根=None, 工具表=None) -> list:
    """四条正反样本 ⇒ 样本表（跑完临时仓与临时账本都删净）。"""
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="v1现场清理样本-") as 临时目录:
        临时根 = Path(临时目录)
        账本件 = 临时根 / "账本.db"
        _建空账本(账本件)
        真连 = 开工账本.连账本
        开工账本.连账本 = lambda: _开账(账本件)
        try:
            样本表 += _场一(临时根 / "一")
            样本表 += _场二(临时根 / "二")
            样本表 += _场三四(临时根 / "三四")
        finally:
            开工账本.连账本 = 真连
    return 样本表
