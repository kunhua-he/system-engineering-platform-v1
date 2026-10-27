# -*- coding: utf-8 -*-
"""空改主干样本 —— 空改已合主干腿改走「当前主干门禁」的正反真样本。

为什么要有它（2026-10-08 实测根因）：旧腿树是**当年的快照**，缺 `构建装配/门禁/复跑.py`
（2026-10-08 才加）⇒ 空改释放复用共享 pre-commit 时 `ROOT = 腿树` ⇒
`ImportError: cannot import name '跑并复跑超顶'` ⇒ 30 条成果早已在主干上的空改腿**永拒**。

本件用**临时真仓**（主干 + 一条旧骨架腿树，腿 tip 是主干祖先）复现并验收修后的三档：
  · 放行：空改已合净（归属一致 · 无保全项）⇒ 走**当前主干**门禁（断言钩子真跑在主干）；
  · 旧路复现：在同一腿树上跑本腿门禁 ⇒ 复现 `ImportError`（修前的病，直接证据）；
  · 主干真失败 ⇒ 拒（主干门禁未过必须拒释放）；
  · 未合 / 腿树脏 ⇒ 拒（**释放规则一字未改**，仍旧 fail-closed）；
  · 未蒸馏反馈 / 台账点名 ⇒ 拒（保全项）。

真夹具：真 `git init` + 真 `git worktree add` + 真共享 pre-commit 钩子（与仓内真钩子同形 ——
按 ROOT 取门禁）；只把 `未蒸馏反馈行` 按档替身（本腿独有，避免污染真反馈账本）。
分档判据住 `空改门禁.py`（唯一一份）；本件只验它三档的**真行为**。
"""
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from ...施工管理 import 释放作业, 开工, 仓操作
from ... import 开工账本
from ...文件编辑 import 写盘账本
from ...集成管理.合主干有界跑 import 干净环境

旧导出 = ("# -*- coding: utf-8 -*-\n"
        "\"\"\"门禁（旧骨架）：**没有** 跑并复跑超顶 —— 复现旧腿树缺件。\"\"\"\n"
        "from .常量 import 硬顶毫秒\n"
        "\n"
        "__all__ = [\"硬顶毫秒\"]\n")
新导出 = ("# -*- coding: utf-8 -*-\n"
        "\"\"\"门禁（现行）：导出 跑并复跑超顶。\"\"\"\n"
        "from .常量 import 硬顶毫秒\n"
        "from .复跑 import 跑并复跑超顶, 是瞬时超顶\n"
        "\n"
        "__all__ = [\"硬顶毫秒\", \"跑并复跑超顶\", \"是瞬时超顶\"]\n")
# 夹具共享钩子：与仓内真钩子同形 —— 按 ROOT 取该树的 `构建装配.门禁` 与 `闸0.py`。
# 旧骨架树缺 `复跑.py` ⇒ 在腿树跑即 `ImportError`（复现修前的病）；主干树有 ⇒ 跑主干闸0。
# 落一枚读数件（记 ROOT 路径）⇒ 断言钩子真跑在哪棵树。
钩子正文 = ("#!/bin/sh\n"
         "ROOT=$(git rev-parse --show-toplevel) || exit 1\n"
         "cd \"$ROOT\" || exit 1\n"
         "printf '%s\\n' \"$ROOT\" >> \"$(git rev-parse --git-common-dir)/门禁读数\"\n"
         "\"$V1_PY\" - \"$ROOT\" <<'PY'\n"
         "import subprocess\n"
         "import sys\n"
         "sys.path.insert(0, sys.argv[1])\n"
         "from 构建装配.门禁 import 跑并复跑超顶\n"
         "回执 = subprocess.run([sys.executable, \"构建装配/一键验证/闸0.py\"],\n"
         "                    capture_output=True, text=True)\n"
         "sys.exit(回执.returncode)\n"
         "PY\n")


