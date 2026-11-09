# -*- coding: utf-8 -*-
"""消失腿承接样本 —— `单纯释放` 在「工作树与支线都不在」时必取证的**真夹具反证**。

一片临时真仓 + 临时账本：真提交、真 ff 合并、真删工作树、真删支线；只把 `非终态作业`
（会读真作业账本）与 `未蒸馏反馈行`（反馈包未合入）按档替身。

十档：**无承接拒 · 自指拒 · 形状不认识拒 · 假提交拒 · 非主干祖先拒 · 落点缺失拒 ·
承接提交放行 · 续作树放行 · 幂等再放行**，外加 `是消失腿` 的负例（树还在就不算消失腿）。
"""
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from ... import 开工账本
from ...施工管理 import 承接证据, 开工
from ...集成管理 import 清树门禁
from ...集成管理.合主干有界跑 import 干净环境


def 删掉树与支线(仓根, 工作树, 支线名):
    """真删：移除工作树登记与目录、删支线 ⇒ 造出「树与支线都不在」这一态。"""
    for 参数表 in (["worktree", "remove", "--force", str(工作树)],
                ["worktree", "prune"], ["branch", "-D", 支线名]):
        回执 = subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                           env=干净环境(), timeout=5)
        assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)


def 搭消失腿夹具(临时根, 带认领=True, 状态=开工账本.状态_进行中):
    """搭一条「活已合主干、树与支线随后都消失」的腿 ⇒ `(仓根, 开工号, 腿提交, 账本件)`。"""
    仓根 = 临时根 / "主工作树"
    工作树 = 临时根 / "工作树"
    仓根.mkdir()
    开工号 = "v1-900001"

    def 跑git命令(参数表, cwd=仓根):
        回执 = subprocess.run(["git", *参数表], cwd=str(cwd), capture_output=True, text=True,
                           env=干净环境(), timeout=5)
        assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
        return 回执.stdout.strip()

    跑git命令(["init", "-b", "主干"])
    跑git命令(["config", "user.name", "消失腿样本"])
    跑git命令(["config", "user.email", "zombie@example.invalid"])
    (仓根 / "件.txt").write_text("基\n", encoding="utf-8")
    跑git命令(["add", "件.txt"])
    跑git命令(["commit", "-m", "基"])
    跑git命令(["worktree", "add", "-b", "腿/" + 开工号, str(工作树)])
    (工作树 / "成果.txt").write_text("腿成果\n", encoding="utf-8")
    跑git命令(["add", "成果.txt"], cwd=工作树)
    跑git命令(["commit", "-m", "腿成果"], cwd=工作树)
    腿提交 = 跑git命令(["rev-parse", "HEAD"], cwd=工作树)
    跑git命令(["merge", "--ff-only", "腿/" + 开工号])
    账本件 = 临时根 / "账本.db"
    连接 = sqlite3.connect(str(账本件))
    连接.row_factory = sqlite3.Row
    for 建表行 in 开工账本.建表语句:
        连接.execute(建表行)
    开工账本.登记开工(连接, 开工号, "消失腿承接样本", "腿/" + 开工号, str(工作树))
    if 带认领:
        开工账本.认领文件(连接, 开工号, {"成果.txt": "0" * 64})
    开工账本.置状态(连接, 开工号, 状态)
    连接.commit()
    连接.close()
    删掉树与支线(仓根, 工作树, "腿/" + 开工号)
    return 仓根, 开工号, 腿提交, 账本件


def _开账(账本件):
    新连接 = sqlite3.connect(str(账本件))
    新连接.row_factory = sqlite3.Row
    return 新连接


def _账本状态(账本件, 开工号):
    连接 = _开账(账本件)
    try:
        return 开工账本.读开工(连接, 开工号)["状态"]
    finally:
        连接.close()


def _断言拒(档名, 退出码, 说明, 期望含, 账本件, 开工号):
    assert 退出码 == 1, (档名, 退出码, 说明)
    assert 期望含 in 说明, (档名, 期望含, 说明)
    assert _账本状态(账本件, 开工号) == 开工账本.状态_进行中, (档名, "拒了却把状态翻了")


def _断言放行(档名, 退出码, 说明, 账本件, 开工号):
    assert 退出码 == 0, (档名, 退出码, 说明)
    assert _账本状态(账本件, 开工号) == 开工账本.状态_已释放, (档名, "放行了却没翻已释放")


