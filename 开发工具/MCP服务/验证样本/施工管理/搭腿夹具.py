# -*- coding: utf-8 -*-
"""搭腿夹具 —— 搭一条「已合主干 + 净树」的真腿（临时真仓 + 真工作树 + 临时账本）。

从 `释放样本.py` 分出（该件行数已顶判据 ⑲ 的 400 上限）；只被释放那几组样本用。
"""
import sqlite3
import subprocess

from ... import 开工账本


def 搭腿夹具(临时根, 开工号="v1-900001"):
    """搭一条「已合主干 + 净树」的真腿：临时真仓 + 真工作树 + 临时账本 ⇒ `(仓根, 工作树, 账本件)`。

    主干 `--ff-only` 合入腿支线 ⇒ `仓操作.检查清树安全`（真跑）判「已合主干且净树」为真。
    """
    from ...集成管理.合主干有界跑 import 干净环境
    仓根 = 临时根 / "主工作树"
    工作树 = 临时根 / "工作树"
    仓根.mkdir()

    def 执行命令(参数表, cwd=仓根):
        回执 = subprocess.run(["git", *参数表], cwd=str(cwd), capture_output=True, text=True,
                           env=干净环境(), timeout=5)
        assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
        return 回执.stdout.strip()

    执行命令(["init", "-b", "主干"])
    执行命令(["config", "user.name", "清树门禁样本"])
    执行命令(["config", "user.email", "gate@example.invalid"])
    (仓根 / "件.txt").write_text("基\n", encoding="utf-8")
    执行命令(["add", "件.txt"])
    执行命令(["commit", "-m", "基"])
    执行命令(["worktree", "add", "-b", "腿/" + 开工号, str(工作树)])
    (工作树 / "成果.txt").write_text("腿成果\n", encoding="utf-8")
    执行命令(["add", "成果.txt"], cwd=工作树)
    执行命令(["commit", "-m", "腿成果"], cwd=工作树)
    执行命令(["merge", "--ff-only", "腿/" + 开工号])
    账本件 = 临时根 / "账本.db"
    连接 = sqlite3.connect(str(账本件))
    连接.row_factory = sqlite3.Row
    for 建表行 in 开工账本.建表语句:
        连接.execute(建表行)
    开工账本.登记开工(连接, 开工号, "清树门禁样本", "腿/" + 开工号, str(工作树))
    开工账本.置状态(连接, 开工号, 开工账本.状态_已释放)
    连接.commit()
    连接.close()
    return 仓根, 工作树, 账本件
