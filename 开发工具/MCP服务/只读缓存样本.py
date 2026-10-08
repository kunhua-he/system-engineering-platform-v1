# -*- coding: utf-8 -*-
"""只读缓存样本 —— `只读缓存.py` 的正式正反样本（判据 ㊽ 的隔离组之一）。

**为什么进正式自检**：独立审计 F1–F4 抓到的都是**缓存陈旧**（同进程内盘面变了却回旧值），
这类缺陷不落成常驻样本就会回潮。本组把「该缓存的照旧缓存、不该缓存的一律现跑」逐条钉住，
**失败即整条 `--自检` 非 0**（`跑隔离样本` 逐组核 len == 计数，任一条 False 即拒）。

**隔离**：本组跑在**独立子进程**里（`隔离样本入口`），临时仓 + 临时环境全在组内建 / 删，
真仓一个字节不改；`GIT_CONFIG_GLOBAL` 一类环境键在组内临时设置、`finally` 还原。
**本组自带全部夹具，不依赖任何 `/tmp` 脚本**。
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def 样本列表(仓根) -> list:
    """⇒ `[(说明, 通过)]`。每条独立临时仓，跑完即删。"""
    from . import 仓状态
    from .只读缓存 import 问句缓存, 可缓存, 仓状态指纹, 跑只读命令

    环境 = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    样本表 = []
    临时根 = Path(tempfile.mkdtemp(prefix="v1只读缓存样本-"))
    try:
        def 建仓(仓库根, 初值):
            仓库根.mkdir(parents=True, exist_ok=True)

            def 执行(*参数列):
                subprocess.run(["git", *参数列], cwd=仓库根, check=True,
                               capture_output=True, env=环境)
            执行("init", "-q")
            (仓库根 / "首件.txt").write_text(初值, encoding="utf-8")
            执行("add", "首件.txt")
            执行("-c", "user.name=样本", "-c", "user.email=样本@例", "commit", "-qm", "一")
            return 执行

        首样本仓 = 临时根 / "首样本仓"
        次样本仓 = 临时根 / "次样本仓"
        首仓提交 = 建仓(首样本仓, "一\n")
        建仓(次样本仓, "壹\n")

        # ① F1：`ls-files --cached --others --exclude-standard` 依赖工作区 ⇒ 拒缓存
        样本表.append(("F1 `ls-files --cached --others --exclude-standard` 不缓存",
                 可缓存(["ls-files", "--cached", "--others", "--exclude-standard"]) is False))
        样本表.append(("F1 纯 `ls-files --cached` 可缓存", 可缓存(["ls-files", "--cached"]) is True))
        前值 = 仓状态.跑git(首样本仓, ["ls-files", "--cached", "--others", "--exclude-standard"])
        (首样本仓 / "新未跟踪.py").write_text("x=1\n", encoding="utf-8")
        后值 = 仓状态.跑git(首样本仓, ["ls-files", "--cached", "--others", "--exclude-standard"])
        样本表.append(("F1 新建未跟踪件后立刻可见（不漏件）",
                 "新未跟踪.py" not in 前值[1] and "新未跟踪.py" in 后值[1]))

        # ② F2：`--short` / 对象集敏感子命令 ⇒ 拒缓存
        样本表.append(("F2 `rev-parse --short HEAD` 不缓存",
                 可缓存(["rev-parse", "--short", "HEAD"]) is False))
        样本表.append(("F2 `rev-parse --abbrev-ref HEAD` 仍可缓存",
                 可缓存(["rev-parse", "--abbrev-ref", "HEAD"]) is True))
        样本表.append(("F2 `log` / `describe` / `name-rev` 不缓存",
                 可缓存(["log", "-1"]) is False and 可缓存(["describe"]) is False
                 and 可缓存(["name-rev", "HEAD"]) is False))

        # ③ F3：配置敏感子命令 + 环境键 ⇒ 拒缓存
        样本表.append(("F3 `rev-parse --is-bare-repository` 不缓存",
                 可缓存(["rev-parse", "--is-bare-repository"]) is False))
        原环境 = dict(os.environ)
        try:
            os.environ["GIT_CONFIG_GLOBAL"] = str(临时根 / "全局配置")
            问句缓存.clear()
            首答 = 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])
            数一 = len(问句缓存)
            再答 = 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])
            数二 = len(问句缓存)
            样本表.append(("F3 环境带 GIT_CONFIG_GLOBAL ⇒ 不写缓存",
                     数一 == 0 and 数二 == 0 and 首答 == 再答))
        finally:
            os.environ.clear()
            os.environ.update(原环境)

        # ④ F4：带工作区开关的 ls-files / diff 一律拒缓存
        for 问句形 in (["ls-files", "--cached", "--modified"], ["ls-files", "--cached", "-m"],
                    ["ls-files", "--cached", "--deleted"], ["ls-files", "--cached", "-u"],
                    ["ls-files", "--cached", "--ignored"], ["diff", "--no-index", "左件", "右件"]):
            样本表.append(("F4 %s 不缓存" % " ".join(问句形), 可缓存(问句形) is False))

        # ⑤ 命中与 ref 变失效
        首提交 = 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])
        问句缓存.clear()
        首仓一问 = 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])
        条一 = len(问句缓存)
        首仓再问 = 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])
        条二 = len(问句缓存)
        样本表.append(("命中：同问句两次同值且缓存不新增",
                 首仓一问 == 首仓再问 == 首提交 and 条一 == 条二 == 1))
        (首样本仓 / "首件.txt").write_text("二\n", encoding="utf-8")
        首仓提交("commit", "-qam", "二")
        样本表.append(("ref 变失效：新提交后读到新 HEAD",
                 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])[1] != 首提交[1]))

        # ⑥ 跨树不串
        样本表.append(("跨树不串：同 argv 两仓各读各自 HEAD",
                 仓状态.跑git(次样本仓, ["rev-parse", "HEAD"])[1]
                 != 仓状态.跑git(首样本仓, ["rev-parse", "HEAD"])[1]))

        # ⑦ 失败不缓存（未出现的 ref 后来出现要能立刻读到）
        失败值 = 仓状态.跑git(首样本仓, ["rev-parse", "--verify", "--quiet", "新支^{commit}"])
        首仓提交("branch", "新支")
        出现值 = 仓状态.跑git(首样本仓, ["rev-parse", "--verify", "--quiet", "新支^{commit}"])
        样本表.append(("失败不缓存：先失败后出现能立刻读到", 失败值[0] != 0 and 出现值[0] == 0))

        # ⑧ index 变失效
        索引前 = 仓状态.跑git(首样本仓, ["ls-files", "--cached"])
        (首样本仓 / "次件.txt").write_text("x\n", encoding="utf-8")
        首仓提交("add", "次件.txt")
        索引后 = 仓状态.跑git(首样本仓, ["ls-files", "--cached"])
        样本表.append(("index 变失效：add 后 ls-files --cached 含新件",
                 "次件.txt" not in 索引前[1] and "次件.txt" in 索引后[1]))

        # ⑨ 拒缓存面（工作区）
        样本表.append(("status / worktree / 工作区 diff 不缓存",
                 可缓存(["status", "--porcelain"]) is False
                 and 可缓存(["worktree", "list"]) is False
                 and 可缓存(["diff", "--name-only"]) is False
                 and 可缓存(["diff", "--cached", "--name-only"]) is True))

        # ⑩ 无仓不缓存
        空目录 = 临时根 / "空目录"
        空目录.mkdir()
        样本表.append(("无仓目录指纹为空 ⇒ 不缓存", 仓状态指纹(空目录) == ""))

        # ⑪ 工作树（.git 文件 + commondir）指纹可算；认领/写盘恢复用的定位问句仍可缓存
        工树 = 临时根 / "工树"
        subprocess.run(["git", "worktree", "add", "-q", str(工树), "-b", "样本支"],
                       cwd=首样本仓, check=True, capture_output=True, env=环境)
        样本表.append(("工作树（.git 文件 + commondir）指纹非空", len(仓状态指纹(工树)) == 16))
        样本表.append(("`--path-format=absolute --git-common-dir` 仍可缓存",
                 可缓存(["rev-parse", "--path-format=absolute", "--git-common-dir"]) is True))

        # ⑫ 读前读后竞态：底层查询期间仓被改 ⇒ 丢弃不写
        问句缓存.clear()

        def 底层(仓根, 参数表, 树根=None, 超时=5):
            (首样本仓 / "首件.txt").write_text("三\n", encoding="utf-8")
            首仓提交("commit", "-qam", "三")
            return 0, "伪造"

        跑只读命令(底层, 首样本仓, ["rev-parse", "HEAD"])
        样本表.append(("读前读后指纹不一致 ⇒ 丢弃不写", len(问句缓存) == 0))
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表
