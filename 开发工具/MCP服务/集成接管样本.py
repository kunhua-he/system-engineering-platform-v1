# -*- coding: utf-8 -*-
"""集成接管样本 —— 「合并冲突保留的集成树」受控接管的**正反**样本（临时裸主仓 + 真 git + 临时账本）。

**为什么挂 `--自测`、不挂 `MCP服务.py --自检`**：闭环要起真 git 裸主仓、走 `--恢复现场` 五步
（约 3 秒），而判据 ㊽ 对 `--自检` 的子进程是 **5 秒硬顶**（`判据_MCP自检.py`）—— `--自检` 基线已
3.4 秒，装不下。`--自测` 是环境步、预算宽松（同 `--承重证明`）⇒ 挂 `自检_集成接管.py`。

仓一个字节都不改：账本连口走替身、索引器走替身；夹具是系统临时目录里的真 git 裸主仓，跑完删净。
"""
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from . import 合主干编排 as 编排
from . import 开工账本 as 账本
from . import 修改, 集成接管
from . import 集成接管删名样本

样本开工号 = "v1-999001"
样本分支 = "腿/" + 样本开工号
接管号前缀 = "接管开工号 "


def _跑git(仓根, *参数表):
    回执 = subprocess.run(["git", *参数表], cwd=str(仓根), capture_output=True, text=True,
                       env=编排.干净环境(), timeout=5)
    assert 回执.returncode == 0, (参数表, 回执.stdout, 回执.stderr)
    return 回执.stdout.strip()


def _建规则库(路径):
    路径.parent.mkdir(parents=True, exist_ok=True)
    连接 = sqlite3.connect(str(路径))
    连接.execute("create table 命名登记(名字 text primary key, 语义 text, 模式 text, 来源 text, 状态 text)")
    连接.execute("create table 命名例外(名字 text primary key, 说明 text)")
    连接.execute("create table 规则(编号 integer primary key, 类 text, 名 text, 内容 text, 依据 text)")
    连接.execute("insert into 规则 values (1, '样本', '语义', '基值', '')")
    连接.commit()
    连接.close()


def _建假信息核心(路径):
    """迷你 `信息核心.py`：认 `记规则`（源库重放用）与 `建源库` / `核源库`（重抽用），真改库 ⇒ 读得到。"""
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(
        "import sqlite3, sys\n"
        "from pathlib import Path\n"
        "参表 = sys.argv[1:]\n"
        "子命令 = 参表[0] if 参表 else ''\n"
        "if 子命令 == '建源库':\n"
        "    连接 = sqlite3.connect(str(Path('开发工具/信息核心/信息核心.db')))\n"
        "    连接.execute('create table if not exists 未完成 (号 integer primary key, 缺什么 text, 落点 text, 验证命令 text)')\n"
        "    连接.commit()\n"
        "    连接.close()\n"
        "    print('建源库 ok')\n"
        "    raise SystemExit(0)\n"
        "if 子命令 == '核源库':\n"
        "    print('核源库 ok')\n"
        "    raise SystemExit(0)\n"
        "键值 = {}\n"
        "键 = None\n"
        "for 项 in 参表[1:]:\n"
        "    if 项.startswith('--'):\n"
        "        键 = 项[2:]\n"
        "        键值[键] = ''\n"
        "    elif 键:\n"
        "        键值[键] = 项\n"
        "if 子命令 != '记规则':\n"
        "    raise SystemExit(3)\n"
        "连接 = sqlite3.connect(str(Path('开发工具/信息核心/信息核心.db')))\n"
        "连接.execute('update 规则 set 类=?, 名=?, 内容=?, 依据=? where 编号=?',\n"
        "           (键值.get('类', ''), 键值.get('名', ''), 键值.get('内容', ''),\n"
        "            键值.get('依据', ''), int(键值.get('编号', '0') or 0)))\n"
        "连接.commit()\n"
        "连接.close()\n"
        "print('记规则 ok')\n", encoding="utf-8")


