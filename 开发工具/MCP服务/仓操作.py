# -*- coding: utf-8 -*-
"""仓操作 —— 开工腿用到的**仓内动作**：跑命令 · 找/建/清工作树 · 读盘指纹 · 变更路径表。

**为什么单独一件**：`开工.py` 已顶 400 行硬数（判据 ⑲）⇒ 照先例「入口转出口」把**环境步**
（git 子进程 · 工作树 · 指纹）挪出来，`开工.py` 只留各功能的编排。**实现只有这一份**：
`符号` / `生成物记账` / `源件记账` 都从本件取，不在别处再写一遍。

**索引必须按树分**：工作树是 `git worktree add` 出来的，只检出**已跟踪件**，而 `.codegraph/`
未跟踪 ⇒ 新树里没有索引。索引落点由 `__file__` 算 ⇒ 在哪棵树里跑 `建` 就在哪棵树里落，
所以这里调的是 `python3 开发工具/代码地图.py 建` 这个**子进程**（不是 import —— import 会把
落点钉在主树上）。

`找工作树` 为什么问 git 而不是拼目录名：那个名字（`系统工程平台V1.工作树`）的唯一定义处是
`开发工具/并行工作树.sh` —— 在本件再写一份就是**第二来源**（判据 ㉕ 当场红，实测撞过）。
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/
from 代码地图 import 文件指纹  # noqa: E402  —— 指纹只此一份（sha256 前 16 位）

超时秒 = 5                     # 查询/写盘这类要判顶的；建树与建索引是**环境步**，不设超时

# git 的提交/推送不设超时（一趟就是它自身的长度），但**必须**禁掉终端提示：
# 远端要认证时 git 会停下来等人敲密码 —— 那不是超时，是**永挂**（子进程 stdin 是管道，没人能敲）。
禁终端提示环境 = {"GIT_TERMINAL_PROMPT": "0"}


def 跑命令(命令表: list, cwd, 超时秒数=超时秒, 输入文本=None, 子进程环境=None) -> tuple:
    """跑一条命令 ⇒ `(退出码, 合并输出)`。超时给 `-1`（**不许当成通过**）。

    `超时秒数=None` ⇒ **不设超时**（环境步：建工作树 · 建索引 —— 一趟就是它自身的长度）。
    `输入文本` 给了就从 stdin 喂进去（`git commit -F -` 用 —— 免得为一条提交信息落临时件）。
    `子进程环境` 给的键**并进**当前环境（不是替换）。git 的 push/commit 必须带 `GIT_TERMINAL_PROMPT=0`：
    不设超时 + 远端要认证 ⇒ git 会**等着人敲密码**，那是一个没有上限的挂起。
    """
    import os
    环境表 = dict(os.environ)
    if 子进程环境:
        环境表.update(子进程环境)
    try:
        回执 = subprocess.run(命令表, cwd=str(cwd), capture_output=True, text=True,
                            input=输入文本, timeout=超时秒数, env=环境表)
    except subprocess.TimeoutExpired:
        return -1, "超时（%s 秒）—— 先查是哪一段慢" % 超时秒数
    except OSError as 起不来的原因:
        return -2, "起不了：%r" % (起不来的原因,)
    return 回执.returncode, (回执.stdout or "") + (回执.stderr or "")


def 跑验证复跑超顶(工作树) -> tuple:
    """跑 `闸0.py`；**瞬时超顶**（并发腿抢 CPU）自动复跑一次 ⇒ `(退出码, 输出, 复跑过)`。

    口径**单源**在 `构建装配/门禁/复跑.py`（pre-commit 钩子共用同一份）—— 本件只把「跑一次」
    接到 `跑命令` 上。原先 `释放` 只跑一次 ⇒ 机器一忙（实测闸 0 墙钟 4816 > 4800 ms）就假红、
    逼人重试（实测 545 腿）。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # 仓根：取共享门禁
    from 构建装配.门禁 import 跑并复跑超顶
    return 跑并复跑超顶(lambda: 跑命令([sys.executable, "构建装配/一键验证/闸0.py"], cwd=工作树))


def 分支名(开工号: str) -> str:
    return "腿/" + 开工号


def 支线在吗(仓根, 开工号: str) -> bool:
    """这条开工的支线还在不在 ⇒ 真假。**问 git**，不问目录（同 `找工作树` 的理由）。

    用途：`清工作树` 判幂等（树与支线都不在 ⇒ 无物可清）· `查僵尸` 判僵尸（树与支线都没了）。
    """
    退出码, 输出文本 = 跑命令(["git", "branch", "--list", 分支名(开工号)], cwd=仓根)
    return 退出码 == 0 and bool(输出文本.strip())


