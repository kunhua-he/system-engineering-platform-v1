# -*- coding: utf-8 -*-
"""临时真实仓正反样本，不借用项目主仓或正式账本。"""
import copy
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from ...集成管理 import 保全主目录编排 as 保全
from ...集成管理.合主干有界跑 import 干净环境
from 开发工具.运行数据根 import 子目录路径, 解析当前环境
from 开发工具.运行数据根.口径 import 覆盖变量名


def 样本命令(主目录, 命令表):
    回执 = subprocess.run(["git", *命令表], cwd=主目录,
        capture_output=True, text=True, env=干净环境(), timeout=5)
    assert 回执.returncode == 0, (命令表, 回执.stderr)
    return 回执.stdout.strip()


def 样本夹具(夹具根):
    主目录 = (夹具根 / "主仓").resolve()
    主目录.mkdir()
    样本命令(主目录, ["init", "-b", "主干"])
    样本命令(主目录, ["config", "user.name", "隔离样本"])
    样本命令(主目录, ["config", "user.email", "fixture@example.invalid"])
    (主目录 / "README.md").write_text("系统工程平台 V1\n", encoding="utf-8")
    (主目录 / "AGENTS.md").write_text("隔离样本\n", encoding="utf-8")
    样本命令(主目录, ["add", "."])
    样本命令(主目录, ["commit", "-m", "基线"])
    期望提交 = 样本命令(主目录, ["rev-parse", "HEAD"])
    样本命令(主目录, ["checkout", "-b", "腿/v1-100524"])
    for 序号, 路径 in enumerate(保全.授权路径):
        件路径 = 主目录 / 路径
        件路径.parent.mkdir(parents=True, exist_ok=True)
        件路径.write_bytes(("替代完整成果%d\n" % 序号).encode())
    样本命令(主目录, ["add", "."])
    样本命令(主目录, ["commit", "-m", "替代成果"])
    替代提交 = 样本命令(主目录, ["rev-parse", "HEAD"])
    样本命令(主目录, ["checkout", "主干"])
    替代工作树 = 夹具根 / "替代树"
    样本命令(主目录, ["worktree", "add", str(替代工作树), "腿/v1-100524"])
    for 序号, 路径 in enumerate(保全.授权路径):
        件路径 = 主目录 / 路径
        件路径.parent.mkdir(parents=True, exist_ok=True)
        件路径.write_bytes(("已审无独有旧稿%d\n" % 序号).encode())
    样本命令(主目录, ["config", "core.bare", "true"])
    库路径 = 子目录路径(解析当前环境(), "数据库") / "开工账本.db"
    库路径.parent.mkdir(parents=True)
    with sqlite3.connect(库路径) as 连接:
        连接.execute("create table 开工 (开工号 text, 分支名 text, 状态 text, 释放时间 text, 工作树 text)")
        连接.execute("insert into 开工 values (?,?,?,?,?)",
            ("v1-100524", "腿/v1-100524", "已释放", "样本已验释放", str(替代工作树)))
    参数表 = {"期望提交": 期望提交, "替代提交": 替代提交, "替代开工": "v1-100524",
        "确认无独有成果": True, "授权件表": [{"路径": 路径,
            "期望指纹": 保全.算指纹值((主目录 / 路径).read_bytes())} for 路径 in 保全.授权路径]}
    return 主目录, 参数表, 库路径


def 样本拒绝(主目录, 参数表, 读数名):
    原字节表 = {路径: (主目录 / 路径).read_bytes() for 路径 in 保全.授权路径
        if (主目录 / 路径).is_file() and not (主目录 / 路径).is_symlink()}
    退出码, 说明 = 保全.保全操作(参数表, 主目录)
    assert 退出码 != 0, (读数名, 说明)
    assert all((主目录 / 路径).read_bytes() == 旧字节 for 路径, 旧字节 in 原字节表.items())
    print("通过：" + 读数名)


