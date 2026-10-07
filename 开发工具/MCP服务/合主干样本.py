# -*- coding: utf-8 -*-
"""合并恢复验收：临时 bare 仓、真实 Git/超时/锁，不触及项目主干。"""
import fcntl as 文件锁
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock
from . import 合主干编排 as 编排, 合主干集成树 as 集成
from .合主干有界跑 import 跑有界命令


def 跑样本仓命令(仓根, *参数表):
    回执 = subprocess.run(["git", *参数表], cwd=仓根, capture_output=True, text=True,
                         env=编排.干净环境(), timeout=5)
    assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
    return 回执.stdout.strip()


def _建夹具(临时根, 名称):
    仓根, 腿树 = 临时根 / "主目录", 临时根 / "腿目录"
    仓根.mkdir()
    for 参数表 in (("init", "-b", "主干"), ("config", "user.name", "样本"), ("config", "user.email", "fixture@example.invalid")):
        跑样本仓命令(仓根, *参数表)
    (仓根 / "README.md").write_text("系统工程平台 V1\n")
    (仓根 / "AGENTS.md").write_text("样本\n")
    (仓根 / "样本.txt").write_text("基线\n")
    门禁件 = 仓根 / "构建装配/一键验证/闸0.py"
    门禁件.parent.mkdir(parents=True)
    门禁件.write_text("print('腿闸通过')\n")
    库件 = 仓根 / 编排.库相对路径
    库件.parent.mkdir(parents=True)
    with sqlite3.connect(库件) as 连接:
        连接.execute("create table 规则 (编号 integer primary key, 类 text, 名 text, 内容 text, 依据 text)")
        连接.execute("insert into 规则 values (1,'样本','语义','基值','')")
    跑样本仓命令(仓根, "add", ".")
    跑样本仓命令(仓根, "commit", "-m", "基线")
    跑样本仓命令(仓根, "worktree", "add", "-b", "腿/v1-999001", str(腿树))
    (腿树 / "新增.txt").write_text("腿成果\n")
    if 名称 == "代码冲突":
        (仓根 / "样本.txt").write_text("主改\n")
        (腿树 / "样本.txt").write_text("腿改\n")
    if 名称 == "源库异义":
        for 树根, 规则正文 in ((仓根, "主干值"), (腿树, "腿值")):
            with sqlite3.connect(树根 / 编排.库相对路径) as 连接:
                连接.execute("update 规则 set 内容=?", (规则正文,))
    if 名称 in ("代码冲突", "源库异义"):
        跑样本仓命令(仓根, "add", ".")
        跑样本仓命令(仓根, "commit", "-m", "主改")
    if 名称 == "重放失败":
        with sqlite3.connect(腿树 / 编排.库相对路径) as 连接:
            连接.execute("update 规则 set 内容='重放值'")
        (腿树 / "开发工具/信息核心/信息核心.py").write_text("import sys\nsys.stderr.write('ORIGINAL-REPLAY-FIRST\\n'+'z'*20000+'REPLAY-LAST')\nraise SystemExit(29)\n")
    if 名称 == "导库失败":
        (腿树 / 编排.库相对路径).unlink()
    跑样本仓命令(腿树, "add", ".")
    跑样本仓命令(腿树, "commit", "-m", "腿成果")
    钩子 = 仓根 / ".git/hooks/pre-commit"
    钩子.write_text("#!/bin/sh\nexit 0\n")
    钩子.chmod(0o755)
    if 名称 == "验证失败":
        钩子.write_text("#!/bin/sh\nprintf 'ORIGINAL-IMPORT-FIRST\\nModuleNotFoundError: 原始环境错误\\n' >&2\nexit 23\n")
    if 名称 == "超时":
        钩子.unlink()
        门禁件.write_text("import os,time\nprint('真实超时首因',flush=True)\nif 'v1集成-' in os.getcwd():time.sleep(10)\n")
        跑样本仓命令(仓根, "add", ".")
        跑样本仓命令(仓根, "commit", "-m", "超时验证")
    if 名称 == "同步保护":
        (仓根 / "样本.txt").write_text("未知用户成果")
    跑样本仓命令(仓根, "config", "core.bare", "true")
    return 仓根.resolve(), 腿树, 钩子


