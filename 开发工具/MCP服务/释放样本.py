# -*- coding: utf-8 -*-
"""释放行为样本：临时 Git 仓与账本，真实提交钩子，push 替身只记录调用。"""
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from . import 开工, 开工账本, 仓操作


def 释放样本() -> list:
    """正反样本不访问真实远端，不碰真实开工账本。"""
    样本表 = []
    for 名称 in ("本地提交", "默认推送", "推送失败", "提交失败", "空改", "已提交", "建后删除",
                 "空改钩子失败", "门禁失败", "门禁瞬时超顶", "门禁真实超顶", "指纹漂移", "越界改动",
                 "强制释放", "跳过验证", "坏推送参数", "缺提交钩子", "钩子产生改动"):
        with tempfile.TemporaryDirectory(prefix="v1释放样本-") as 临时目录:
            _跑释放夹具(Path(临时目录), 名称)
        样本表.append((名称, True))
    return 样本表


def _跑释放夹具(临时根, 名称):
    仓根 = 临时根 / "主工作树"
    工作树 = 临时根 / "工作树"
    仓根.mkdir()
    开工号 = "v1-样本"
    原跑命令 = 仓操作.跑命令
    命令表 = []
    闸0计数 = [0]        # 「门禁瞬时超顶 / 真实超顶」两样本用：数闸 0 被跑了几次

    def 执行命令(参数表, cwd=仓根, **关键字参数):
        退出码, 输出文本 = 原跑命令(参数表, cwd=cwd, **关键字参数)
        assert 退出码 == 0, (参数表, 退出码, 输出文本)
        return 输出文本.strip()

    执行命令(["git", "init", "-b", "主干"])
    执行命令(["git", "config", "user.name", "释放样本"])
    执行命令(["git", "config", "user.email", "release@example.invalid"])
    执行命令(["git", "config", "core.quotePath", "false"])
    (仓根 / "样本.txt").write_text("旧内容\n", encoding="utf-8")
    件路径 = 仓根 / "构建装配/一键验证/闸0.py"
    件路径.parent.mkdir(parents=True)
    件路径.write_text("print('夹具门禁通过')\n", encoding="utf-8")
    执行命令(["git", "add", "--", "样本.txt", "构建装配/一键验证/闸0.py"])
    执行命令(["git", "commit", "-m", "夹具基线"])
    执行命令(["git", "worktree", "add", "-b", 仓操作.分支名(开工号), str(工作树)])
    文件条目 = 仓根 / ".git/hooks/pre-commit"
    文件条目.write_text("#!/bin/sh\nprintf '闸0 自测 案例\\n' >> \"$(git rev-parse --git-common-dir)/门禁读数\"\nexit 0\n", encoding="utf-8")
    文件条目.chmod(0o755)
    账本路径 = 临时根 / "账本.db"

    def 连样本账本():
        连接 = sqlite3.connect(账本路径)
        连接.row_factory = sqlite3.Row
        return 连接

    连接 = 连样本账本()
    for 建表行 in 开工账本.建表语句:
        连接.execute(建表行)
    开工账本.登记开工(连接, 开工号, "释放样本", 仓操作.分支名(开工号), str(工作树))
    if 名称 not in ("空改", "空改钩子失败", "坏推送参数"):
        (工作树 / "样本.txt").write_text("新内容\n", encoding="utf-8")
        指纹 = 仓操作.文件指纹(str(工作树 / "样本.txt"))
        开工账本.认领文件(连接, 开工号, {"样本.txt": 指纹})
        开工账本.记改动(连接, 开工号, "样本.txt", "修改", "", 指纹)
    if 名称 == "已提交":
        执行命令(["git", "add", "--", "样本.txt"], cwd=工作树)
        执行命令(["git", "commit", "-m", "已完成本地提交"], cwd=工作树)
    if 名称 == "建后删除":
        执行命令(["git", "restore", "样本.txt"], cwd=工作树)
        连接.execute("delete from 认领")
        连接.execute("delete from 改动")
        连接.commit()
        开工账本.记改动(连接, 开工号, "消失.txt", "新建", "", "")
        开工账本.记改动(连接, 开工号, "消失.txt", "删除", "", "")
    if 名称 in ("提交失败", "空改钩子失败"):
        文件条目.write_text("#!/bin/sh\nexit 23\n", encoding="utf-8")
    if 名称 == "缺提交钩子":
        文件条目.unlink()
    if 名称 == "钩子产生改动":
        文件条目.write_text("#!/bin/sh\nprintf '副产物' > 钩子产物.txt\nexit 0\n", encoding="utf-8")
    if 名称 == "门禁失败":
        件路径 = 工作树 / "构建装配/一键验证/闸0.py"
        件路径.write_text("raise SystemExit(19)\n", encoding="utf-8")
        指纹 = 仓操作.文件指纹(str(件路径))
        开工账本.认领文件(连接, 开工号, {"构建装配/一键验证/闸0.py": 指纹})
        开工账本.记改动(连接, 开工号, "构建装配/一键验证/闸0.py", "修改", "", 指纹)
    if 名称 == "指纹漂移":
        (工作树 / "样本.txt").write_text("绕过写盘\n", encoding="utf-8")
    if 名称 == "越界改动":
        (工作树 / "越界.txt").write_text("未认领\n", encoding="utf-8")
    连接.close()
    提交哈希 = 执行命令(["git", "rev-parse", "HEAD"], cwd=工作树)

    def 观测命令(参数表, **关键字参数):
        命令表.append(参数表)
        if 参数表[:2] == ["git", "push"]:
            return (31, "夹具拒绝push") if 名称 == "推送失败" else (0, "夹具push成功")
        if 名称 in ("门禁瞬时超顶", "门禁真实超顶") and "闸0.py" in str(参数表):
            闸0计数[0] += 1
            if 名称 == "门禁真实超顶" or 闸0计数[0] == 1:
                return 1, "✗ 超顶：完整墙钟 4816 ms > 4800 ms —— 五秒硬顶无例外（裁决 §一）"
        return 原跑命令(参数表, **关键字参数)

    参数表 = {"功能": 7 if 名称 == "跳过验证" else 3, "开工ID": 开工号}
    if 名称 not in ("默认推送", "推送失败"):
        参数表["推送"] = False
    if 名称 == "坏推送参数":
        参数表["推送"] = "false"
    参数表["强制"] = 名称 == "强制释放"
    with mock.patch.object(开工账本, "连账本", 连样本账本), mock.patch.object(开工, "跑命令", 观测命令), \
            mock.patch.object(仓操作, "跑命令", 观测命令):
        退出码, 输出文本 = 开工.派发(参数表, 仓根)
        连接 = 连样本账本()
        状态 = 开工账本.读开工(连接, 开工号)["状态"]
        连接.close()
        失败表 = ("提交失败", "空改钩子失败", "门禁失败", "门禁真实超顶", "指纹漂移", "越界改动", "推送失败", "坏推送参数", "缺提交钩子", "钩子产生改动")
        assert 退出码 == (2 if 名称 == "坏推送参数" else 1 if 名称 in 失败表 else 0), (名称, 退出码, 输出文本)
        assert 状态 == (开工账本.状态_进行中 if 名称 in 失败表 else 开工账本.状态_待合并 if 名称 == "默认推送" else 开工账本.状态_已释放), (名称, 状态)
        assert sum(命令[:2] == ["git", "push"] for 命令 in 命令表) == (1 if 名称 in ("默认推送", "推送失败") else 0)
        if 名称 in ("门禁瞬时超顶", "门禁真实超顶"):
            assert 闸0计数[0] == 2, (名称, 闸0计数[0])   # 第一次瞬时超顶 ⇒ 自动复跑一次（共两次）
        if 名称 == "门禁真实超顶":
            assert "负载红" in 输出文本 and "功能 = 7" in 输出文本, 输出文本
        if 名称 == "门禁瞬时超顶":
            assert "负载红" not in 输出文本, 输出文本   # 复跑后绿 ⇒ 不该报负载红
        if 名称 in ("空改", "已提交", "建后删除", "强制释放") or 名称 in 失败表 and 名称 not in ("推送失败", "钩子产生改动"):
            assert 执行命令(["git", "rev-parse", "HEAD"], cwd=工作树) == 提交哈希
        if 名称 in ("本地提交", "跳过验证"):
            assert "明确跳过远端推送" in 输出文本 and "本地提交成功" in 输出文本
            assert (仓根 / ".git/门禁读数").read_text().strip() == "闸0 自测 案例"
            assert 执行命令(["git", "status", "--porcelain"], cwd=工作树) == ""
            assert 开工.单纯释放(仓根, 开工号)[0] == 1
            (工作树 / "脏件.txt").write_text("保留\n", encoding="utf-8")
            assert "未提交" in 开工.单纯释放(仓根, 开工号)[1]
            (工作树 / "脏件.txt").unlink()
            执行命令(["git", "merge", "--ff-only", 仓操作.分支名(开工号)])
            assert 仓操作.检查清树安全(仓根, 开工号, 工作树)[0] == 0
            执行命令(["git", "worktree", "remove", str(工作树)])
            执行命令(["git", "branch", "-d", 仓操作.分支名(开工号)])
            assert 开工.单纯释放(仓根, 开工号)[0] == 0
        if 名称 in ("空改", "已提交", "建后删除"):
            assert "未创建空提交" in 输出文本
            assert (仓根 / ".git/门禁读数").read_text().strip()