def _建夹具(临时根: Path) -> dict:
    主目录, 腿树, 集成树 = 临时根 / "主目录", 临时根 / "腿目录", 临时根 / "集成目录"
    主目录.mkdir()
    for 参数表 in (("init", "-b", "主干"), ("config", "user.name", "样本"),
               ("config", "user.email", "fixture@example.invalid")):
        _跑git(主目录, *参数表)
    (主目录 / "README.md").write_text("系统工程平台 V1\n", encoding="utf-8")
    (主目录 / "AGENTS.md").write_text("样本\n", encoding="utf-8")
    (主目录 / "样本.txt").write_text("基线\n", encoding="utf-8")
    门禁件 = 主目录 / "构建装配/一键验证/闸0.py"
    门禁件.parent.mkdir(parents=True)
    门禁件.write_text("print('腿闸通过')\n", encoding="utf-8")
    _建规则库(主目录 / "开发工具/信息核心/信息核心.db")
    _建假信息核心(主目录 / "开发工具/信息核心/信息核心.py")
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "基线")
    _跑git(主目录, "worktree", "add", "-b", 样本分支, str(腿树))
    (腿树 / "样本.txt").write_text("腿改\n", encoding="utf-8")
    with sqlite3.connect(腿树 / "开发工具/信息核心/信息核心.db") as 连接:
        连接.execute("update 规则 set 内容='腿值' where 编号=1")
    _跑git(腿树, "add", ".")
    _跑git(腿树, "commit", "-m", "腿成果")
    (主目录 / "样本.txt").write_text("主改\n", encoding="utf-8")
    _跑git(主目录, "add", ".")
    _跑git(主目录, "commit", "-m", "主改")
    _跑git(主目录, "worktree", "add", "-b", "集成/" + 样本开工号, str(集成树), "主干")
    回执 = subprocess.run(["git", "merge", "--no-commit", "--no-ff", 样本分支], cwd=str(集成树),
                      capture_output=True, text=True, env=编排.干净环境(), timeout=5)
    assert 回执.returncode != 0 and "CONFLICT" in (回执.stdout + 回执.stderr), (回执.stdout, 回执.stderr)
    钩子 = 主目录 / ".git/hooks/pre-commit"
    钩子.write_text("#!/bin/sh\nexit 0\n")
    钩子.chmod(0o755)
    账本路径 = 临时根 / "账本.db"
    连接 = sqlite3.connect(str(账本路径))
    for 建表行 in 账本.建表语句:
        连接.execute(建表行)
    连接.execute("insert into 开工 (开工号, 工作内容, 分支名, 工作树, 状态, 开工时间) "
             "values (?,?,?,?,?,?)", (样本开工号, "样本腿", 样本分支, str(腿树), "已释放", "2026-10-07"))
    连接.commit()
    连接.close()
    return {"主目录": 主目录, "腿树": 腿树, "集成树": 集成树, "账本路径": 账本路径}


def _开账(账本路径):
    连接 = sqlite3.connect(str(账本路径))
    连接.row_factory = sqlite3.Row
    return 连接


def _开工行数(账本路径):
    连接 = _开账(账本路径)
    try:
        return 连接.execute("select count(*) from 开工").fetchone()[0]
    finally:
        连接.close()


def _查状态(账本路径, 开工号):
    连接 = _开账(账本路径)
    try:
        源码行 = 连接.execute("select 状态 from 开工 where 开工号 = ?", (开工号,)).fetchone()
        return 源码行["状态"] if 源码行 else ""
    finally:
        连接.close()


def _读规则内容(库路径):
    连接 = sqlite3.connect("file:%s?mode=ro" % 库路径, uri=True)
    try:
        return 连接.execute("select 内容 from 规则 where 编号=1").fetchone()[0]
    finally:
        连接.close()


def _接管号(回执):
    for 文本行 in 回执.splitlines():
        if 文本行.startswith(接管号前缀):
            return 文本行.split("（")[0][len(接管号前缀):].strip()
    return ""


def _跑夹具():
    """搭夹具、换账本连口与索引器替身 ⇒ 样本表。异常也在内部收尾删净。"""
    临时根 = Path(tempfile.mkdtemp(prefix="v1集成接管自检-"))
    真连, 真索引 = 账本.连账本, 修改.同步索引
    try:
        夹具 = _建夹具(临时根)
        主目录, 腿树, 集成树 = 夹具["主目录"], 夹具["腿树"], 夹具["集成树"]
        账本路径 = 夹具["账本路径"]
        账本.连账本 = lambda: _开账(账本路径)
        修改.同步索引 = lambda _根: (0, "样本：索引器跳过")
        样本表 = _反向无现场(主目录, 集成树, 账本路径)
        样本表 += _反向核验重放(集成树)
        样本表 += 集成接管删名样本.验删名重放()
        绑定表, 接管号 = _正向绑定(主目录, 集成树, 账本路径)
        样本表 += 绑定表
        样本表 += _恢复收口(主目录, 腿树, 集成树, 账本路径, 接管号)
    finally:
        账本.连账本, 修改.同步索引 = 真连, 真索引
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表


