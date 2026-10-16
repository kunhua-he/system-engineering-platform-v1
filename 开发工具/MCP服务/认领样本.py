# -*- coding: utf-8 -*-
"""独立工作树认领与本地三方合并的临时 Git 反向样本。

`MCP服务.py --长样本` 调本件的 `长样本` —— 它跑 7 个重事务场景（临时仓 + 临时账本，
跑完即删，仓一个字节都不改）。短自检 `--自检` **不跑它**：它 1.7–2.8 s，装不进 5 秒硬顶。
"""
from pathlib import Path

场景表 = (
    "独立树功能1自动认领 + 各自 v1_edit 提交 + 三方合并保留两函数（短回执与二进制重放提示）",
    "事务失败无部分认领：漂移拒写、拒洗账，旁件可继续",
    "同树 / 别名 / 公共源落点 / 非本仓拒绝；确认重叠不绕隔离硬闸",
    "bare 仓根（core.bare=true）下树身份仍核验成立；外仓仍拒",
    "同片段三方合并报告冲突，标记保留双方且两支提交仍在",
    "父子片段三方合并报告冲突，标记保留双方且两支提交仍在",
    "强制相同旧快照的并发认领：独立树两者成功，同树只有一个成功",
)


def 认领样本(仓根=None, 工具表=None, 输出表=None):
    import sqlite3
    import tempfile
    from unittest.mock import patch
    from . import 开工, 开工账本, 修改, 认领隔离, 命名闸, 登记编排, 清树门禁
    from .仓操作 import 跑命令

    if 输出表 is None:
        输出表 = []
    with tempfile.TemporaryDirectory(prefix="v1认领隔离-") as 临时目录:
        临时根 = Path(临时目录)
        仓根 = 临时根 / "仓库"
        仓根.mkdir()
        _跑Git(仓根, "init", "-b", "主线")
        _跑Git(仓根, "config", "user.name", "本地样本")
        _跑Git(仓根, "config", "user.email", "local@example.invalid")
        内容值 = "def 前段函数():\n    return 1\n\n\n\n\n\ndef 后段函数():\n    return 2\n"
        (仓根 / "样例.py").write_text(内容值, encoding="utf-8")
        (仓根 / "规则.db").write_bytes(b"binary-source")
        _跑Git(仓根, "add", "样例.py", "规则.db")
        _跑Git(仓根, "commit", "-m", "样本基线")
        基线提交 = _跑Git(仓根, "rev-parse", "HEAD").strip()
        # 前置硬闸（541 缺陷的永久反向样本）：夹具 git 只能落在夹具那棵树，注入 Git 重定向也不许
        # 污染别的仓 —— 谁把重定向键放回 `仓操作.跑命令`，本样本当场红，长样本退出码非 0。
        断言夹具自洽(仓根)
        输出表.append(("夹具 git 隔离：注入 GIT_DIR 后搭夹具跑 git，别仓索引零污染（541 反向样本）", True))
        账本路径 = 临时根 / "账本.db"

        def 开账():
            连接 = sqlite3.connect(str(账本路径))
            连接.row_factory = sqlite3.Row
            for 建表行 in 开工账本.建表语句:
                连接.execute(建表行)
            连接.commit()
            return 连接

        def 路径命令(命令表, cwd, **参数表):
            if 命令表[0] == "sh":
                with 开账() as 连接:
                    连接.execute("begin immediate")
                    连接.rollback()
                return 0, str(临时根 / 命令表[-1])
            return 跑命令(命令表, cwd, **参数表)

        def 建树(仓根, 开工号):
            with 开账() as 连接:
                连接.execute("begin immediate")
                连接.rollback()
            return 跑命令(["git", "worktree", "add", "-b", "腿/" + 开工号,
                          str(临时根 / 开工号), 基线提交], cwd=仓根)

        def 清树(仓根, 开工号):
            return 跑命令(["git", "worktree", "remove", "--force", str(临时根 / 开工号)], cwd=仓根)

        with patch.object(开工账本, "连账本", 开账), \
                patch.object(认领隔离, "跑命令", 路径命令), \
                patch.object(登记编排, "建工作树", 建树), \
                patch.object(清树门禁, "清工作树", 清树), \
                patch.object(登记编排, "建工作树索引", lambda 工作树: (0, "样本索引")), \
                patch.object(修改, "同步索引", lambda 工作树: (0, "样本索引")), \
                patch.object(命名闸, "读名册", lambda 工作树: ({"前段函数", "后段函数"}, set())):
            for 工作内容 in ("前段修改", "后段修改"):
                退出码, 回执 = 开工.派发({"功能": 1, "工作内容": 工作内容,
                                       "文件认领": ["样例.py", "规则.db"]}, 仓根)
                assert 退出码 == 0, 回执
            # 回执上界：合并后**两条链的回执都在**（`事务认领` 的独立副本提示 + 514 链的状态化
            # 重叠回执 + 重复登记提示），故上界由 520 的 12 行放宽到 20 行；内容断言不变。
            assert "独立副本" in 回执 and "主键增量重放" in 回执 and len(回执.splitlines()) < 20
            with 开账() as 连接:
                开工表 = 开工账本.列开工(连接)
                assert 连接.execute("select count(*) from 认领重叠").fetchone()[0] == 2
            开工表.reverse()
            for 开工记录, 旧内容, 新内容 in zip(开工表, ("return 1", "return 2"), ("return 11", "return 22")):
                退出码, 回执 = 修改.派发({"开工ID": 开工记录["开工号"], "改动表": [
                    {"路径": "样例.py", "功能": 1, "旧内容": 旧内容, "新内容": 新内容}]}, 仓根)
                assert 退出码 == 0, 回执
                工作树 = Path(开工记录["工作树"])
                _跑Git(工作树, "add", "样例.py")
                _跑Git(工作树, "commit", "-m", 开工记录["工作内容"])
            for 开工记录 in 开工表:
                _跑Git(仓根, "merge", "--no-edit", 开工记录["分支名"])
            全文 = (仓根 / "样例.py").read_text(encoding="utf-8")
            assert "return 11" in 全文 and "return 22" in 全文
            输出表.append(("独立树功能1自动认领、v1_edit各自提交、三方合并保留两函数；短回执与二进制重放提示", True))
            _验拒绝(仓根, 临时根, 开账, 开工表, 输出表)
            _验并发(仓根, 临时根, 开账, 基线提交, 输出表)
            _验冲突(仓根, 临时根, 基线提交, 内容值, 输出表)
            退出码, 回执 = 开工.派发({"功能": 0, "开工ID": 开工表[0]["开工号"]}, 仓根)
            assert 退出码 == 0 and "认领" in 回执
            输出表.append(("功能0查询保留；功能3/4安全释放由424释放样本覆盖", True))
        return 输出表


