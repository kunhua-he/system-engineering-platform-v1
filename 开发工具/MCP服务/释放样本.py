# -*- coding: utf-8 -*-
"""释放行为样本：临时 Git 仓与账本，真实提交钩子，push 替身只记录调用。"""
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from . import 释放作业, 开工, 开工账本, 仓操作, 写盘账本


def 释放样本() -> list:
    """正反样本不访问真实远端，不碰真实开工账本。"""
    样本表 = []
    for 名称 in ("本地提交", "默认推送", "推送失败", "提交失败", "空改", "已提交", "建后删除",
                 "空改钩子失败", "门禁失败", "门禁瞬时超顶", "门禁真实超顶", "指纹漂移", "越界改动",
                 "强制释放", "跳过验证", "坏推送参数", "缺提交钩子", "钩子产生改动"):
        with tempfile.TemporaryDirectory(prefix="v1释放样本-") as 临时目录:
            _跑释放夹具(Path(临时目录), 名称)
        样本表.append((名称, True))
    样本表 += 单纯释放门禁样本()
    样本表 += 登记回滚样本()
    样本表 += 基线消费边样本()
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
    # 真账本由 v1_edit / 写盘恢复 懒建 `写盘意图` 表；夹具直写盘不走 v1_edit ⇒ 这里补上，与生产同形
    # （否则释放的越界检测调 `列写盘意图` 报 no such table）
    写盘账本.补意图表(连接)
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
        return 原跑命令(参数表, **关键字参数)

    def 假验证带跨阈(工作树, 跨阈回调=None):
        """替身：验证已搬进 `仓操作.跑验证带跨阈`（真起子进程）；本夹具只考**释放编排**
        （前置 / 提交 / 推 / 翻状态），故按档位返回读数 —— 真子进程路另由 `验证超阈样本` 覆盖。"""
        if 名称 == "门禁失败":
            return 1, "✗ 判据红：夹具样例", False
        if 名称 in ("门禁瞬时超顶", "门禁真实超顶"):
            闸0计数[0] = 2          # 瞬时超顶 ⇒ 自动复跑一次（共两次）
            if 名称 == "门禁真实超顶":
                return 1, "✗ 超顶：完整墙钟 4816 ms > 4800 ms —— 五秒硬顶无例外（裁决 §一）", True
            return 0, "✓ 夹具门禁通过", True
        return 0, "✓ 夹具门禁通过", False

    with mock.patch.object(开工账本, "连账本", 连样本账本), \
            mock.patch.object(释放作业, "跑命令", 观测命令), \
            mock.patch.object(仓操作, "跑命令", 观测命令), \
            mock.patch.object(释放作业, "跑验证带跨阈", 假验证带跨阈):
        if 名称 in ("强制释放", "坏推送参数"):
            # 强制 / 坏参数两档走**前台**入口（不起后台作业 —— 它们在便宜前置就出结论）。
            退出码, 输出文本 = 开工.派发(
                {"功能": 3, "开工ID": 开工号, "强制": 名称 == "强制释放",
                 "推送": "false" if 名称 == "坏推送参数" else False}, 仓根)
        else:
            退出码, 输出文本 = 释放作业.释放主体(
                仓根, 开工号, 跳过验证=名称 == "跳过验证", 推送=名称 in ("默认推送", "推送失败"))
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


def 搭腿夹具(临时根, 开工号="v1-900001"):
    """搭一条「已合主干 + 净树」的真腿：临时真仓 + 真工作树 + 临时账本 ⇒ `(仓根, 工作树, 账本件)`。

    主干 `--ff-only` 合入腿支线 ⇒ `仓操作.检查清树安全`（真跑）判「已合主干且净树」为真。
    """
    from .合主干有界跑 import 干净环境
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