def 接管样本(仓根, 工具表) -> list:
    """集成接管的绑定档 + 拒绝档 + 端到端闭环 ⇒ 样本表（挂 `一键验证.py --自测`）。"""
    return _跑夹具()


def _反向无现场(主目录, 集成树, 账本路径) -> list:
    样本表 = []
    开工行数 = _开工行数(账本路径)
    退出码, 回执 = 集成接管.派发(主目录, "v1-999777")
    样本表.append(("接管集成 反向（没有集成现场）：退出码 %d（期望 1）· 说「没有已知集成现场」%s · 账本开工行 %d→%d"
              % (退出码, "是" if "没有已知集成现场" in 回执 else "否",
                 开工行数, _开工行数(账本路径)),
            退出码 == 1 and "没有已知集成现场" in 回执 and _开工行数(账本路径) == 开工行数))
    退出码, 回执 = 集成接管.派发(主目录, "瞎号")
    样本表.append(("接管集成 反向（开工号形状非法）：退出码 %d（期望 2）· 账本开工行未涨 %s"
              % (退出码, "是" if _开工行数(账本路径) == 开工行数 else "否"),
            退出码 == 2 and _开工行数(账本路径) == 开工行数))
    退出码, 行表 = 集成接管.暂存接管成果(主目录, 集成树)
    未合并 = 集成接管.未合并件(集成树)[1]
    样本表.append(("暂存接管成果 反向（现场未被正式接管）：退出码 %d（期望 1）· 未合并件仍在 %s"
              % (退出码, "是" if 未合并 else "否"),
            退出码 == 1 and bool(未合并) and any("未被正式接管" in 回执行 for 回执行 in 行表)))
    return 样本表


def _反向核验重放(集成树) -> list:
    """源库重放**未完成**（库还是主干值）⇒ `核验重放` 显式拒 —— 不静默跳过丢腿侧动作。"""
    库件 = 集成树 / "开发工具/信息核心/信息核心.db"
    连接 = sqlite3.connect(str(库件))
    连接.execute("update 规则 set 内容='主干值' where 编号=1")
    连接.commit()
    连接.close()
    动作表 = [{"表": "规则", "键": (1,), "列名表": ["编号", "类", "名", "内容", "依据"],
            "腿值": (1, "样本", "语义", "腿值", "")}]
    退出码, 行表 = 集成接管.核验重放(集成树, 动作表)
    return [("核验重放 反向（源库重放未完成）：退出码 %d（期望 1）· 说「显式拒」%s"
             % (退出码, "是" if any("显式拒" in 回执行 for 回执行 in 行表) else "否"),
             退出码 == 1 and any("显式拒" in 回执行 for 回执行 in 行表))]


def _正向绑定(主目录, 集成树, 账本路径) -> tuple:
    """接管绑成正式开工 ⇒ 拒绝档 ⇒ `v1_edit` 真改真账 ⇒ 暂存 ⇒ (样本表, 接管号)。"""
    样本表 = []
    退出码, 回执 = 集成接管.派发(主目录, 样本开工号)
    接管号 = _接管号(回执)
    样本表.append(("接管集成 正向：退出码 %d（期望 0）· 回接管开工号 %s · 分支 集成/%s"
              % (退出码, 接管号 or "（无）", 样本开工号),
            退出码 == 0 and 接管号.startswith("v1-") and "集成/" + 样本开工号 in 回执))
    退出码, 回执 = 集成接管.派发(主目录, 样本开工号)
    样本表.append(("接管集成 反向（重复绑定）：退出码 %d（期望 1）· 说「已被 **%s** 正式接管」%s"
              % (退出码, 接管号, "是" if "正式接管" in 回执 else "否"),
            退出码 == 1 and "正式接管" in 回执 and 接管号 in 回执))
    样本表 += _反向未认领(主目录, 集成树, 接管号)
    样本表 += _反向指纹漂移(主目录, 集成树, 接管号)
    冲突全文 = (集成树 / "样本.txt").read_text(encoding="utf-8")
    退出码, 回执 = 修改.派发({"开工ID": 接管号, "改动表": [
        {"路径": "样本.txt", "功能": 1, "旧内容": 冲突全文, "新内容": "主改+腿改\n"}]}, 主目录)
    改后 = (集成树 / "样本.txt").read_text(encoding="utf-8")
    样本表.append(("v1_edit 正向（接管开工号解冲突）：退出码 %d（期望 0）· 件已改 %s · 回执说「改了 1/1 条」%s"
              % (退出码, "是" if 改后 == "主改+腿改\n" else "否",
                 "是" if "改了 1/1 条" in 回执 else "否"),
            退出码 == 0 and 改后 == "主改+腿改\n" and "改了 1/1 条" in 回执))
    退出码, 行表 = 集成接管.暂存接管成果(主目录, 集成树)
    样本表.append(("暂存接管成果 正向：退出码 %d（期望 0）· 未合并件已清 %s"
              % (退出码, "是" if not 集成接管.未合并件(集成树)[1] else "否"),
            退出码 == 0 and not 集成接管.未合并件(集成树)[1]))
    return 样本表, 接管号