def 长样本(仓根, 工具表=None, 输出表=None):
    """跑全部重事务场景 ⇒ (退出码, 行表)。断言失败也如实报，不抛给调用方。"""
    记录表 = [] if 输出表 is None else 输出表
    错误 = ""
    try:
        认领样本(仓根, 工具表, 记录表)
    except AssertionError as 异常:
        错误 = "断言失败：%s" % (异常.args[0] if 异常.args else "")
    except Exception as 异常:  # noqa: BLE001 —— 样本要把失败如实报成读数，不吞
        错误 = "%s：%s" % (type(异常).__name__, 异常)
    行表 = ["  %s %s" % ("✓" if 通过 else "✗", 说明) for 说明, 通过 in 记录表]
    if 错误:
        行表.append("  ✗ %s" % 错误)
    失败 = bool(错误) or any(not 通过 for _, 通过 in 记录表)
    return (1 if 失败 else 0), 行表


def 入口(命令行参数, 仓根, 工具表=None):
    """`MCP服务.py --长样本 [--列]` 的实现：`--列` 只报场景名单（短自检的发现口），否则跑全部场景。"""
    if "--列" in 命令行参数:
        for 序号, 场景名 in enumerate(场景表, 1):
            print("%d. %s" % (序号, 场景名))
        return 0
    退出码, 行表 = 长样本(仓根, 工具表)
    print("MCP 长样本 —— 重事务认领链 7 场景（短自检 `--自检` 不跑它；本口挂在提交长路 `一键验证.py --自测`）")
    for 一行读数 in 行表:
        print(一行读数)
    print("长样本：%s（场景 %d 个）" % ("全过" if 退出码 == 0 else "有不过的场景", len(场景表)))
    return 退出码


