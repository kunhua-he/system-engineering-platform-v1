# -*- coding: utf-8 -*-
"""集成腿退场样本 —— 接管集成腿（分支 `集成/<原腿>`）走正式 `单纯释放` 的**正反**样本。

为什么单开一件：`集成接管样本.py` 已 301 行，加进去会顶 400 行硬顶（判据 ⑲）⇒ 增量落新件。

口径（债务 10108401）：退场口问支线/工作树**只认账本那一行**（`仓操作.分支名` 是唯一解析节点），
不许硬拼 `腿/<号>` —— 接管腿的分支是 `集成/<原腿>`；硬拼 ⇒ `清工作树` 判「无物可清」、状态却
翻「已释放」，集成树与支线留在盘上（第一档即复现这一漏）。

四档 + 一档回归（临时真仓 + 真账本，跑完删净）：
  ① 已合主干·净树 ⇒ 真清树 + 真删支线 + 状态「已释放」
  ② 未合主干 ⇒ 拒并保留（未合成果不得误删）
  ③ 脏树 ⇒ 拒并保留
  ④ 不在账本 ⇒ `单纯释放` 报「没有这条开工」；`分支名` 退回老口径 `腿/<号>`
  ⑤ 普通腿回归：账本分支 `腿/<号>` ⇒ 解析结果不变
"""
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from ...施工管理 import 开工, 仓操作
from ... import 开工账本 as 账本
from ...集成管理.合主干有界跑 import 干净环境

档表 = (("已合主干", True, False, True), ("未合主干", False, False, True),
        ("脏树", True, True, True), ("不在账本", False, False, False))


def _跑git(仓根, *参数表):
    回执 = subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                       env=干净环境(), timeout=10)
    assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
    return 回执.stdout.strip()


def _开账(账本路径):
    连接 = sqlite3.connect(str(账本路径), uri=True)
    连接.row_factory = sqlite3.Row
    return 连接


def _建仓(场根):
    仓根 = 场根 / "主工作树"
    仓根.mkdir(parents=True)
    _跑git(仓根, "init", "-b", "主干")
    _跑git(仓根, "config", "user.name", "样本")
    _跑git(仓根, "config", "user.email", "fixture@example.invalid")
    # 不在夹具里改仓配置（那行会掩盖路径读数：节点坏掉时夹具仍然绿）。改为**行为断言**：
    # 本样本验的正是路径集合比对（④ 覆盖判定）⇒ 先证明中文+空格路径能按原字节读回。
    中文样本件 = 仓根 / "中文 样本.txt"
    中文样本件.write_text("旧内容\n", encoding="utf-8")
    _, 中文路径表 = 仓操作.变更路径表(仓根)
    assert "中文 样本.txt" in 中文路径表, (
        "中文/含空格路径没按原字节读出（`-z` + 唯一解析节点的口径坏了）：%s" % 中文路径表)
    中文样本件.unlink()
    (仓根 / "样本.txt").write_text("旧内容\\n", encoding="utf-8")
    _跑git(仓根, "add", "--", "样本.txt")
    _跑git(仓根, "commit", "-m", "基线")
    return 仓根


def _一场(临时根, 序号, 档名, 已合主干, 脏树, 登记):
    原腿 = "v1-99980%d" % 序号
    接管号 = "v1-99990%d" % 序号
    分支 = "集成/" + 原腿
    仓根 = _建仓(临时根 / ("场%d" % 序号))
    集成树 = 仓根.parent / "集成树"
    _跑git(仓根, "worktree", "add", "-b", 分支, str(集成树))
    (集成树 / "样本.txt").write_text("冲突已解\\n", encoding="utf-8")
    _跑git(集成树, "add", "--", "样本.txt")
    _跑git(集成树, "commit", "-m", "接管腿解冲突")
    if 已合主干:
        _跑git(仓根, "merge", "--ff-only", 分支)
    if 脏树:
        (集成树 / "样本.txt").write_text("绕过 v1_edit 直改\\n", encoding="utf-8")
    if 登记:
        连接 = 账本.连账本()
        账本.登记开工(连接, 接管号, "接管集成现场 %s 解冲突" % 原腿, 分支, str(集成树))
        账本.记归属(连接, 接管号, 原腿, 账本.种类_接管)
        账本.置状态(连接, 接管号, 账本.状态_已释放)
        连接.close()
    解析名 = 仓操作.分支名(接管号)
    退出码, 回执 = 开工.单纯释放(仓根, 接管号)
    树残留 = 集成树.is_dir()
    支线残留 = bool(_跑git(仓根, "branch", "--list", 分支))
    if not 登记:
        成立 = 退出码 != 0 and "没有这条开工" in 回执 and 解析名 == "腿/" + 接管号
    elif 已合主干 and not 脏树:
        连接 = 账本.连账本()
        状态 = 账本.读开工(连接, 接管号)["状态"]
        连接.close()
        成立 = (退出码 == 0 and not 树残留 and not 支线残留
              and 状态 == 账本.状态_已释放 and 解析名 == 分支)
    else:
        成立 = 退出码 != 0 and 树残留 and 支线残留 and 解析名 == 分支
    return [("%s（%s）：解析分支 %r（期望 %r）· 退出码 %d · 树残留 %s · 支线残留 %s"
             % (档名, 接管号, 解析名, 分支 if 登记 else "腿/" + 接管号, 退出码, 树残留, 支线残留),
             成立)]


def _普通腿回归(临时根):
    仓根 = _建仓(临时根 / "普通腿")
    腿树 = 仓根.parent / "腿树"
    分支 = "腿/v1-999921"
    _跑git(仓根, "worktree", "add", "-b", 分支, str(腿树))
    连接 = 账本.连账本()
    账本.登记开工(连接, "v1-999921", "普通腿回归", 分支, str(腿树))
    连接.close()
    解析名 = 仓操作.分支名("v1-999921")
    return [("普通腿回归：分支名 = %r（期望 %r）" % (解析名, 分支), 解析名 == 分支)]


def 验退场() -> list:
    """四档正反 + 普通腿回归 ⇒ 样本表（异常也在内部收尾删净）。"""
    临时根 = Path(tempfile.mkdtemp(prefix="v1集成腿退场-"))
    真连 = (账本.连账本, 账本.只读连账本)
    try:
        账本路径 = 临时根 / "账本.db"
        账本.连账本 = lambda: _开账(账本路径)
        连接 = 账本.连账本()
        for 建表行 in 账本.建表语句:
            连接.execute(建表行)
        连接.commit()
        连接.close()
        # 写口与只读口必须绑定同一本隔离账本，禁止分支查询落到真实运行库。
        账本.只读连账本 = lambda: _开账("file:%s?mode=ro" % 账本路径)
        样本表 = []
        for 序号, (档名, 已合主干, 脏树, 登记) in enumerate(档表, start=1):
            样本表 += _一场(临时根, 序号, 档名, 已合主干, 脏树, 登记)
        样本表 += _普通腿回归(临时根)
        return 样本表
    finally:
        账本.连账本, 账本.只读连账本 = 真连
        shutil.rmtree(临时根, ignore_errors=True)