def _跑档内(档名, 临时根) -> tuple:
    """一档的完整运行：真夹具 + 真 `单纯释放` + 真断言 ⇒ `(档名, True)`。"""

    def 替身两件():
        """`非终态作业` / `未蒸馏反馈行` 按档替身（其余门禁全真跑）。"""
        原件表 = (清树门禁.非终态作业, 清树门禁.未蒸馏反馈行, 开工账本.连账本)
        清树门禁.非终态作业 = lambda *占位参数: []
        清树门禁.未蒸馏反馈行 = lambda *占位参数: []
        return 原件表

    def 还原(原件表):
        清树门禁.非终态作业, 清树门禁.未蒸馏反馈行, 开工账本.连账本 = 原件表

    if 档名 == "续作树放行":
        仓根, 开工号, 腿提交, 账本件 = 搭消失腿夹具(临时根, 带认领=False)
        连接 = _开账(账本件)
        try:
            承接腿号 = "v1-900002"
            开工账本.登记开工(连接, 承接腿号, "承接腿（续作源头）", "腿/" + 承接腿号,
                         str(临时根 / "工作树"))
            开工账本.认领文件(连接, 承接腿号, {"成果.txt": "0" * 64})
            开工账本.置状态(连接, 承接腿号, 开工账本.状态_已释放)
            连接.commit()
        finally:
            连接.close()
        原件表 = 替身两件()
        开工账本.连账本 = lambda: _开账(账本件)
        try:
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, 承接腿号)
        finally:
            还原(原件表)
        _断言放行(档名, 退出码, 说明, 账本件, 开工号)
        assert "承接开工号" in 说明, (档名, 说明)
        return 档名, True

    仓根, 开工号, 腿提交, 账本件 = 搭消失腿夹具(临时根)
    原件表 = 替身两件()
    开工账本.连账本 = lambda: _开账(账本件)
    try:
        if 档名 == "无承接拒":
            退出码, 说明 = 开工.单纯释放(仓根, 开工号)
            _断言拒(档名, 退出码, 说明, "必须给 `承接`", 账本件, 开工号)
        elif 档名 == "自指拒":
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, 开工号)
            _断言拒(档名, 退出码, 说明, "指回本开工", 账本件, 开工号)
        elif 档名 == "形状不认识拒":
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, "不是提交也不是开工号")
            _断言拒(档名, 退出码, 说明, "形状不认识", 账本件, 开工号)
        elif 档名 == "假提交拒":
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, "deadbeefdeadbeef")
            _断言拒(档名, 退出码, 说明, "是仓里真实提交对象", 账本件, 开工号)
        elif 档名 == "非主干祖先拒":
            跑git命令 = lambda 参数表, cwd=仓根: subprocess.run(
                ["git", *参数表], cwd=str(cwd), capture_output=True, text=True,
                env=干净环境(), timeout=5)
            跑git命令(["checkout", "-b", "临时/孤儿"])
            (仓根 / "孤儿.txt").write_text("孤儿\n", encoding="utf-8")
            跑git命令(["add", "孤儿.txt"])
            跑git命令(["commit", "-m", "孤儿"])
            孤儿提交 = 跑git命令(["rev-parse", "HEAD"]).stdout.strip()
            跑git命令(["checkout", "主干"])
            跑git命令(["branch", "-D", "临时/孤儿"])
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, 孤儿提交)
            _断言拒(档名, 退出码, 说明, "在主干历史里", 账本件, 开工号)
        elif 档名 == "落点缺失拒":
            连接 = _开账(账本件)
            try:
                开工账本.认领文件(连接, 开工号, {"缺失/缺件.txt": "0" * 64})
                连接.commit()
            finally:
                连接.close()
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, 腿提交)
            _断言拒(档名, 退出码, 说明, "缺失/缺件.txt", 账本件, 开工号)
        elif 档名 == "承接提交放行":
            退出码, 说明 = 开工.单纯释放(仓根, 开工号, 腿提交)
            _断言放行(档名, 退出码, 说明, 账本件, 开工号)
            assert "承接证据" in 说明, (档名, 说明)
        elif 档名 == "幂等再放行":
            首回 = 开工.单纯释放(仓根, 开工号, 腿提交)
            _断言放行(档名, 首回[0], 首回[1], 账本件, 开工号)
            再回 = 开工.单纯释放(仓根, 开工号)
            _断言放行(档名, 再回[0], 再回[1], 账本件, 开工号)
            assert "无物可清" in 再回[1], (档名, 再回[1])
        else:
            raise AssertionError("未知档：" + 档名)
    finally:
        还原(原件表)
    return 档名, True


def 跑一档承接(档名: str) -> tuple:
    """一档一片临时真仓（互不依赖，可并行）⇒ `(档名, True)`。"""
    with tempfile.TemporaryDirectory(prefix="v1消失腿-") as 临时目录:
        return _跑档内(档名, Path(临时目录))


def 消失腿承接样本() -> list:
    """九档逐档真跑；`是消失腿` 另做一条「树还在 ⇒ 不算消失腿」的负例。"""
    承接档名 = ("无承接拒", "自指拒", "形状不认识拒", "假提交拒", "非主干祖先拒",
             "落点缺失拒", "承接提交放行", "续作树放行", "幂等再放行")
    样本表 = [跑一档承接(档名) for 档名 in 承接档名]
    assert 跑一档承接("承接提交放行")[1], "单档复跑失败"
    with tempfile.TemporaryDirectory(prefix="v1消失腿负例-") as 临时目录:
        临时根 = Path(临时目录)
        仓根 = 临时根 / "主工作树"
        仓根.mkdir()
        for 参数表 in (["init", "-b", "主干"], ["config", "user.name", "消失腿负例"],
                    ["config", "user.email", "zombie@example.invalid"]):
            subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                           env=干净环境(), timeout=5, check=True)
        (仓根 / "件.txt").write_text("基\n", encoding="utf-8")
        subprocess.run(["git", "add", "件.txt"], cwd=str(仓根), check=True,
                       capture_output=True, env=干净环境(), timeout=5)
        subprocess.run(["git", "commit", "-m", "基"], cwd=str(仓根), check=True,
                       capture_output=True, env=干净环境(), timeout=5)
        工作树 = 仓根
        assert not 承接证据.是消失腿(仓根, {"工作树": str(工作树), "开工号": "v1-900009"}), \
            "树在盘上（退化为主树）也被判成消失腿 ⇒ 会把正常腿误拦"
        样本表.append(("树还在不算消失腿", True))
    return 样本表