def 跑样本():
    起始时刻 = time.monotonic()
    for 名称 in ("成功", "代码冲突", "源库异义", "验证失败", "超时", "重放失败", "导库失败", "同步保护"):
        with tempfile.TemporaryDirectory(prefix="v1合并样本-") as 临时目录:
            仓根, 腿树, 钩子 = _建夹具(Path(临时目录), 名称)
            开工记录 = {"状态":"已释放", "工作树":str(腿树), "分支名":"腿/v1-999001"}
            旧主干 = 跑样本仓命令(仓根, "rev-parse", "主干")
            with mock.patch.object(编排, "_读开工记录", return_value=开工记录):
                退出码, 报告文本 = 编排.派发("v1-999001", False, 腿树)
                assert "主仓目标 " + str(仓根) in 报告文本, 报告文本
                if 名称 == "成功":
                    assert 退出码 == 0 and 集成.找集成树(仓根, "v1-999001") is None, 报告文本
                    assert (仓根 / "新增.txt").read_text() == "腿成果\n" and "实际工作文件" in 报告文本
                else:
                    assert 退出码 != 0 and 集成.找集成树(仓根, "v1-999001"), 报告文本
                    assert 跑样本仓命令(仓根, "rev-parse", "主干") == 旧主干
                    assert "失败现场保留" in 报告文本
                    assert "原完整报告" in 编排.派发("v1-999001",False,仓根,操作="查看现场")[1]
                    assert 编排.派发("v1-999001",False,仓根,操作="清理现场")[0] != 0
                    assert 编排.派发("v1-999001",False,仓根)[0] != 0
                    assert 跑样本仓命令(仓根,"worktree","list","--porcelain").count("branch refs/heads/集成/v1-999001") == 1
                    if 名称 == "验证失败":
                        assert "③ 集成验证" in 报告文本 and "退出码 23" in 报告文本 and "ORIGINAL-IMPORT-FIRST" in 报告文本
                        钩子.write_text("#!/bin/sh\nexit 0\n")
                        恢复码, 恢复报告 = 编排.派发("v1-999001",False,仓根,操作="恢复现场")
                        assert 恢复码 == 0 and 集成.找集成树(仓根,"v1-999001") is None, 恢复报告
                    if 名称 == "超时":
                        assert "③ 集成验证" in 报告文本 and "退出码 -1" in 报告文本 and "是否超时 True" in 报告文本 and "真实超时首因" in 报告文本
                    if 名称 == "重放失败":
                        assert "退出码 29" in 报告文本 and "ORIGINAL-REPLAY-FIRST" in 报告文本
                    if 名称 == "代码冲突":
                        assert "CONFLICT" in 报告文本
                    if 名称 == "源库异义":
                        assert all(规则正文 in 报告文本 for 规则正文 in ("主干值", "腿值", "基值"))
                if 名称 == "成功":
                    (腿树 / "续作.txt").write_text("恢复同步成果")
                    跑样本仓命令(腿树,"add","续作.txt")
                    跑样本仓命令(腿树,"commit","-m","续作成果")
                    with mock.patch.object(集成,"同步主工作区",return_value=(31,"原始同步失败替身")):
                        同步失败码,同步失败报告=编排.派发("v1-999001",False,仓根)
                        assert 同步失败码!=0 and "⑤ 同步主目录" in 同步失败报告 and "原始同步失败替身" in 同步失败报告
                    恢复码,恢复报告=编排.派发("v1-999001",False,仓根,操作="恢复现场")
                    assert 恢复码==0 and (仓根/"续作.txt").read_text()=="恢复同步成果",恢复报告
                    assert 集成.找集成树(仓根,"v1-999001") is None
                print("通过", 名称, "编排退出码", 退出码)
                已有树 = 集成.找集成树(仓根, "v1-999001")
                if 已有树:
                    跑样本仓命令(仓根, "worktree", "remove", "--force", str(已有树))
    with tempfile.TemporaryDirectory(prefix="v1定位样本-") as 临时目录:
        _验定位同步锁(Path(临时目录))
    退出码, 输出文本, 日志路径 = 跑有界命令([sys.executable,"-c","import sys;print('OUT-FIRST');sys.stderr.write('ERR-FIRST\\n'+'z'*9000000+'ERR-LAST');print('OUT-LAST')"],tempfile.gettempdir(),超时秒数=5)
    全文 = Path(日志路径).read_text()
    assert 退出码 == 0 and "ERR-FIRST" in 输出文本 and "ERR-LAST" in 全文 and "OUT-LAST" in 全文 and len(全文)>9000000
    退出码, _, 日志路径 = 跑有界命令(["/不存在的样本命令"],tempfile.gettempdir(),超时秒数=5)
    assert 退出码 == -2 and "退出码 -2" in Path(日志路径).read_text()
    print("通过 全文日志与启动失败；总墙钟 %.3f 秒（time.monotonic）" % (time.monotonic()-起始时刻))
    return 0