def 找工作树(仓根, 开工号: str):
    """**问 git** 这条开工的工作树在哪 ⇒ `Path` 或 `None`。

    为什么不在这里拼目录名：那个名字（`系统工程平台V1.工作树`）的唯一定义处是
    `开发工具/并行工作树.sh` —— 在本件再写一份就是**第二来源**（判据 ㉕ 当场红，实测撞过）。
    git 知道每条工作树在哪，问它最准。
    """
    退出码, 输出文本 = 跑命令(["git", "worktree", "list", "--porcelain"], cwd=仓根)
    if 退出码 != 0:
        return None
    目标分支 = "refs/heads/" + 分支名(开工号)
    当前路径 = None
    for 源码行 in 输出文本.splitlines():
        if 源码行.startswith("worktree "):
            当前路径 = 源码行[len("worktree "):].strip()
        elif 源码行.strip() == "branch " + 目标分支 and 当前路径:
            return Path(当前路径)
    return None


def 建工作树(仓根, 开工号: str) -> tuple:
    """调 `并行工作树.sh 新建 <开工号>`（**一处实现**：它还建那棵树的构建缓存与 venv）。"""
    脚本路径 = Path(仓根) / "开发工具" / "并行工作树.sh"
    return 跑命令(["sh", str(脚本路径), "新建", 开工号], cwd=仓根, 超时秒数=None)


def 建工作树索引(工作树: Path) -> tuple:
    """在那条工作树里跑 `代码地图.py 建`（子进程 —— 落点由 `__file__` 算，天然按树分）。"""
    return 跑命令([sys.executable, "开发工具/代码地图.py", "建"], cwd=工作树, 超时秒数=None)


def 检查提交门禁(工作树) -> tuple:
    """缺失或不可执行的提交钩子不能证明自测与案例已过。"""
    import os
    退出码, 输出文本 = 跑命令(["git", "rev-parse", "--git-path", "hooks/pre-commit"], cwd=工作树)
    钩子路径 = Path(输出文本.strip())
    if not 钩子路径.is_absolute():
        钩子路径 = Path(工作树) / 钩子路径
    if 退出码 != 0 or not 钩子路径.is_file() or not os.access(钩子路径, os.X_OK):
        return 1, "提交门禁钩子缺失或不可执行 ⇒ 不提交、不释放"
    return 0, "提交门禁已安装"


def 跑空改门禁(工作树) -> tuple:
    """复用 Git 实际生效的 pre-commit；缺钩子或钩子失败都拒绝空改释放。"""
    return 跑命令(["git", "hook", "run", "pre-commit"], cwd=工作树,
                 超时秒数=None, 子进程环境=禁终端提示环境)


def 检查清树安全(仓根, 开工号: str, 工作树) -> tuple:
    """清理前证明没有未提交改动，且支线已进入主工作树当前历史。"""
    if Path(工作树).is_dir():
        退出码, 输出文本 = 跑命令(["git", "status", "--porcelain", "-uall"], cwd=工作树)
        if 退出码 != 0 or 输出文本.strip():
            return 1, "工作树有未提交改动或状态读不出 ⇒ 拒绝清理，保留树与支线：\n%s" % 输出文本[-400:]
    退出码, 输出文本 = 跑命令(["git", "worktree", "list", "--porcelain"], cwd=仓根)
    if 退出码 != 0 or not 输出文本.startswith("worktree "):
        return 1, "无法确定主工作树 ⇒ 拒绝清理"
    主树路径 = Path(输出文本.splitlines()[0][len("worktree "):])
    if 主树路径.resolve() == Path(工作树).resolve():
        return 1, "目标是主工作树 ⇒ 拒绝清理"
    退出码, 主树提交 = 跑命令(["git", "rev-parse", "HEAD"], cwd=主树路径)
    if 退出码 != 0:
        return 1, "无法读取主工作树提交 ⇒ 拒绝清理"
    退出码, 输出文本 = 跑命令(["git", "show-ref", "--verify", "--quiet",
                              "refs/heads/" + 分支名(开工号)], cwd=仓根)
    if 退出码 == 1:
        return 0, "支线已不存在"
    if 退出码 != 0:
        return 1, "无法读取支线引用 ⇒ 拒绝清理"
    退出码, 输出文本 = 跑命令(["git", "merge-base", "--is-ancestor", 分支名(开工号),
                              主树提交.strip()], cwd=仓根)
    if 退出码 != 0:
        return 1, "支线尚未合并到主工作树或无法确认 ⇒ 拒绝清理，保留提交与支线"
    return 0, "支线已合并到主工作树"


