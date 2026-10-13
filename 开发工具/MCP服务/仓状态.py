# -*- coding: utf-8 -*-
"""仓状态 —— `v1_repo` 的实现：仓级只读快照（一次给全）＋环境体检。

**为什么要有它**（多路代理实测）：一次「仓现在什么样」要 8+ 条命令拼（status / branch / worktree
list / rev-list / 账本查询 / hash-object），逐条一次往返。本件把它收成一个**有界只读回执**，只跑
查询类 git 子命令 ＋账本 sqlite **只读**连接（零写）。

**bare 仓根**：本仓主目录 `core.bare=true` ⇒ 需要工作树的命令（`status`/`hash-object`）要显式给
`GIT_DIR`/`GIT_WORK_TREE`（与 `shell.py` 同一份口径），否则 git 报「must be run in a work tree」。
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # 开发工具/

from 运行数据根 import 无位置, 子目录路径, 解析当前环境          # noqa: E402
from .仓操作 import 找工作树, 禁终端提示环境, 跑命令              # noqa: E402
from .开工账本 import 库文件名, 子目录类别
from .名册僵尸 import 读僵尸行                                    # noqa: E402                        # noqa: E402

超时秒 = 5
字节上限 = 20000
上限条数 = 200
跳过目录 = frozenset({".git", "__pycache__", ".codegraph", "node_modules", "target",
                  "构建缓存", "cargo", "python"})
主入口模式 = re.compile(r'^if\s+__name__\s*==\s*[\'\"]__main__[\'\"]\s*:', re.M)
超时参 = re.compile(r"timeout\s*=\s*([0-9][0-9_]*)")
源件路径 = "开发工具/信息核心/信息核心.db"
配置路径 = ".mcp.json"
索引路径 = "开发工具/代码地图/索引库.py"
文档路径 = "项目文档/文档账本.json"

class 参数错(Exception):
    """参数不合法 —— 派发层折成退出码 2 ＋ 最短例（缺参 / 未知参一次拒）。"""

def git环境(树根) -> dict:
    """子进程环境：剔除继承的 Git 定位变量 ＋ 禁终端提示；bare 仓根显式给 GIT_DIR/GIT_WORK_TREE。"""
    环境表 = dict(os.environ)
    for 键名 in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
               "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        环境表.pop(键名, None)
    环境表.update(禁终端提示环境)
    仓库元目录 = Path(树根) / ".git"
    if 仓库元目录.is_dir():
        try:
            配置文本 = (仓库元目录 / "config").read_text(encoding="utf-8", errors="replace")
        except OSError:
            配置文本 = ""
        if re.search(r"^\s*bare\s*=\s*true\s*$", 配置文本, re.M):
            环境表["GIT_DIR"] = str(仓库元目录)
            环境表["GIT_WORK_TREE"] = str(树根)
    return 环境表

def 跑git(仓根, 参数表, 树根=None, 超时=超时秒) -> tuple:
    """跑一条查询类 git 子命令 ⇒ `(退出码, 输出文本)`；强制 `core.quotePath=false` 防中文路径假阴性。

    ★ 走 `只读缓存.跑只读命令`（实测 2026-10-08）：判据 ㊽ 的隔离样本组与主线程样本会把同一个
    只读问句（同一棵树 + 同一组 ref）问几十次，每次 fork 一个 git 是纯浪费，负载一高就把
    `--自检` 顶过五秒硬顶。缓存按**仓内容指纹**失效（见 `只读缓存.py`：ref / 索引正文一变即
    未命中，失败不缓存，不跨树串）。非只读子命令与读不出仓库元目录的一律现跑。
    """
    def 现跑(仓根, 参数表, 树根=None, 超时=超时秒):
        return 跑命令(["git", "-c", "core.quotePath=false"] + list(参数表),
                    cwd=str(树根 or 仓根), 超时秒数=超时, 子进程环境=git环境(树根 or 仓根))
    from .只读缓存 import 跑只读命令
    return 跑只读命令(现跑, 仓根, 参数表, 树根=树根, 超时=超时)

def 主干引用(仓根) -> str:
    """主干引用名：本地 `主干` 在就用它，否则退 `origin/主干`；都读不出 ⇒ 空串。"""
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "--verify", "--quiet", "主干"])
    if 退出码 == 0 and 输出文本.strip():
        return "主干"
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "--verify", "--quiet", "origin/主干"])
    if 退出码 == 0 and 输出文本.strip():
        return "origin/主干"
    return ""

def 相对主干位次(仓根, 引用, 树根=None) -> str:
    """`引用` 相对主干：`相同` / `落后主干 N（主干祖先）` / `领先主干 M（主干后代）` /
    `分叉：落后 N · 领先 M` / `未判：…`。"""
    基准 = 主干引用(仓根)
    引用 = str(引用 or "").strip()
    if not 基准 or not 引用:
        return "未判（主干或引用读不出）"
    退出码, 输出文本 = 跑git(仓根, ["rev-list", "--left-right", "--count",
                               "%s...%s" % (基准, 引用)], 树根=树根)
    if 退出码 != 0:
        return "未判（%s）" % 输出文本.strip()[-120:]
    段表 = 输出文本.split()
    if len(段表) < 2:
        return "未判（rev-list 读数异常）"
    if 段表[0] == "0" and 段表[1] == "0":
        return "相同"
    if 段表[1] == "0":
        return "落后主干 %s（主干祖先）" % 段表[0]
    if 段表[0] == "0":
        return "领先主干 %s（主干后代）" % 段表[1]
    return "分叉：落后 %s · 领先 %s" % (段表[0], 段表[1])

def 读开工表() -> tuple:
    """只读开工账本 ⇒ `(行表, 错误)`；库不在 / 读不动如实说，不假装空。"""
    try:
        库件 = 子目录路径(解析当前环境(), 子目录类别) / 库文件名
    except 无位置 as 错误:
        return [], "开工账本落点解析不出：%s" % 错误
    if not 库件.is_file():
        return [], "开工账本不在：%s" % 库件
    try:
        连接 = sqlite3.connect("file:%s?mode=ro" % 库件, uri=True)
        连接.row_factory = sqlite3.Row
        try:
            return [dict(数据行) for 数据行 in 连接.execute(
                "select 开工号, 状态, 工作树, 分支名 from 开工 order by 开工号")], ""
        finally:
            连接.close()
    except sqlite3.Error as 错误:
        return [], "开工账本读不动：%s" % 错误

def 收尾(行表) -> str:
    """拼回执并按 `字节上限` 截断（有界）—— 截了就如实说，不假装完整。"""
    正文 = "\n".join(行表)
    if len(正文) > 字节上限:
        正文 = 正文[:字节上限] + "\n…（已截断：回执超 %d 字，收窄参数再取）" % 字节上限
    return 正文

def 取记录条数(参数表, 默认=40, 硬顶=上限条数) -> int:
    取值 = 参数表.get("条数", 默认)
    if type(取值) is not int or 取值 < 1:
        raise 参数错("`条数` 要是正整数（收到 %r）" % (取值,))
    return min(取值, 硬顶)

def 取开工号(参数表) -> str:
    取值 = 参数表.get("开工ID") or ""
    if not isinstance(取值, str):
        raise 参数错("`开工ID` 要是字符串（收到 %r）" % (取值,))
    取值 = 取值.strip()
    if 取值 and not re.fullmatch(r"v1-[0-9]{6}", 取值):
        raise 参数错("`开工ID` 形状要是 `v1-` 加六位数字（收到 %r）" % (取值,))
    return 取值

def 拒未知(参数表, 键集) -> None:
    未定 = sorted(set(参数表) - set(键集) - {"操作"})
    if 未定:
        raise 参数错("未知键 %s；本操作只认 %s" % ("、".join(未定), "、".join(sorted(键集))))

def 建操作处理(处理, 并入开工=False):
    """把底层操作适配到统一处理签名，参数错仍按业务码返回。"""
    def 操作处理(开工号, 参数表, 仓根):
        实参 = dict(参数表)
        if 并入开工:
            实参["开工ID"] = 开工号
        elif 开工号:
            工作树 = 找工作树(仓根, 开工号)
            if 工作树 is None or not 工作树.is_dir():
                return 1, "开工 %s 的工作树不在" % 开工号
            仓根 = 工作树
        try:
            return 处理(仓根, 实参)
        except 参数错 as 错误:
            return 2, "参数拒绝：%s" % 错误
    return 操作处理

def _三方(仓根, 树根) -> tuple:
    """`git status --porcelain` ⇒ `(差异表, 错误)`（键：暂存 / 未暂存 / 未跟踪）。"""
    退出码, 输出文本 = 跑git(仓根, ["status", "--porcelain=v1", "-uall"], 树根=树根)
    if 退出码 != 0:
        return None, "git status 失败：%s" % 输出文本.strip()[-200:]
    差异 = {"暂存": [], "未暂存": [], "未跟踪": []}
    for 源码行 in 输出文本.splitlines():
        if len(源码行) < 4:
            continue
        标记 = 源码行[0]
        标签 = 源码行[1]
        路径 = 源码行[3:].strip().strip('"')
        if " -> " in 路径:
            路径 = 路径.split(" -> ")[-1].strip().strip('"')
        if 标记 == "?" or 标签 == "?":
            差异["未跟踪"].append(路径)
            continue
        if 标记 != " ":
            差异["暂存"].append(路径)
        if 标签 != " ":
            差异["未暂存"].append(路径)
    return 差异, ""

def _列件表(行表, 名称, 件表, 记录条数) -> None:
    for 路径 in 件表[:记录条数]:
        行表.append("  %s  %s" % (名称, 路径))
    if len(件表) > 记录条数:
        行表.append("  …（%s 还有 %d 件）" % (名称, len(件表) - 记录条数))

def _单树状态(仓根, 开工号, 记录条数) -> tuple:
    工作树 = 找工作树(仓根, 开工号)
    if 工作树 is None or not 工作树.is_dir():
        return 1, "开工 %s 的工作树不在（问 git 问不到）⇒ 不编路径" % 开工号
    行表 = ["【开工 %s 的工作树】%s" % (开工号, 工作树)]
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "--short", "HEAD"], 树根=工作树)
    行表.append("HEAD：%s" % (输出文本.strip() if 退出码 == 0 else "读不出"))
    退出码, 输出文本 = 跑git(仓根, ["branch", "--show-current"], 树根=工作树)
    行表.append("分支：%s" % (输出文本.strip() or "（游离）"))
    行表.append("相对主干：%s" % 相对主干位次(仓根, "HEAD", 树根=工作树))
    差异, 错误 = _三方(仓根, 工作树)
    if 错误:
        行表.append("三方一致：%s" % 错误)
    else:
        行表.append("三方一致：暂存 %d · 未暂存 %d · 未跟踪 %d"
                 % (len(差异["暂存"]), len(差异["未暂存"]), len(差异["未跟踪"])))
        _列件表(行表, "暂存", 差异["暂存"], 记录条数)
        _列件表(行表, "未暂存", 差异["未暂存"], 记录条数)
        _列件表(行表, "未跟踪", 差异["未跟踪"], 记录条数)
    # 278：未解冲突 / 合并中途是「看着干净、实则卡着」的最常见形态 ⇒ 直接点名，不让人靠猜。
    退出码, 输出文本 = 跑git(仓根, ["status", "--porcelain"], 树根=工作树)
    if 退出码 == 0:
        冲突行 = [冲突项 for 冲突项 in 输出文本.splitlines()
                if 冲突项[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")]
        if 冲突行:
            行表.append("★ 有未解冲突 %d 件 ⇒ 先解冲突再动：%s%s"
                     % (len(冲突行), 冲突行[0][3:], " …" if len(冲突行) > 1 else ""))
    退出码, 输出文本 = 跑git(仓根, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], 树根=工作树)
    if 退出码 == 0 and 输出文本.strip():
        行表.append("★ 正在合并中（MERGE_HEAD %s）⇒ 未提交前别当干净树用" % 输出文本.strip()[:8])
    return 0, 收尾(行表)

def _未合分支(仓根, 记录条数) -> list:
    """未合主干的分支（本地 `腿/*` 里领先主干或分叉的）—— 一次 `for-each-ref` 拿全，逐条不另起进程。"""
    退出码, 输出文本 = 跑git(仓根, ["for-each-ref", "--format=%(refname:short) %(ahead-behind:主干)",
                               "refs/heads/腿/"])
    if 退出码 != 0:
        return ["未合主干的分支：读不出（%s）" % 输出文本.strip()[-120:]]
    未合表 = []
    for 源码行 in 输出文本.splitlines():
        段表 = 源码行.split()
        if len(段表) < 3:
            continue
        if int(段表[1]) > 0:
            位次 = ("领先主干 %s" % 段表[1] if 段表[2] == "0"
                  else "分叉：落后 %s · 领先 %s" % (段表[2], 段表[1]))
            未合表.append((段表[0], 位次))
    行表 = ["未合主干的分支：%d 条（本地 腿/*）" % len(未合表)]
    for 名称, 位次 in 未合表[:记录条数]:
        行表.append("  %s  %s" % (名称, 位次))
    if len(未合表) > 记录条数:
        行表.append("  …（还有 %d 条）" % (len(未合表) - 记录条数))
    return 行表

def _全仓状态(仓根, 记录条数) -> tuple:
    基准 = 主干引用(仓根)
    行表 = ["主干引用：%s" % (基准 or "读不出")]
    if 基准:
        退出码, 输出文本 = 跑git(仓根, ["rev-parse", "--short", 基准])
        行表.append("主干 HEAD：%s" % (输出文本.strip() if 退出码 == 0 else "读不出"))
    差异, 错误 = _三方(仓根, 仓根)
    if 错误:
        行表.append("三方一致：%s" % 错误)
    else:
        行表.append("三方一致（主干工作树）：暂存 %d · 未暂存 %d · 未跟踪 %d"
                 % (len(差异["暂存"]), len(差异["未暂存"]), len(差异["未跟踪"])))
        _列件表(行表, "暂存", 差异["暂存"], 记录条数)
        _列件表(行表, "未暂存", 差异["未暂存"], 记录条数)
        _列件表(行表, "未跟踪", 差异["未跟踪"], 记录条数)
    行表 += _未合分支(仓根, 记录条数)
    记录表, 错误 = 读开工表()
    if 错误:
        行表.append("已释放但树仍在的开工：%s" % 错误)
    else:
        命中表 = [数据行 for 数据行 in 记录表
               if 数据行.get("状态") == "已释放"
               and Path(str(数据行.get("工作树") or "")).is_dir()]
        行表.append("已释放但树仍在的开工：%d 条" % len(命中表))
        for 数据行 in 命中表[:记录条数]:
            行表.append("  %s  树在 %s" % (数据行.get("开工号"), 数据行.get("工作树")))
    退出码, 输出文本 = 跑git(仓根, ["rev-list", "--left-right", "--count", "主干...origin/主干"])
    段表 = 输出文本.split() if 退出码 == 0 else []
    行表.append("远端关系：本地领先 %s · 本地落后 %s（主干 vs origin/主干）" % (段表[0], 段表[1])
             if len(段表) >= 2 else "远端关系：读不出（%s）" % 输出文本.strip()[-120:])
    行表.append("源库 blob 指纹（%s）：" % 源件路径)
    if 基准:
        退出码, 输出文本 = 跑git(仓根, ["rev-parse", "%s:%s" % (基准, 源件路径)])
        行表.append("  主干:  %s" % (输出文本.strip() if 退出码 == 0 else "读不出（该 ref 无此件）"))
    退出码, 输出文本 = 跑git(仓根, ["hash-object", "--", str(Path(仓根) / 源件路径)])
    行表.append("  盘上:  %s" % (输出文本.strip() if 退出码 == 0 else "读不出"))
    return 0, 收尾(行表)


def 仓状态(仓根, 参数表) -> tuple:
    拒未知(参数表, ("开工ID", "条数"))
    记录条数 = 取记录条数(参数表)
    开工号 = 取开工号(参数表)
    if 开工号:
        return _单树状态(仓根, 开工号, 记录条数)
    return _全仓状态(仓根, 记录条数)

def _体检_md账本(仓根, 记录条数) -> list:
    """全树 md 差文档账本：缺定义（盘上有、账本没定档）与幽灵（账本登记了、盘上不在）。"""
    库件 = Path(仓根) / 文档路径
    if not 库件.is_file():
        return ["md 差文档账本：账本不在（%s）⇒ 未判" % 文档路径]
    try:
        账本 = json.loads(库件.read_text(encoding="utf-8"))
    except (OSError, ValueError) as 错误:
        return ["md 差文档账本：账本读不动（%s）⇒ 未判" % 错误]
    名集 = {str(参项.get("路径", "")) for 参项 in 账本.get("件") or []}
    名表 = [str(参项.get("前缀", "")) for 参项 in 账本.get("按路径定档") or []]
    盘上表 = []
    根目录 = Path(仓根)
    for 目录路径, 目录表, 文件表 in os.walk(根目录):
        目录表[:] = [目录名 for 目录名 in 目录表 if 目录名 not in 跳过目录]
        for 名称 in 文件表:
            if 名称.endswith(".md"):
                盘上表.append(str((Path(目录路径) / 名称).relative_to(根目录)).replace(os.sep, "/"))
    全集 = set(盘上表)
    缺名 = [路径 for 路径 in 盘上表
           if 路径 not in 名集 and not any(路径.startswith(参名) for 参名 in 名表)]
    悬空 = [路径 for 路径 in 名集 if 路径 and 路径 not in 全集]
    行表 = ["md 差文档账本：盘上 %d 份 · 缺定义 %d · 幽灵登记 %d" % (len(盘上表), len(缺名), len(悬空))]
    for 路径 in 缺名[:记录条数]:
        行表.append("  缺定义  %s" % 路径)
    for 路径 in 悬空[:记录条数]:
        行表.append("  幽灵    %s" % 路径)
    return 行表

def _体检_mcp(仓根) -> list:
    """`.mcp.json` 指向的模块有没有 `__main__` —— 没有 ⇒ `python3 -m <模块>` 是空跑。"""
    库件 = Path(仓根) / 配置路径
    if not 库件.is_file():
        return ["MCP 配置指向模块的 __main__ 检查：配置不在（%s）" % 配置路径]
    try:
        配置 = json.loads(库件.read_text(encoding="utf-8"))
    except (OSError, ValueError) as 错误:
        return ["MCP 配置指向模块的 __main__ 检查：配置读不动（%s）" % 错误]
    行表 = ["MCP 配置指向模块的 __main__ 检查："]
    for 服务名, 节点 in (配置.get("mcpServers") or {}).items():
        参数表 = list((节点 or {}).get("args") or [])
        模块名 = 参数表[参数表.index("-m") + 1] if "-m" in 参数表 else ""
        if not 模块名:
            行表.append("  %s：args 里没有 `-m <模块>` ⇒ 未判" % 服务名)
            continue
        目录路径 = Path(仓根) / 模块名.replace(".", "/")
        入口 = 目录路径 / "__main__.py"
        模块件 = 目录路径.with_suffix(".py")
        if 目录路径.is_dir() or 入口.is_file():
            行表.append("  %s → `%s`：包（有 __main__.py=%s）" % (服务名, 模块名, 入口.is_file()))
        elif 模块件.is_file():
            标记值 = bool(主入口模式.search(模块件.read_text(encoding="utf-8", errors="replace")))
            行表.append("  %s → `%s`：%s" % (服务名, 模块名,
                      "有 __main__ 守卫" if 标记值 else "★ 无 __main__ 守卫 ⇒ `python3 -m %s` 是空跑" % 模块名))
        else:
            行表.append("  %s → `%s`：★ 模块件不在（%s）" % (服务名, 模块名, 模块件))
    return 行表

def _体检_工具面(仓根) -> list:
    """同步索引的 timeout 读数 + 修改器是否按后缀分流（两项环境体检读数）。"""
    行表 = ["同步索引的 timeout 检查（判据 ㊲：≤5 秒）："]
    for 相对路径 in (索引路径, "开发工具/代码地图.py"):
        件路径 = Path(仓根) / 相对路径
        命中表 = 超时参.findall(件路径.read_text(encoding="utf-8", errors="replace")) if 件路径.is_file() else None
        行表.append("  %s：%s" % (相对路径, "不在" if 命中表 is None
                 else "timeout 设置 %s" % ("、".join(命中表) or "无（不设超时，环境步）")))
    件路径 = Path(仓根) / "开发工具/MCP服务/修改.py"
    源码 = 件路径.read_text(encoding="utf-8", errors="replace") if 件路径.is_file() else ""
    按后缀 = ("按后缀分流" if ("扫局部绑定" in 源码 and "件后缀" in 源码) else "★ 未见按后缀分流") if 源码 else "件不在"
    return 行表 + ["修改器后缀分流：%s（开发工具/MCP服务/修改.py）" % 按后缀]

def 环境体检(仓根, 参数表) -> tuple:
    拒未知(参数表, ("条数",))
    记录条数 = 取记录条数(参数表)
    配置文本 = (Path(仓根) / ".git" / "config")
    行表 = ["core.bare：%s" % ("true" if re.search(r"^\s*bare\s*=\s*true\s*$",
                       配置文本.read_text(encoding="utf-8", errors="replace"), re.M) else "false")
           if 配置文本.is_file() else "core.bare：读不出（.git/config 不在）"]
    差异, 错误 = _三方(仓根, 仓根)
    if 错误:
        行表.append("未跟踪 md：%s" % 错误)
    else:
        名表 = [路径 for 路径 in 差异["未跟踪"] if 路径.endswith(".md")]
        行表.append("未跟踪 md：%d 份" % len(名表))
        for 路径 in 名表[:记录条数]:
            行表.append("  %s" % 路径)
    行表 += _体检_md账本(仓根, 记录条数)
    行表 += _体检_mcp(仓根)
    行表 += _体检_工具面(仓根)
    行表 += 读僵尸行(Path(仓根) / 源件路径, 记录条数)
    return 0, 收尾(行表)

工具名 = "v1_repo"
工具说明 = ("仓状态：一次给全（三方一致 · 未跟踪件 · 未合主干的分支 · 已释放但树仍在的开工 · "
        "远端关系 · 源库 blob 指纹）＋环境体检（core.bare · 未跟踪 md · md 差文档账本 · "
        ".mcp.json 指向模块有无 __main__ · 同步索引 timeout · 修改器后缀分流 · "
        "名册僵尸行（命名登记.出现次数=0 的陈旧行，由 落库 维护，只报告不删））。只读零写。"
        "给 `开工ID` 只看那条开工的工作树，不给=全仓。")
操作表 = {
    '仓状态': {"说明": '仓状态' , "需开工ID": False, "必需": [],
        "可选": ['条数'], "最短例": {'操作': '仓状态'},
        "处理": 建操作处理(仓状态, 并入开工=True)},
    '环境体检': {"说明": '环境体检' , "需开工ID": False, "必需": [],
        "可选": ['条数'], "最短例": {'操作': '环境体检'},
        "处理": 建操作处理(环境体检, 并入开工=False)},
}