def 单纯释放门禁样本() -> list:
    """`单纯释放`（功能 4）物理删除前门禁的**真夹具**样本（临时真仓 + 临时账本，跑完删净）。

    真读账本（`消费者行`）与真读台账（`未完成.json`）· 真跑 `检查清树安全`；只把 `非终态作业`
    （会读真作业账本）与 `未蒸馏反馈行`（反馈包未合入）按档替身。
    两档：拒删（保留树与支线并定位）· 放行（清树 + 状态已释放）· 幂等。
    """
    from . import 清树门禁
    样本表 = []
    for 档名 in ("未释放消费者拒", "非终态作业拒", "工作树脏拒", "台账点名拒", "未蒸馏反馈拒",
              "放行清树", "幂等再放行"):
        with tempfile.TemporaryDirectory(prefix="v1清树门禁-") as 临时目录:
            临时根 = Path(临时目录)
            仓根, 工作树, 账本件 = 搭腿夹具(临时根)
            开工号 = "v1-900001"

            def 开账():
                新连接 = sqlite3.connect(str(账本件))
                新连接.row_factory = sqlite3.Row
                return 新连接

            真连, 真清工作树 = 开工账本.连账本, 开工.清工作树
            真非终态, 真反馈 = 清树门禁.非终态作业, 清树门禁.未蒸馏反馈行
            清树记录 = []

            def 假清树(仓根, 开工号):
                from .合主干有界跑 import 干净环境
                做了 = False
                if 工作树.is_dir():
                    subprocess.run(["git", "worktree", "remove", str(工作树)], cwd=str(仓根),
                                   capture_output=True, text=True, timeout=5, env=干净环境())
                    做了 = True
                支线 = subprocess.run(["git", "branch", "--list", "腿/" + 开工号], cwd=str(仓根),
                                   capture_output=True, text=True, timeout=5,
                                   env=干净环境()).stdout.strip()
                if 支线:
                    subprocess.run(["git", "branch", "-D", "腿/" + 开工号], cwd=str(仓根),
                                   capture_output=True, text=True, timeout=5, env=干净环境())
                    做了 = True
                if 做了:
                    清树记录.append(开工号)
                return 0, ("夹具清树" if 做了 else "无物可清")

            开工账本.连账本 = 开账
            开工.清工作树 = 假清树
            清树门禁.非终态作业 = lambda 开工号, 工作树: []
            清树门禁.未蒸馏反馈行 = lambda 连接, 仓根, 开工号: []
            try:
                连接 = 开账()
                if 档名 == "未释放消费者拒":
                    开工账本.登记开工(连接, "v1-900009", "消费腿", "腿/v1-900009", str(工作树))
                    连接.execute("update 开工 set 父开工号 = ? where 开工号 = ?", (开工号, "v1-900009"))
                    连接.commit()
                if 档名 == "非终态作业拒":
                    清树门禁.非终态作业 = lambda 开工号, 工作树: ["任务X · 运行中"]
                if 档名 == "工作树脏拒":
                    (工作树 / "脏件.txt").write_text("未跟踪成果\n", encoding="utf-8")
                if 档名 == "台账点名拒":
                    台账件 = 仓根 / "开发工具" / "信息核心" / "未完成.json"
                    台账件.parent.mkdir(parents=True, exist_ok=True)
                    台账件.write_text('{"行": [[311, "点名 %s"]]}\n' % 开工号, encoding="utf-8")
                if 档名 == "未蒸馏反馈拒":
                    清树门禁.未蒸馏反馈行 = lambda 连接, 仓根, 开工号: ["反馈X：未判词"]
                连接.close()
                退出码, 输出文本 = 开工.单纯释放(仓根, 开工号)
                连接 = 开账()
                状态 = 开工账本.读开工(连接, 开工号)["状态"]
                连接.close()
                if 档名.endswith("拒"):
                    样本表.append(("单纯释放拒·%s：退出码 %d（期望 1）· 保留（状态 %s · 未清树 %s · 说拒 %s）"
                            % (档名, 退出码, 状态, "是" if not 清树记录 else "否",
                               "是" if "拒" in 输出文本 else "否"),
                            退出码 == 1 and 状态 == 开工账本.状态_已释放 and not 清树记录
                            and "拒" in 输出文本))
                elif 档名 == "放行清树":
                    样本表.append(("单纯释放放行：退出码 %d（期望 0）· 已清树 %s · 状态 %s"
                            % (退出码, "是" if 清树记录 == [开工号] else "否", 状态),
                            退出码 == 0 and 清树记录 == [开工号] and 状态 == 开工账本.状态_已释放))
                else:
                    首次码, _ = 开工.单纯释放(仓根, 开工号)
                    再跑码, 文本二 = 开工.单纯释放(仓根, 开工号)
                    样本表.append(("单纯释放幂等：首次 %d · 再跑 %d（期望均 0）· 只清树一次 %s · 状态 %s"
                            % (首次码, 再跑码, "是" if 清树记录 == [开工号] else "否", 状态),
                            首次码 == 0 and 再跑码 == 0 and 清树记录 == [开工号]
                            and 状态 == 开工账本.状态_已释放))
            finally:
                开工账本.连账本 = 真连
                开工.清工作树 = 真清工作树
                清树门禁.非终态作业, 清树门禁.未蒸馏反馈行 = 真非终态, 真反馈
    return 样本表