def _跑Git(工作树, *命令表):
    from .仓操作 import 跑命令
    退出码, 输出文本 = 跑命令(["git", *命令表], cwd=工作树)
    assert 退出码 == 0, 输出文本
    return 输出文本


def 断言夹具自洽(夹具根):
    """夹具的 git **必须**落在夹具那棵树里；**注入 Git 重定向也不许污染别的仓**。

    ① 本仓身份自洽：`--show-toplevel` 与 `--git-dir` 都落在夹具根内。
    ② **541 缺陷的永久反向样本**：主动把 `GIT_DIR` 注入本进程环境指向「别仓」，再在夹具
    （`外仓`）里 `git add` —— 断言别仓索引**零写**、夹具这一侧**真的落账**。
    真事故：父进程带 `GIT_DIR` 时，夹具 `cwd=临时仓` 的 `git add` 会写进**真仓索引**
    （`--git-dir` 指真仓、`--show-toplevel` 仍是临时仓），退出码却是 0 ⇒ 判据 ㊽ 只看退出码
    时**假绿**。`仓操作.跑命令` 已把 `Git重定向键` 从子进程环境里剔掉；别仓是本仓的**安全替身**
    （剔键是无条件的 ⇒ 目标指向哪里都一样，真仓一个字节都不碰）。谁再把重定向键放回去，
    本样本当场红，不是悄悄改真仓。
    """
    import os
    import tempfile
    from .仓操作 import 跑命令, Git重定向键
    夹具根 = Path(夹具根).resolve()
    退出码, 输出文本 = 跑命令(["git", "rev-parse", "--show-toplevel", "--git-dir"], cwd=夹具根)
    行表 = 输出文本.strip().splitlines()
    assert 退出码 == 0 and len(行表) == 2, 输出文本
    # `--git-dir` 在 toplevel 下回的是**相对** `.git` ⇒ 必须按夹具根解析，别按本进程的 cwd。
    Git目录 = Path(行表[1])
    Git目录 = Git目录 if Git目录.is_absolute() else 夹具根 / Git目录
    assert Path(行表[0]).resolve() == 夹具根 and Git目录.resolve().is_relative_to(夹具根), (
        "夹具 git 的 toplevel/git-dir 不在夹具根内 ⇒ 环境有 Git 重定向，会污染真仓：%s" % 输出文本)
    with tempfile.TemporaryDirectory(prefix="v1夹具隔离-") as 临时目录:
        别仓 = Path(临时目录) / "别仓"
        别仓.mkdir()
        _跑Git(别仓, "init")
        外仓 = Path(临时目录) / "外仓"
        外仓.mkdir()
        _跑Git(外仓, "init")
        路径 = 别仓 / ".git" / "index"
        新件 = 外仓 / "隔离样本件.txt"
        新件.write_text("隔离样本\n", encoding="utf-8")
        旧值 = {键名: os.environ.get(键名) for 键名 in Git重定向键}
        try:
            os.environ["GIT_DIR"] = str(别仓 / ".git")
            退出码, 输出文本 = 跑命令(["git", "add", "隔离样本件.txt"], cwd=外仓)
        finally:
            for 键名, 值 in 旧值.items():
                if 值 is None:
                    os.environ.pop(键名, None)
                else:
                    os.environ[键名] = 值
        assert 退出码 == 0, "隔离夹具 git add 没跑成：%s" % 输出文本
        assert not 路径.exists(), (
            "注入 GIT_DIR 后夹具 git add 写进了别仓索引 ⇒ `仓操作.跑命令` 没剔 Git 重定向键"
            "（判据 ㊽ 只看退出码会假绿）：%s" % 输出文本)
        退出码, 输出文本 = 跑命令(["git", "status", "--porcelain"], cwd=外仓)
        assert 退出码 == 0 and "隔离样本件.txt" in 输出文本, (
            "夹具 git add 没落到夹具本体的索引 ⇒ 正向控制失败：%s" % 输出文本)