def 清工作树(仓根, 开工号: str) -> tuple:
    """移工作树 + 删支线 ⇒ `(退出码, 一句话说明)`。**幂等**：树与支线都不在 ⇒ 什么都不做、返回成功。

    `并行工作树.sh 移除` 只移树、**保留支线**（便于查它的提交）⇒ 这里补删。
    ★ 回执由本件**就地拼**（2026-10-01 修）：原先直接转发那条命令的输出，于是回执里同时出现
    「分支 `腿/<名>` 保留，便于查它的提交」（脚本的话）与 git 的 `Deleted branch 腿/<名>`
    （**这里真删了**）⇒ **自相矛盾**，收口方会以为还能靠支线查提交。删支线是刻意的（提交已在
    origin/腿/<名> 与主干历史里），故文案要如实写「已删」。
    ★ 树与支线都早已不在时，那两条命令会报
    `fatal: '…' is not a working tree` / `error: branch '…' not found` ⇒ 调用方把
    「早已清干净」误判成失败。故**先问存在性再动手**（存在性走 `找工作树` / `支线在吗`）。
    """
    工作树在 = 找工作树(仓根, 开工号) is not None
    支线在 = 支线在吗(仓根, 开工号)
    if not 工作树在 and not 支线在:
        return 0, "无物可清（工作树与支线都不在）"
    脚本路径 = Path(仓根) / "开发工具" / "并行工作树.sh"
    码一 = 码二 = 0
    说明表 = []
    if 工作树在:
        # 环境步同建树口径（`超时秒数=None`）：移除带构建缓存的大树可能 >5s，默认 5 秒会把
        # 它误报成「工作树没移除掉（退出码 -1）」（2026-10-05 修 · 与建树 `:89` 对齐）。
        码一, 出一 = 跑命令(["sh", str(脚本路径), "移除", 开工号], cwd=仓根, 超时秒数=None)
        if 码一 == 0:
            说明表.append("工作树已移除")
        else:
            说明表.append("工作树**没**移除掉（退出码 %d）：%s" % (码一, 出一.strip()[-300:]))
    if 支线在 and 码一 == 0:
        码二, 出二 = 跑命令(["git", "branch", "-D", 分支名(开工号)], cwd=仓根)
        if 码二 == 0:
            说明表.append("分支 `%s` 已删" % 分支名(开工号))
        else:
            说明表.append("分支 `%s` **没**删掉（退出码 %d）：%s"
                      % (分支名(开工号), 码二, 出二.strip()[-300:]))
    return (码一 or 码二), " · ".join(说明表)


def 读盘指纹(工作树: Path, 相对路径表: list) -> tuple:
    """认领那一刻 MCP **当场读盘**算指纹 ⇒ `({路径: 指纹}, 读不出的路径表)`。

    agent 只给路径、不传指纹。读不出的件（路径写错 / 不存在）**不静默跳过** —— 报出来，
    由调用方**拒收**（2026-10-01：认领不存在的路径必须拒，不许收进认领表 —— 收进去会让
    `释放` 的 `git add` 撞 `fatal: pathspec … did not match any files`，整条腿卡死）。
    """
    指纹表, 读不出表 = {}, []
    for 相对路径 in 相对路径表:
        相对路径项 = str(相对路径).strip()
        if not 相对路径项:
            continue
        # 只认仓内相对路径（口径与 `修改._读一条改动` 同一份）：绝对路径 / `..` **fail-closed 拒收**
        # —— 原先只 `strip()` ⇒ 绝对路径被静默收进认领表，后续 `对账` 会拿 `工作树 / "/etc/hosts"`
        # = `/etc/hosts` 去比指纹（认领表可被塞进树外/仓外路径）。
        if 相对路径项.startswith("/") or ".." in Path(相对路径项).parts:
            读不出表.append(相对路径项)
            continue
        件路径 = 工作树 / 相对路径项
        if not 件路径.is_file():
            读不出表.append(相对路径项)
            continue
        指纹表[相对路径项] = 文件指纹(str(件路径))
    return 指纹表, 读不出表


def 变更路径表(工作树) -> tuple:
    """`git status --porcelain` ⇒ `(退出码, 变过的路径表 或 说明)`。**一处解析**：`释放` 的
    越界检测与 `生成物记账` 的产出识别共用它 —— 不各写一份「什么算脏」。
    """
    退出码, 输出文本 = 跑命令(["git", "status", "--porcelain", "-uall"], cwd=工作树)
    if 退出码 != 0:
        return 退出码, "git status 失败（查不清盘上动了什么）：\n%s" % 输出文本.strip()[-400:]
    路径表 = []
    for 源码行 in 输出文本.splitlines():
        if not 源码行.strip():
            continue
        路径 = 源码行[3:].strip().strip('"')
        if " -> " in 路径:
            路径 = 路径.split(" -> ")[-1].strip().strip('"')
        if 路径:
            路径表.append(路径)
    return 0, 路径表