def 登记回滚样本() -> list:
    """`清树门禁.回滚登记` 真夹具：无成果无消费者 ⇒ 清；有其一 ⇒ 保留；幂等。"""
    from . import 清树门禁
    样本表 = []
    for 档名 in ("无成果无消费者清", "有未提交成果保留", "有消费者保留", "幂等"):
        with tempfile.TemporaryDirectory(prefix="v1回滚登记-") as 临时目录:
            临时根 = Path(临时目录)
            仓根, 工作树, 账本件 = 搭腿夹具(临时根)
            开工号 = "v1-900001"

            def 开账():
                新连接 = sqlite3.connect(str(账本件))
                新连接.row_factory = sqlite3.Row
                return 新连接

            真连, 真清工作树 = 开工账本.连账本, 清树门禁.清工作树
            清树记录 = []

            def 假清树(仓根, 开工号):
                清树记录.append(开工号)
                return 0, "夹具清树"

            开工账本.连账本 = 开账
            清树门禁.清工作树 = 假清树
            try:
                连接 = 开账()
                开工账本.认领文件(连接, 开工号, {"件.txt": "指纹占位"})
                if 档名 == "有未提交成果保留":
                    (工作树 / "未提交.txt").write_text("成果\n", encoding="utf-8")
                if 档名 == "有消费者保留":
                    开工账本.登记开工(连接, "v1-900009", "消费腿", "腿/v1-900009", str(工作树))
                    连接.execute("update 开工 set 父开工号 = ? where 开工号 = ?", (开工号, "v1-900009"))
                    连接.commit()
                连接.close()
                说明 = 清树门禁.回滚登记(仓根, 开账(), 开工号)
                连接 = 开账()
                行在 = 开工账本.读开工(连接, 开工号) is not None
                认领数 = len(开工账本.读认领(连接, 开工号))
                连接.close()
                if 档名 == "无成果无消费者清":
                    样本表.append(("回滚·无成果无消费者 ⇒ 清（行删 %s · 认领删 %s · 清树 %s）"
                            % ("是" if not 行在 else "否", "是" if 认领数 == 0 else "否",
                               "是" if 清树记录 == [开工号] else "否"),
                            not 行在 and 认领数 == 0 and 清树记录 == [开工号]))
                elif 档名 == "幂等":
                    再说明 = 清树门禁.回滚登记(仓根, 开账(), 开工号)
                    样本表.append(("回滚幂等：首次清 %s · 再跑回空串 %s · 只清树一次 %s"
                            % ("是" if 说明 else "否", "是" if 再说明 == "" else "否",
                               "是" if 清树记录 == [开工号] else "否"),
                            bool(说明) and 再说明 == "" and 清树记录 == [开工号]))
                else:
                    样本表.append(("回滚·%s ⇒ 保留（行在 %s · 未清树 %s · 说保留 %s）"
                            % (档名, "是" if 行在 else "否", "是" if not 清树记录 else "否",
                               "是" if "保留" in 说明 else "否"),
                            行在 and not 清树记录 and "保留" in 说明))
            finally:
                开工账本.连账本 = 真连
                清树门禁.清工作树 = 真清工作树
    return 样本表


def 基线消费边样本() -> list:
    """基线消费边：`基线腿号` 解析 + 消费者标注分类（登记落库与清树门禁共用一份）。"""
    from .基线并入 import 基线腿号
    from . import 清树门禁
    return [
        ("基线腿号·腿支线 ⇒ 开工号", 基线腿号("腿/v1-100615") == "v1-100615"),
        ("基线腿号·origin 腿 ⇒ 开工号", 基线腿号("origin/腿/v1-900001") == "v1-900001"),
        ("基线腿号·主干与提交 ⇒ 空串", 基线腿号("主干") == "" and 基线腿号("a" * 40) == ""),
        ("消费者标注·接管 ⇒ 继承者", "继承者" in 清树门禁.消费者标注(
            {"开工号": "v1-900002", "状态": "进行中", "开工种类": 开工账本.种类_接管})),
        ("消费者标注·原腿有父 ⇒ 基线消费者", "基线消费者" in 清树门禁.消费者标注(
            {"开工号": "v1-900003", "状态": "已释放", "开工种类": 开工账本.种类_原腿})),
    ]