def _恢复收口(主目录, 腿树, 集成树, 账本路径, 接管号) -> list:
    """端到端：`--恢复现场` 经三件套 + 源库重放保双方 ⇒ 清树 ⇒ 接管开工翻已释放。"""
    开工记录 = {"状态": "已释放", "工作树": str(腿树), "分支名": 样本分支}
    with mock.patch.object(编排, "_读开工记录", return_value=开工记录):
        恢复码, 恢复报告 = 编排.派发(样本开工号, False, 主目录, 操作="恢复现场")
    树在 = 集成树.exists()
    主库 = 主目录 / "开发工具/信息核心/信息核心.db"
    样本表 = [("恢复现场 正向（接管成果经三件套 + 源库重放保双方）：退出码 %d（期望 0）· 集成树已清 %s · "
            "主干件=主改+腿改 %s · 源库腿侧动作保住（内容=%s）"
            % (恢复码, "是" if not 树在 else "否",
               "是" if (主目录 / "样本.txt").read_text(encoding="utf-8") == "主改+腿改\n" else "否",
               _读规则内容(主库)),
            恢复码 == 0 and not 树在 and _读规则内容(主库) == "腿值"
            and (主目录 / "样本.txt").read_text(encoding="utf-8") == "主改+腿改\n")]
    样本表.append(("接管开工随现场收口翻「已释放」：%s（%s）"
              % (_查状态(账本路径, 接管号), 接管号),
            _查状态(账本路径, 接管号) == "已释放"))
    return 样本表


def _反向未认领(主目录, 集成树, 接管号) -> list:
    原样 = (集成树 / "AGENTS.md").read_text(encoding="utf-8")
    退出码, 回执 = 修改.派发({"开工ID": 接管号, "改动表": [
        {"路径": "AGENTS.md", "功能": 1, "旧内容": "样本\n", "新内容": "被改\n"}]}, 主目录)
    未动 = (集成树 / "AGENTS.md").read_text(encoding="utf-8") == 原样
    return [("v1_edit 反向（接管开工改未认领件）：退出码 %d（期望 3）· 件没动 %s · 说「不在开工 %s 的认领集」%s"
             % (退出码, "是" if 未动 else "否", 接管号, "是" if "认领集" in 回执 else "否"),
             退出码 == 3 and 未动 and "认领集" in 回执)]


def _反向指纹漂移(主目录, 集成树, 接管号) -> list:
    件路径 = 集成树 / "样本.txt"
    原冲突全文 = 件路径.read_text(encoding="utf-8")
    件路径.write_text("绕过 v1_edit 直改\n", encoding="utf-8")
    退出码, 回执 = 修改.派发({"开工ID": 接管号, "改动表": [
        {"路径": "样本.txt", "功能": 1, "旧内容": "绕过 v1_edit 直改\n", "新内容": "主改+腿改\n"}]}, 主目录)
    漂移未写 = 件路径.read_text(encoding="utf-8") == "绕过 v1_edit 直改\n"
    样本表 = [("v1_edit 反向（盘上指纹漂移）：退出码 %d（期望 3）· 拒写 %s · 说「绕过 MCP」%s"
            % (退出码, "是" if 漂移未写 else "否", "是" if "绕过 MCP" in 回执 else "否"),
            退出码 == 3 and 漂移未写 and "绕过 MCP" in 回执)]
    件路径.write_text(原冲突全文, encoding="utf-8")
    return 样本表