def _验拒绝(仓根, 临时根, 开账, 开工表, 输出表):
    from . import 开工, 开工账本, 修改, 认领隔离
    开工记录 = 开工表[0]
    工作树 = Path(开工记录["工作树"])
    原文 = (工作树 / "样例.py").read_text(encoding="utf-8")
    (工作树 / "样例.py").write_text(原文 + "# 漂移\n", encoding="utf-8")
    退出码, 回执 = 开工.派发({"功能": 2, "开工ID": 开工记录["开工号"], "文件认领": ["样例.py"]}, 仓根)
    assert 退出码 == 2 and "洗账" in 回执
    退出码, 回执 = 修改.派发({"开工ID": 开工记录["开工号"], "改动表": [
        {"路径": "样例.py", "功能": 1, "旧内容": "return 11", "新内容": "return 12"}]}, 仓根)
    assert 退出码 != 0
    (工作树 / "样例.py").write_text(原文, encoding="utf-8")
    (工作树 / "旁件.txt").write_text("正常旁件", encoding="utf-8")
    退出码, 回执 = 开工.派发({"功能": 2, "开工ID": 开工记录["开工号"], "文件认领": ["旁件.txt"]}, 仓根)
    assert 退出码 == 0, 回执
    with 开账() as 连接:
        开工账本.登记开工(连接, "v1-同树", "同树反向", 开工记录["分支名"], str(工作树))
    for 路径值 in (str(工作树), str(临时根 / "树别名")):
        if 路径值 != str(工作树):
            Path(路径值).symlink_to(工作树, target_is_directory=True)
        with 开账() as 连接:
            连接.execute("update 开工 set 工作树=? where 开工号='v1-同树'", (路径值,))
            连接.commit()
        退出码, 回执 = 开工.派发({"功能": 2, "开工ID": "v1-同树", "文件认领": ["样例.py"], "确认重叠": True}, 仓根)
        assert 退出码 == 2 and "硬闸" in 回执
    with 开账() as 连接:
        连接.execute("delete from 开工 where 开工号='v1-同树'")
        连接.commit()
    (工作树 / "公共别名.txt").symlink_to(仓根 / "样例.py")
    退出码, 回执 = 开工.派发({"功能": 2, "开工ID": 开工记录["开工号"], "文件认领": ["公共别名.txt"]}, 仓根)
    assert 退出码 == 2 and "公共物理" in 回执
    外仓 = 临时根 / "外仓"
    外仓.mkdir()
    _跑Git(外仓, "init")
    with 开账() as 连接:
        开工账本.登记开工(连接, "v1-外仓", "外仓", "master", str(外仓))
        开工账本.认领文件(连接, "v1-外仓", {"样例.py": "外仓指纹"})
    退出码, 回执 = 开工.派发({"功能": 2, "开工ID": 开工记录["开工号"], "文件认领": ["样例.py"], "确认重叠": True}, 仓根)
    assert 退出码 == 2
    with 开账() as 连接:
        连接.execute("delete from 认领 where 开工号='v1-外仓'")
        连接.execute("delete from 开工 where 开工号='v1-外仓'")
        连接.commit()
    # 仓根为 bare（core.bare=true）时树身份核验仍须成立；外仓照旧拒。
    _跑Git(仓根, "config", "core.bare", "true")
    assert 认领隔离.核验树身份(仓根, 工作树, 开工记录["分支名"]), "bare 仓根下树身份核验失败"
    assert 认领隔离.核验树身份(仓根, 外仓, "master") is None, "外仓未被拒"
    _跑Git(仓根, "config", "core.bare", "false")
    输出表.append(("bare 仓根（core.bare=true）下树身份仍核验成立；外仓仍拒", True))