def 样本保护(夹具根):
    主目录, 参数表, 库路径 = 样本夹具(夹具根)
    索引字节 = (主目录 / ".git/index").read_bytes()
    原字节表 = {路径: (主目录 / 路径).read_bytes() for 路径 in 保全.授权路径}
    盘前指纹 = {str(路径): (路径.read_bytes(), 路径.stat().st_mtime_ns)
        for 路径 in 主目录.rglob("*") if 路径.is_file()}
    库前字节 = 库路径.read_bytes()
    备份目录, 清单字节 = 保全.保全落点(主目录, 参数表, 保全.核基本表(参数表))
    退出码, 说明 = 保全.保全操作(参数表, 主目录)
    assert 退出码 == 0, 说明
    assert not 备份目录.exists() and not (主目录 / ".git/合主干.lock").exists()
    assert (主目录 / ".git/index").read_bytes() == 索引字节
    assert 盘前指纹 == {str(路径): (路径.read_bytes(), 路径.stat().st_mtime_ns)
        for 路径 in 主目录.rglob("*") if 路径.is_file()}
    assert 库路径.read_bytes() == 库前字节
    print("通过：默认dry-run全仓文件字节/mtime/账本零写")
    后备参数 = copy.deepcopy(参数表)
    后备参数["授权件表"][0]["路径"] = ".zcode/agents/chat-zidaili.md"
    样本拒绝(主目录, 后备参数, "陌生路径拒绝")
    后备参数 = copy.deepcopy(参数表)
    后备参数["授权件表"][0]["期望指纹"] = "0" * 40
    样本拒绝(主目录, 后备参数, "指纹漂移拒绝")
    后备参数["授权件表"][0]["期望指纹"] = 参数表["授权件表"][0]["期望指纹"][:8]
    样本拒绝(主目录, 后备参数, "指纹前缀拒绝")
    后备参数 = copy.deepcopy(参数表)
    后备参数["替代提交"] = 参数表["期望提交"]
    样本拒绝(主目录, 后备参数, "替代提交不符拒绝")
    后备参数 = copy.deepcopy(参数表)
    后备参数["确认无独有成果"] = False
    样本拒绝(主目录, 后备参数, "缺明确成果确认拒绝")
    with sqlite3.connect(库路径) as 连接:
        连接.execute("update 开工 set 状态='进行中'")
    样本拒绝(主目录, 参数表, "未释放替代拒绝")
    with sqlite3.connect(库路径) as 连接:
        连接.execute("update 开工 set 状态='已释放'")
    件路径 = 主目录 / 保全.授权路径[0]
    件路径.unlink()
    件路径.mkdir()
    样本拒绝(主目录, 参数表, "目录拒绝")
    件路径.rmdir()
    件路径.symlink_to(主目录 / "README.md")
    样本拒绝(主目录, 参数表, "符号链接拒绝")
    件路径.unlink()
    件路径.write_bytes(原字节表[保全.授权路径[0]])
    (主目录 / ".gitignore").write_text(保全.授权路径[0] + "\n")
    样本拒绝(主目录, 参数表, "忽略路径拒绝")
    (主目录 / ".gitignore").unlink()
    保全.跑主仓(主目录, ["add", 保全.授权路径[0]])
    样本拒绝(主目录, 参数表, "tracked/index漂移拒绝")
    保全.跑主仓(主目录, ["reset", "--", 保全.授权路径[0]])
    索引字节 = (主目录 / ".git/index").read_bytes()
    参数表["执行"] = True
    with patch.object(保全, "核副本表", side_effect=保全.保全拒绝("样本副本复核失败")):
        样本拒绝(主目录, 参数表, "副本复核失败原件全批不动")
    for 路径 in 备份目录.iterdir():
        路径.unlink()
    备份目录.rmdir()
    原移开 = 保全.移开件
    移开次数 = [0]
    def 故障移开(件路径):
        移开次数[0] += 1
        if 移开次数[0] == 2:
            raise OSError("样本移开故障")
        原移开(件路径)
    with patch.object(保全, "移开件", 故障移开):
        退出码, 说明 = 保全.保全操作(参数表, 主目录)
    assert 退出码 != 0 and "样本移开故障" in 说明, 说明
    assert len(保全.核副本表(备份目录, 清单字节, 保全.核基本表(参数表))) == 3
    参数表["操作"] = "取回"
    件路径.write_bytes(b"new canonical")
    样本拒绝(主目录, 参数表, "取回新正本整批拒绝")
    件路径.unlink()
    with patch.object(保全.os, "link", side_effect=OSError("样本平台link拒绝")):
        样本拒绝(主目录, 参数表, "取回发布失败不留半正本/副本保留")
    assert not list(主目录.rglob(".v1取回-*"))
    退出码, 说明 = 保全.保全操作(参数表, 主目录)
    assert 退出码 == 0, 说明
    assert all((主目录 / 路径).read_bytes() == 旧字节 for 路径, 旧字节 in 原字节表.items())
    print("通过：中途故障副本全在，取回无损")
    for 路径 in 备份目录.iterdir():
        路径.unlink()
    备份目录.rmdir()
    参数表["操作"] = "保护"
    退出码, 说明 = 保全.保全操作(参数表, 主目录)
    assert 退出码 == 0, 说明
    assert all(not (主目录 / 路径).exists() for 路径 in 保全.授权路径)
    assert 备份目录.stat().st_mode & 0o777 == 0o700
    assert (主目录 / ".git/index").read_bytes() == 索引字节
    print("通过：三授权件保护成功/index未改")
    参数表["操作"] = "结清"
    参数表["合入提交"] = 参数表["替代提交"]
    样本拒绝(主目录, 参数表, "未同步禁止结清")
    保全.跑主仓(主目录, ["update-ref", "refs/heads/主干", 参数表["替代提交"], 参数表["期望提交"]])
    保全.跑主仓(主目录, ["read-tree", "-u", "-m", 参数表["期望提交"], 参数表["替代提交"]])
    件路径.write_bytes(b"drift")
    样本拒绝(主目录, 参数表, "正本盘上漂移禁止结清")
    旧字节 = 保全.跑主仓(主目录, ["cat-file", "blob", 参数表["替代提交"] + ":" + 保全.授权路径[0]]).stdout
    件路径.write_bytes(旧字节)
    退出码, 说明 = 保全.保全操作(参数表, 主目录)
    assert 退出码 == 0, 说明
    assert not 备份目录.exists()
    print("通过：正本盘上/index/合入提交全符后结清")


def 跑样本():
    try:
        with tempfile.TemporaryDirectory(prefix="v1三件保全样本-") as 临时目录:
            夹具根 = Path(临时目录)
            外仓 = 夹具根 / "外仓"
            外仓.mkdir()
            样本命令(外仓, ["init"])
            (外仓 / "外件").write_bytes(b"external")
            样本命令(外仓, ["add", "."])
            外仓索引 = (外仓 / ".git/index").read_bytes()
            with patch.dict(os.environ, {覆盖变量名: str(夹具根 / "运行根"),
                "GIT_DIR": str(外仓 / ".git"), "GIT_INDEX_FILE": str(外仓 / ".git/index"),
                "GIT_WORK_TREE": str(外仓)}):
                样本保护(夹具根)
            assert (外仓 / ".git/index").read_bytes() == 外仓索引
            print("通过：别仓GIT_DIR/GIT_INDEX_FILE零污染")
        return 0
    except (AssertionError, OSError) as 错误:
        print("保全样本失败：%r" % (错误,))
        return 1