def _验定位同步锁(临时根):
    仓根, 腿树, _ = _建夹具(临时根,"成功")
    assert 集成.定位主仓(腿树) == (0,仓根) and 集成.定位主仓(仓根) == (0,仓根)
    assert 集成.定位主仓(仓根/".git")[0] != 0 and 集成.定位主仓(临时根)[0] != 0
    assert 集成.同步主工作区(腿树)[0] != 0
    (仓根/"用户未知.txt").write_text("保留")
    assert 集成.同步主工作区(仓根)[0] == 0 and (仓根/"用户未知.txt").read_text()=="保留"
    命令头=("--git-dir",str(仓根/".git"),"--work-tree",str(仓根))
    for 标记 in ("--skip-worktree","--assume-unchanged"):
        跑样本仓命令(仓根,*命令头,"update-index",标记,"样本.txt")
        (仓根/"样本.txt").write_text("不可覆盖成果")
        assert 集成.同步主工作区(仓根)[0] != 0 and (仓根/"样本.txt").read_text()=="不可覆盖成果"
        (仓根/"样本.txt").write_text("基线\n")
        跑样本仓命令(仓根,*命令头,"update-index","--no-"+标记[2:],"样本.txt")
    (仓根/"样本.txt").write_text("暂存用户成果")
    跑样本仓命令(仓根,*命令头,"add","样本.txt")
    (仓根/"样本.txt").write_text("基线\n")
    assert 集成.同步主工作区(仓根)[0] != 0
    跑样本仓命令(仓根,*命令头,"restore","--staged","样本.txt")
    (仓根/"新增.txt").write_text("未知未跟踪碰撞")
    旧主干=跑样本仓命令(仓根,"rev-parse","主干")
    新提交=跑样本仓命令(腿树,"rev-parse","HEAD")
    跑样本仓命令(仓根,"update-ref","refs/heads/主干",新提交,旧主干)
    assert 集成.同步主工作区(仓根,旧主干)[0] != 0
    assert (仓根/"新增.txt").read_text()=="未知未跟踪碰撞"
    跑样本仓命令(仓根,"update-ref","refs/heads/主干",旧主干,新提交)
    (仓根/"新增.txt").unlink()
    (仓根/"README.md").write_text("其他项目")
    assert 集成.定位主仓(腿树)[0] != 0
    (仓根/"README.md").write_text("系统工程平台 V1\n")
    模块根=Path(__file__).resolve().parents[2]
    for 树根 in (仓根,腿树):
        for 相对路径 in ("开发工具/MCP服务/合并主干.py","开发工具/MCP服务/合主干编排.py","开发工具/MCP服务/合主干集成树.py","开发工具/MCP服务/合主干有界跑.py","开发工具/MCP服务/合主干源库重放.py","开发工具/信息核心/表定义.py"):
            件路径=树根/相对路径
            件路径.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(模块根/相对路径,件路径)
        (树根/"构建装配/门禁").mkdir(parents=True,exist_ok=True)
        (树根/"构建装配/门禁/__init__.py").write_text("def 报告环境步(起始时刻,退出码,说明):return 退出码\n")
        回执=subprocess.run([sys.executable,str(树根/"开发工具/MCP服务/合并主干.py"),"v1-999001","--查看现场"],cwd=临时根,capture_output=True,text=True,env={键名:值 for 键名,值 in os.environ.items() if 键名!="PYTHONPATH"},timeout=5)
        assert 回执.returncode==1 and "主仓 "+str(仓根) in 回执.stdout,(回执.stdout,回执.stderr)
    with open(仓根/".git/合主干.lock","a+") as 文件句柄:
        文件锁.flock(文件句柄,文件锁.LOCK_EX|文件锁.LOCK_NB)
        脚本="import sys;sys.path.insert(0,%r);from 开发工具.MCP服务.合主干编排 import 派发;print(派发('v1-999001',False,%r))"%(str(模块根),str(仓根))
        起始时刻=time.monotonic()
        回执=subprocess.run([sys.executable,"-c",脚本],capture_output=True,text=True,timeout=5)
        assert "主仓合并忙" in 回执.stdout and time.monotonic()-起始时刻<5
        不同根=临时根/"不同仓"
        不同根.mkdir()
        别仓,_,_=_建夹具(不同根,"成功")
        with mock.patch.object(编排,"_读开工记录",side_effect=RuntimeError("原始异常")):
            for 重试次数 in range(2):
                退出码,报告文本=编排.派发("v1-999001",False,别仓)
                assert 退出码!=0 and "原始异常" in 报告文本 and "主仓合并忙" not in 报告文本
    assert "主仓合并忙" not in 编排.派发("v1-999001",False,仓根,操作="查看现场")[1]
    print("通过 定位/CLI双路/同步保护/跨进程忙拒/不同仓/异常释放")