def _验冲突(仓根, 临时根, 基线提交, 内容值, 输出表):
    from .仓操作 import 跑命令
    for 说明, 新内容表 in (("同片段", (内容值.replace("return 1", "return 31"), 内容值.replace("return 1", "return 32"))),
                        ("父子片段", (内容值.replace("def 前段函数():\n    return 1", "def 前段函数():\n    return 41\n    # 父片段"),
                                  内容值.replace("return 1", "return 42")))):
        支线表 = []
        for 序号, 新内容 in enumerate(新内容表):
            支线名 = "冲突/" + 说明 + str(序号)
            工作树 = 临时根 / (说明 + str(序号))
            _跑Git(仓根, "worktree", "add", "-b", 支线名, str(工作树), 基线提交)
            (工作树 / "样例.py").write_text(新内容, encoding="utf-8")
            _跑Git(工作树, "add", "样例.py")
            _跑Git(工作树, "commit", "-m", 说明)
            支线表.append(支线名)
        工作树 = 临时根 / (说明 + "合并")
        _跑Git(仓根, "worktree", "add", "--detach", str(工作树), 支线表[0])
        退出码, 回执 = 跑命令(["git", "merge", "--no-edit", 支线表[1]], cwd=工作树)
        全文 = (工作树 / "样例.py").read_text(encoding="utf-8")
        assert 退出码 == 1 and "<<<<<<<" in 全文 and "=======" in 全文 and ">>>>>>>" in 全文
        assert all(_跑Git(仓根, "rev-parse", 支线名).strip() for 支线名 in 支线表)
        输出表.append((说明 + "三方合并报告冲突，标记保留双方且两支提交仍在；覆盖文本重叠示例", True))
    输出表.append(("同树/别名/公共源落点/非本仓拒绝；确认重叠不绕硬闸；漂移拒写拒洗账，旁件可继续", True))


def _验并发(仓根, 临时根, 开账, 基线提交, 输出表):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, local
    from unittest.mock import patch
    from . import 开工, 开工账本, 认领隔离
    同步闸 = Barrier(2)
    线程状态 = local()
    原核验 = 认领隔离.判认领隔离

    def 同步核验(*参数表):
        核验结果 = 原核验(*参数表)
        if not getattr(线程状态, "已同步", False):
            线程状态.已同步 = True
            同步闸.wait(timeout=5)
        return 核验结果

    def 补认领(开工号):
        return 开工.派发({"功能": 2, "开工ID": 开工号, "文件认领": ["样例.py"]}, 仓根)

    号表 = ["v1-并发前", "v1-并发后"]
    for 开工号 in 号表:
        工作树 = 临时根 / 开工号
        _跑Git(仓根, "worktree", "add", "-b", "腿/" + 开工号, str(工作树), 基线提交)
        with 开账() as 连接:
            开工账本.登记开工(连接, 开工号, "并发认领", "腿/" + 开工号, str(工作树))
    with patch.object(认领隔离, "判认领隔离", 同步核验), ThreadPoolExecutor(max_workers=2) as 并发池:
        结果表 = list(并发池.map(补认领, 号表))
    assert all(退出码 == 0 for 退出码, _ in 结果表), 结果表
    with 开账() as 连接:
        assert all("样例.py" in 开工账本.读认领(连接, 开工号) for 开工号 in 号表)
        for 开工号 in 号表:
            连接.execute("delete from 认领 where 开工号=?", (开工号,))
        连接.execute("update 开工 set 工作树=?,分支名=? where 开工号=?",
                     (str(临时根 / 号表[0]), "腿/" + 号表[0], 号表[1]))
        连接.commit()
    同步闸 = Barrier(2)
    线程状态 = local()
    with patch.object(认领隔离, "判认领隔离", 同步核验), ThreadPoolExecutor(max_workers=2) as 并发池:
        结果表 = list(并发池.map(补认领, 号表))
    assert sorted(退出码 for 退出码, _ in 结果表) == [0, 2], 结果表
    输出表.append(("强制相同旧快照的并发认领：独立树两者成功，同树只有一个成功；事务内复核状态一致", True))
