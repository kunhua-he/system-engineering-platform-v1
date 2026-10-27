# -*- coding: utf-8 -*-
"""判据 ㉓：散文不落被忽略目录（被 `.gitignore` 忽略的目录里 0 处 `.md`）。

依据：`README.md` §十（本树明确不含什么）· `项目文档/开发规范/开发规范.md` §八.8
（「散文不许住进被忽略的目录」）· `项目文档/决策记录/2026-09-27_判据口径十一条.md` §十四
「落法」末段（那份 `构建装配/制品产物/说明.md` 就是这么永久丢的）。

**口径（读数已定，不许再发明）**：

    git ls-files --others --ignored --exclude-standard -z | tr '\\0' '\\n' | grep '\\.md$' | grep -v '^构建环境/构建缓存/'

**必须带 `-z`**：`core.quotePath=false` 只关「非 ASCII 加引号」，含空格 / 引号 / 换行的路径仍会失真，
`splitlines()` 还会把一个含换行的件名拆成两条；只有 NUL 分隔是路径安全形式（2026-10-27 实证：
不带 `-z` 时中文路径读成八进制串 ⇒ 本条曾假绿）。

**空即通过**。要排掉 `构建环境/构建缓存/`：那里只放自动生成或可由锁定依赖还原的第三方缓存，
包括 rustdoc 字体 LICENSE 和 Cargo 原包说明，不能放项目编写的散文。

**为什么要有它**：被 `.gitignore` 忽略的目录会被 `git clean -xdf` 一次清掉，而散文（`.md`）
**不可复得**（实测已丢过一份 `构建装配/制品产物/说明.md`：它从未进版本库、别处无副本）。
纪律写在 `开发规范.md` §八.8 里，但**没有判据** —— 于是它只是一条能手跑的命令，会随仓长大而失效。
本条把它变成常驻判据：读数不为空即红，并逐条指名那份散文。

**git 定位**（2026-10-07）：目标树若为 **bare 布局**（`core.bare = true`）⇒
`git -C <仓根> ls-files` 退 128「must be run in a work tree」。故**显式**给 `--git-dir` /
`--work-tree`（`.git` 是目录时），并剔除继承的 Git 定位变量；不改全局 Git 配置、不改
`core.bare`。`.git` 是文件（工作树）⇒ 退 `-C`（同 `开发工具/MCP服务/作业执行/shell.py` 口径）。

**非 git 仓**（读不出被忽略面）⇒ 报**判不了**（未判），不是通过 —— 空集不算通过。
故正向样本的合成仓自身 `git init`（见 `合成仓.py`），这样本条在夹具上也有对象。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from 构建装配.门禁.git路径解析 import 解析零分隔

from ...判据编排.验证小工具 import 判不了, 违规
from ...基础定义.常量 import 检查名


# 子进程不许继承的 Git 定位变量（会把 git 带到别的树 / 别的 index 上）—— 同 `开发工具/MCP服务/作业执行/shell.py`
继承定位变量 = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
              "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")


def 版本库命令(仓根: Path, *子命令: str) -> list:
    """git 命令**显式定位**这条仓：`.git` 是目录（含 bare 主目录）⇒ 给 `--git-dir` / `--work-tree`；
    否则（工作树 `.git` 是文件）⇒ 退 `-C`。与 `开发工具/MCP服务/作业执行/shell.py` 同一份口径。
    """
    仓库元目录 = 仓根 / ".git"
    if 仓库元目录.is_dir():
        return ["git", "--git-dir", str(仓库元目录), "--work-tree", str(仓根), *子命令]
    return ["git", "-C", str(仓根), *子命令]


def 版本库环境() -> dict:
    """子进程环境：剔除继承的 Git 定位变量（避免读成被污染的仓）。"""
    环境表 = dict(os.environ)
    for 键名 in 继承定位变量:
        环境表.pop(键名, None)
    return 环境表


# 被忽略面里**按设计允许**的 `.md` 前缀表（不是我们的散文）：
# · `构建环境/构建缓存/` —— rustdoc 生成的字体 LICENSE；
# · `.zcode/` —— zcode 客户端目录，2026-09-27 已裁决「不进版本库、各机自行维护」，
#   里面的 `.md` 是工具配置（子代理定义 / 计划草稿），挪不得、也不该进库。
被忽略散文排除前缀表 = ("构建环境/构建缓存/", ".zcode/")

# 读数命令是定死的（文件头）；git 的读数在一次运行里不变 ⇒ 缓存住，避免对象数与判定各跑一遍。
_忽略条目缓存: dict = {}


def 忽略条目(仓根) -> tuple:
    """跑一次 `git ls-files --others --ignored --exclude-standard` ⇒ `(条目表, 错误或 None)`。

    返回的是**全部**被忽略条目（未过滤 `.md`）—— 它同时是「对象数」（0 ⇒ 未判）。
    """
    键名 = str(仓根)
    if 键名 in _忽略条目缓存:
        return _忽略条目缓存[键名]
    try:
        判定汇总 = subprocess.run(
            版本库命令(Path(键名), "ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
            capture_output=True, text=True, timeout=5, env=版本库环境(),
        )
    except (OSError, subprocess.SubprocessError) as 错误:
        待处理值 = ([], f"跑不动 git（{type(错误).__name__}：{错误}）")
        _忽略条目缓存[键名] = 待处理值
        return 待处理值
    if 判定汇总.returncode != 0:
        待处理值 = ([], f"git ls-files 退出码 {判定汇总.returncode}：{判定汇总.stderr.strip()[:200]}")
        _忽略条目缓存[键名] = 待处理值
        return 待处理值
    待处理值 = (解析零分隔(判定汇总.stdout), None)
    _忽略条目缓存[键名] = 待处理值
    return 待处理值


def 是版本库(仓根) -> bool:
    """仓根能不能被 git 读到（`rev-parse --git-dir` 退出码 0 即算；worktree 也算）。"""
    判定汇总 = subprocess.run(
        版本库命令(Path(仓根), "rev-parse", "--git-dir"),
        cwd=str(仓根), capture_output=True, text=True, env=版本库环境(),
    )
    return 判定汇总.returncode == 0


def 样本_忽略条目(上层读数: dict) -> int:
    """对象数：本判据的**适用面** —— 仓是不是 git 仓（`.gitignore` 机制在不在）。

    不取「被忽略条目数」：开工腿与集成树都是新建 worktree，只 checkout 跟踪件 ⇒ 被忽略件
    天然为 0，取条目数会让本条在**每次合主线**时判「空集未判」（2026-10-10 实测）。
    条目本身由判定函数读（同一份缓存）；对象数只回答「这条判据有没有面可判」。
    """
    return 1 if 是版本库(上层读数["仓根"]) else 0


def 检查23_散文不落被忽略目录(上层读数: dict) -> list:
    """被忽略目录里的散文必须为空（`git ls-files --others --ignored` 里的 `.md`）。

    三元读数：**通过** = 被忽略面非空且其中 0 个（非排除前缀的）`.md`；
    **失败** = 逐条报出那份散文；**未判** = 读不出被忽略面（非 git 仓 / git 不可用）。
    """
    输出缓冲 = []
    忽略条目表, 错误 = 忽略条目(上层读数["仓根"])
    if 错误:
        判不了(
            检查名[22],
            "git ls-files --others --ignored --exclude-standard",
            f"判不了：{错误}",
            "被忽略目录里的散文只有 git 看得见（`.gitignore` 的语义不许自身重写一份——"
            "那是第二个事实源）⇒ 读不出就判不了。读数命令是定死的（见文件头）⇒ "
            "只能由环境（git 可用）或判据作者确认",
        )
        return 输出缓冲
    if not 忽略条目表:
        # 条目真为 0 有两种：git 仓里确实没有忽略件（含开工腿 / 集成树 worktree —— 它们只
        # checkout 跟踪件）；非 git 树。两种都不是本判据的违规 ⇒ 直接返回（通过）。
        return 输出缓冲

    命中 = [
        键名 for 键名 in 忽略条目表
        if 键名.endswith(".md") and not 键名.startswith(被忽略散文排除前缀表)
    ]
    for 键名 in sorted(命中):
        输出缓冲.append(
            违规(
                检查名[22],
                键名,
                f"散文 `{键名}` 落在被 git 忽略的目录里 ⇒ 一次 `git clean -xdf` 就永久丢",
                "`开发规范.md` §八.8：**散文不许住进被忽略的目录**。落点目录要被忽略时，"
                "忽略必须写成「忽略内容 + 例外散文」（`构建装配/制品产物/*` + "
                "`!构建装配/制品产物/说明.md`），否则任何一次 `git clean -xdf` 都会把文档清掉，"
                "而散文不可复得（实测已丢过一份）⇒ 只能由把这份散文放进该目录的人挪出/加例外",
            )
        )
    return 输出缓冲