def 搭空改夹具(临时根, 夹具参数):
    """搭一条「旧骨架腿 tip = 主干祖先」的真腿 ⇒ `(仓根, 腿树, 账本件, 开工号)`。

    主干先提交旧骨架（门禁不导出 跑并复跑超顶），腿树检出它；主干再前进一格补 `复跑.py`
    ⇒ 腿 tip 成为主干祖先（`检查清树安全` 判「已合主干」为真）；腿树保持净（空改）。
    """
    仓根 = 临时根 / "主工作树"
    腿树 = 临时根 / "工作树"
    开工号 = "v1-900701"
    仓根.mkdir()

    def 执行命令(参数表, cwd=仓根):
        回执 = subprocess.run(["git", *参数表], cwd=str(cwd), capture_output=True, text=True,
                           env=干净环境(), timeout=5)
        assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
        return 回执.stdout.strip()

    执行命令(["init", "-b", "主干"])
    执行命令(["config", "user.name", "空改主干样本"])
    执行命令(["config", "user.email", "gate@example.invalid"])
    (仓根 / "构建装配/门禁").mkdir(parents=True)
    (仓根 / "构建装配/门禁/常量.py").write_text("硬顶毫秒 = 5000\n", encoding="utf-8")
    (仓根 / "构建装配/门禁/__init__.py").write_text(旧导出, encoding="utf-8")
    (仓根 / "构建装配/一键验证").mkdir(parents=True)
    (仓根 / "构建装配/一键验证/闸0.py").write_text("print('夹具闸0通过')\n", encoding="utf-8")
    执行命令(["add", "-A"])
    执行命令(["commit", "-m", "旧骨架"])
    执行命令(["worktree", "add", "-b", 仓操作.分支名(开工号), str(腿树)])
    (仓根 / "构建装配/门禁/复跑.py").write_text(
        "def 是瞬时超顶(输出文本):\n    return \"超顶\" in (输出文本 or \"\")\n\n"
        "def 跑并复跑超顶(执行一次):\n    return 执行一次()\n", encoding="utf-8")
    (仓根 / "构建装配/门禁/__init__.py").write_text(新导出, encoding="utf-8")
    执行命令(["add", "-A"])
    执行命令(["commit", "-m", "主干补复跑"])
    钩子文件 = 仓根 / ".git/hooks/pre-commit"
    钩子文件.write_text(钩子正文, encoding="utf-8")
    钩子文件.chmod(0o755)
    if 夹具参数.get("腿脏"):
        (腿树 / "越界.txt").write_text("未跟踪\n", encoding="utf-8")
    if 夹具参数.get("未合"):
        (腿树 / "腿后加.txt").write_text("腿后加的活\n", encoding="utf-8")
        执行命令(["add", "-A"], cwd=腿树)
        # 造「未合」态本身不是被测点，不跑钩子（`--no-verify`）；被测的是释放时走哪一档。
        执行命令(["commit", "--no-verify", "-m", "腿后加"], cwd=腿树)
    if 夹具参数.get("主干门禁红"):
        (仓根 / "构建装配/一键验证/闸0.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    if 夹具参数.get("台账点名"):
        台账库件 = 仓根 / "开发工具/信息核心/信息核心.db"
        台账库件.parent.mkdir(parents=True, exist_ok=True)
        台账连接 = sqlite3.connect(str(台账库件))
        台账连接.execute("create table if not exists 未完成 "
                    "(号 integer primary key, 缺什么 text, 落点 text, 验证命令 text)")
        台账连接.execute("insert or replace into 未完成(号, 缺什么, 落点, 验证命令) values (311, ?, '', '')",
                    ("点名 %s" % 开工号,))
        台账连接.commit()
        台账连接.close()
    账本件 = 临时根 / "账本.db"
    连接 = sqlite3.connect(str(账本件))
    连接.row_factory = sqlite3.Row
    for 建表行 in 开工账本.建表语句:
        连接.execute(建表行)
    写盘账本.补意图表(连接)
    开工账本.登记开工(连接, 开工号, "空改主干样本", 仓操作.分支名(开工号), str(腿树))
    连接.commit()
    连接.close()
    return 仓根, 腿树, 账本件, 开工号


def 旧路复现样本() -> list:
    """修前的病：同一腿树上跑**本腿门禁** ⇒ `ImportError: 跑并复跑超顶`（直接证据）。"""
    样本表 = []
    with tempfile.TemporaryDirectory(prefix="v1空改旧路-") as 临时目录:
        仓根, 腿树, _账本件, _开工号 = 搭空改夹具(Path(临时目录), {})
        退出码, 输出文本 = 仓操作.跑空改门禁(腿树)
        样本表.append(("旧路复现：本腿门禁缺 `复跑.py` ⇒ 退出码 %d" % 退出码,
                   退出码 != 0 and "ImportError" in 输出文本))
    return 样本表


def 空改主干样本() -> list:
    """空改已合腿走主干门禁的正反真样本 ⇒ `[(说明, 是否好)]`。"""
    from ...集成管理 import 清树门禁
    样本表 = []
    真连 = 开工账本.连账本
    真反馈 = 清树门禁.未蒸馏反馈行
    for 档名, 夹具参数, 期望码, 期望词 in (
            ("放行(空改已合净⇒走主干门禁)", {}, 0, "当前主干门禁"),
            ("主干真失败⇒拒", {"主干门禁红": True}, 1, "门禁没过"),
            ("未合⇒拒", {"未合": True}, 1, "本腿门禁"),
            ("腿树脏⇒拒", {"腿脏": True}, 1, "越界"),
            ("未蒸馏反馈⇒拒(保全)", {"反馈": True}, 1, "保全项"),
            ("台账点名⇒拒(保全)", {"台账点名": True}, 1, "保全项")):
        with tempfile.TemporaryDirectory(prefix="v1空改主干-") as 临时目录:
            临时根 = Path(临时目录)
            仓根, 腿树, 账本件, 开工号 = 搭空改夹具(临时根, 夹具参数)

            def 开账():
                新连接 = sqlite3.connect(str(账本件))
                新连接.row_factory = sqlite3.Row
                return 新连接

            清树门禁.未蒸馏反馈行 = (
                (lambda 连接, 仓根, 开工号: ["反馈X：未判词"]) if 夹具参数.get("反馈") else 真反馈)
            try:
                import unittest.mock as _mock
                # 走**同步真入口** `释放作业.释放主体`（主干已把功能 3 改成后台作业路；
                # 样本要的是同步读数 ⇒ 与 `释放样本.py` 同一口径，不起作业）。
                with _mock.patch.object(开工账本, "连账本", 开账):
                    退出码, 输出文本 = 释放作业.释放主体(仓根, 开工号, 推送=False)
                连接 = 开账()
                状态 = 开工账本.读开工(连接, 开工号)["状态"]
                连接.close()
            finally:
                开工账本.连账本 = 真连
                清树门禁.未蒸馏反馈行 = 真反馈
            过否 = (退出码 == 期望码 and (期望词 is None or 期望词 in 输出文本))
            期望态 = 开工账本.状态_已释放 if 期望码 == 0 else 开工账本.状态_进行中
            过否 = 过否 and 状态 == 期望态
            读数附 = ""
            if 期望码 == 0:
                # 直接证据：钩子确实跑在**主干树**（读数件记的是 ROOT 路径）。
                读数件 = 仓根 / ".git/门禁读数"
                读数线 = 读数件.read_text(encoding="utf-8").strip().splitlines() if 读数件.is_file() else []
                跑主干 = bool(读数线) and all(str(仓根) in 逐行 for 逐行 in 读数线)
                过否 = 过否 and 跑主干
                读数附 = " · 钩子跑主干=%s" % 跑主干
            样本表.append(("空改主干·%s：退出码 %d（期望 %d）· 状态 %s%s"
                        % (档名, 退出码, 期望码, 状态, 读数附), 过否))
    return 样本表
