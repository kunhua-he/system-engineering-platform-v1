# -*- coding: utf-8 -*-
"""三件已授权旧稿的短期保护、无覆盖取回与同步后结清。"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import tempfile
from pathlib import Path

from 开发工具.运行数据根 import 子目录路径, 解析当前环境
from .合主干有界跑 import 干净环境
from .恢复主目录编排 import 算指纹值

授权路径 = (
    "开发工具/MCP服务/认领隔离.py",
    "开发工具/MCP服务/认领样本.py",
    "构建装配/一键验证/一键验证/自检_MCP事务.py",
)


class 保全拒绝(Exception):
    """前置核验失败。"""


def 核条件(成立, 说明):
    if not 成立:
        raise 保全拒绝(说明)


def 跑主仓(主目录, 命令表, 允许失败=False):
    回执 = subprocess.run(["git", "--git-dir", str(主目录 / ".git"),
        "--work-tree", str(主目录), *命令表], cwd=主目录,
        capture_output=True, env=干净环境(), timeout=5)
    if not 允许失败:
        核条件(回执.returncode == 0, "Git查询失败：" + 回执.stderr.decode(errors="replace"))
    return 回执


def 核普通件(件路径, 基准路径, 允许缺失=False):
    核条件(件路径.is_relative_to(基准路径), "路径在树外")
    for 路径 in (件路径, *件路径.parents):
        if 路径 == 基准路径:
            break
        核条件(not 路径.is_symlink(), "拒绝符号链接：%s" % 路径)
    核条件(件路径.resolve().is_relative_to(基准路径.resolve()), "解析路径在树外")
    if 允许缺失 and not 件路径.exists():
        return
    核条件(stat.S_ISREG(件路径.lstat().st_mode), "不是普通文件：%s" % 件路径)


def 读替代记录(替代开工):
    库路径 = 子目录路径(解析当前环境(), "数据库") / "开工账本.db"
    核条件(库路径.is_file(), "正式开工账本缺失")
    with sqlite3.connect(库路径.as_uri() + "?mode=ro", uri=True) as 连接:
        连接.row_factory = sqlite3.Row
        替代记录 = 连接.execute("select * from 开工 where 开工号=?", (替代开工,)).fetchone()
        核条件(替代记录 is not None, "替代开工无正式账本证明")
        return dict(替代记录)


def 核基本表(参数表):
    for 名称 in ("期望提交", "替代提交"):
        核条件(isinstance(参数表.get(名称), str) and
            re.fullmatch(r"[0-9a-f]{40}", 参数表[名称]), "须完整提交：" + 名称)
    核条件(re.fullmatch(r"v1-[0-9]{6}", str(参数表.get("替代开工", ""))), "替代开工形状错误")
    核条件(参数表.get("确认无独有成果") is True, "须显式确认无独有成果")
    授权件表 = 参数表.get("授权件表")
    核条件(isinstance(授权件表, list) and len(授权件表) == 3, "必须恰为三件授权路径")
    核条件(all(isinstance(条目项, dict) for 条目项 in 授权件表), "授权件表形状错误")
    核条件({条目项.get("路径") for 条目项 in 授权件表} == set(授权路径), "陌生或重复路径")
    核条件(all(re.fullmatch(r"[0-9a-f]{40}", str(条目项.get("期望指纹", "")))
        for 条目项 in 授权件表), "须逐件完整blob指纹")
    return sorted(授权件表, key=lambda 条目项: 条目项["路径"])


def 核主身份(仓根, 参数表):
    回执 = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=仓根, capture_output=True, env=干净环境(), timeout=5)
    核条件(回执.returncode == 0, "公共Git目录定位失败")
    元目录 = Path(os.fsdecode(回执.stdout).strip()).resolve()
    主目录 = 元目录.parent
    核条件(元目录.name == ".git" and 元目录.is_dir() and Path(仓根).resolve() != 元目录,
        "不是公共主仓")
    核条件("系统工程平台 V1" in (主目录 / "README.md").read_text(encoding="utf-8")
        and (主目录 / "AGENTS.md").is_file(), "主仓身份不符")
    核条件(跑主仓(主目录, ["symbolic-ref", "HEAD"]).stdout.strip() == "refs/heads/主干".encode(),
        "公共HEAD不是主干")
    替代记录 = 读替代记录(参数表["替代开工"])
    核条件(替代记录["状态"] == "已释放" and 替代记录.get("释放时间"), "替代开工未正式释放")
    核条件(替代记录["分支名"] == "腿/" + 参数表["替代开工"], "替代账本分支不符")
    核条件(跑主仓(主目录, ["rev-parse", "--verify", "refs/heads/" + 替代记录["分支名"]]).stdout.strip()
        == 参数表["替代提交"].encode(), "替代支线提交不符")
    核条件(替代记录.get("工作树"), "账本缺少替代工作树")
    回执 = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=替代记录["工作树"], capture_output=True, env=干净环境(), timeout=5)
    核条件(回执.returncode == 0 and Path(os.fsdecode(回执.stdout).strip()).resolve() == 元目录,
        "替代账本工作树不属当前公共仓")
    for 路径 in 授权路径:
        输出字节 = 跑主仓(主目录, ["ls-tree", "-z", 参数表["替代提交"], "--", 路径]).stdout
        核条件(输出字节.startswith((b"100644 blob ", b"100755 blob ")) and
            输出字节.endswith(b"\t" + 路径.encode() + b"\0"), "替代成果未提交普通文件：" + 路径)
    return 主目录


def 核索引(主目录, 提交):
    核条件(跑主仓(主目录, ["diff", "--cached", "--ita-visible-in-index", "--quiet", 提交, "--"], True).returncode == 0,
        "主index与提交不符")
    核条件(not (主目录 / ".git/index.lock").exists(), "主index正在写入")


def 核旧件(主目录, 授权件表):
    原件表 = []
    for 条目项 in 授权件表:
        路径 = 条目项["路径"]
        件路径 = 主目录 / 路径
        核普通件(件路径, 主目录)
        核条件(not 跑主仓(主目录, ["ls-files", "-z", "--", 路径]).stdout, "已tracked：" + 路径)
        核条件(跑主仓(主目录, ["check-ignore", "--quiet", "--", 路径], True).returncode == 1,
            "被忽略或查询失败：" + 路径)
        核条件(跑主仓(主目录, ["ls-files", "--others", "--exclude-standard", "-z", "--", 路径]).stdout
            == 路径.encode() + b"\0", "不是精确未跟踪文件：" + 路径)
        旧字节 = 件路径.read_bytes()
        核条件(算指纹值(旧字节) == 条目项["期望指纹"], "指纹漂移：" + 路径)
        原件表.append((路径, 旧字节, stat.S_IMODE(件路径.stat().st_mode)))
    return 原件表


def 保全落点(主目录, 参数表, 授权件表):
    绑定清单 = {名称: 参数表[名称] for 名称 in ("期望提交", "替代开工", "替代提交")}
    绑定清单.update({"主仓": str(主目录), "授权件表": 授权件表})
    清单字节 = json.dumps(绑定清单, ensure_ascii=False, sort_keys=True).encode()
    保全编号 = hashlib.sha256(清单字节).hexdigest()
    备份基准 = 子目录路径(解析当前环境(), "临时件")
    备份目录 = 备份基准 / ("主仓三件保全-" + 保全编号)
    核条件(not 备份目录.is_symlink() and 备份目录.resolve().is_relative_to(备份基准.resolve()),
        "保全目录越界")
    return 备份目录, 清单字节


def 核副本表(备份目录, 清单字节, 授权件表):
    清单路径 = 备份目录 / "清单.json"
    核普通件(清单路径, 备份目录)
    核条件(清单路径.read_bytes() == 清单字节, "保全清单绑定不符")
    核条件({路径.name for 路径 in 备份目录.iterdir()} ==
        {"清单.json", *(条目项["期望指纹"] for 条目项 in 授权件表)}, "保全含未知文件")
    副本表 = []
    for 条目项 in 授权件表:
        副本路径 = 备份目录 / 条目项["期望指纹"]
        核普通件(副本路径, 备份目录)
        旧字节 = 副本路径.read_bytes()
        核条件(算指纹值(旧字节) == 条目项["期望指纹"], "副本指纹漂移")
        副本表.append((条目项["路径"], 旧字节, stat.S_IMODE(副本路径.stat().st_mode)))
    return 副本表


def 移开件(件路径):
    件路径.unlink()


def 执行保护(主目录, 备份目录, 清单字节, 授权件表, 原件表):
    备份目录.parent.mkdir(parents=True, exist_ok=True)
    备份目录.mkdir(mode=0o700)
    for 路径, 旧字节, 模式值 in 原件表:
        副本路径 = 备份目录 / 算指纹值(旧字节)
        with 副本路径.open("xb") as 句柄:
            句柄.write(旧字节)
            句柄.flush()
            os.fsync(句柄.fileno())
        副本路径.chmod(模式值)
    with (备份目录 / "清单.json").open("xb") as 句柄:
        句柄.write(清单字节)
        句柄.flush()
        os.fsync(句柄.fileno())
    核副本表(备份目录, 清单字节, 授权件表)
    核条件(核旧件(主目录, 授权件表) == 原件表, "复制期间原件漂移")
    for 路径, 旧字节, 模式值 in 原件表:
        核普通件(主目录 / 路径, 主目录)
        核条件((主目录 / 路径).read_bytes() == 旧字节, "移开前漂移：" + 路径)
        移开件(主目录 / 路径)
    return "三件已保护；可取回现场：%s" % 备份目录


def 执行取回(主目录, 副本表):
    for 路径, 旧字节, 模式值 in 副本表:
        件路径 = 主目录 / 路径
        核普通件(件路径, 主目录, True)
        if 件路径.exists():
            核条件(件路径.read_bytes() == 旧字节 and
                stat.S_IMODE(件路径.stat().st_mode) == 模式值, "取回期间出现新正本，拒绝覆盖")
            continue
        with tempfile.NamedTemporaryFile(dir=件路径.parent, prefix=".v1取回-", delete=False) as 句柄:
            临时路径 = Path(句柄.name)
            try:
                句柄.write(旧字节)
                句柄.flush()
                os.fsync(句柄.fileno())
                临时路径.chmod(模式值)
                核条件(临时路径.read_bytes() == 旧字节, "写回核验失败；副本保留")
                os.link(临时路径, 件路径)
            finally:
                临时路径.unlink(missing_ok=True)
    return "三件已取回，副本保留；未覆盖任何新正本"


def 核同步(主目录, 参数表, 授权件表):
    合入提交 = 参数表.get("合入提交", "")
    核条件(re.fullmatch(r"[0-9a-f]{40}", 合入提交), "结清须完整合入提交")
    核条件(跑主仓(主目录, ["rev-parse", "refs/heads/主干"]).stdout.strip() == 合入提交.encode(),
        "主干不是指定合入提交")
    核条件(跑主仓(主目录, ["merge-base", "--is-ancestor", 参数表["替代提交"], 合入提交], True).returncode == 0,
        "替代成果尚未合入")
    核索引(主目录, 合入提交)
    for 条目项 in 授权件表:
        路径 = 条目项["路径"]
        件路径 = 主目录 / 路径
        核普通件(件路径, 主目录)
        提交记录 = 跑主仓(主目录, ["ls-tree", "-z", 合入提交, "--", 路径]).stdout
        核条件(提交记录 == 跑主仓(主目录, ["ls-tree", "-z", 参数表["替代提交"], "--", 路径]).stdout,
            "正本提交与替代成果不符")
        模式, 类型, 指纹值 = 提交记录.split(b"\t", 1)[0].split()
        核条件(算指纹值(件路径.read_bytes()).encode() == 指纹值 and
            模式 == (b"100755" if 件路径.stat().st_mode & 0o111 else b"100644"), "正本盘上未同步")
        核条件(跑主仓(主目录, ["ls-files", "-s", "-z", "--", 路径]).stdout ==
            模式 + b" " + 指纹值 + b" 0\t" + 路径.encode() + b"\0", "正本index未同步")


def 保全操作(参数表, 仓根):
    备份目录 = None
    try:
        授权件表 = 核基本表(参数表)
        主目录 = 核主身份(仓根, 参数表)
        备份目录, 清单字节 = 保全落点(主目录, 参数表, 授权件表)
        操作名 = 参数表.get("操作", "保护")
        核条件(操作名 in ("保护", "取回", "结清"), "操作只收保护/取回/结清")
        执行开关 = 参数表.get("执行") is True
        def 核与操作():
            if 操作名 == "结清":
                核同步(主目录, 参数表, 授权件表)
            else:
                核条件(跑主仓(主目录, ["rev-parse", "主干"]).stdout.strip() == 参数表["期望提交"].encode(),
                    "主干漂移")
                核索引(主目录, 参数表["期望提交"])
            if 操作名 == "保护":
                核条件(not 备份目录.exists(), "已有保全现场，禁止覆盖")
                原件表 = 核旧件(主目录, 授权件表)
                return 执行保护(主目录, 备份目录, 清单字节, 授权件表, 原件表) if 执行开关 else "只读预检通过，零写"
            副本表 = 核副本表(备份目录, 清单字节, 授权件表)
            if 操作名 == "取回":
                for 路径, 旧字节, 模式值 in 副本表:
                    件路径 = 主目录 / 路径
                    核普通件(件路径, 主目录, True)
                    核条件(not 跑主仓(主目录, ["ls-files", "-z", "--", 路径]).stdout, "取回拒绝覆盖tracked")
                    核条件(not 件路径.exists() or (件路径.read_bytes() == 旧字节 and
                        stat.S_IMODE(件路径.stat().st_mode) == 模式值), "取回拒绝覆盖新正本")
                return 执行取回(主目录, 副本表) if 执行开关 else "取回预检通过，零写"
            if 执行开关:
                for 条目项 in 授权件表:
                    (备份目录 / 条目项["期望指纹"]).unlink()
                (备份目录 / "清单.json").unlink()
                备份目录.rmdir()
            return "结清完成" if 执行开关 else "结清预检通过，零写"
        if not 执行开关:
            return 0, 核与操作()
        with (主目录 / ".git" / "合主干.lock").open("a+") as 句柄:
            fcntl.flock(句柄, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return 0, 核与操作()
    except (保全拒绝, OSError, ValueError, TypeError, KeyError, sqlite3.Error, subprocess.SubprocessError) as 错误:
        return 2, "拒绝或操作中断：%s；原件或已核副本保留，可取回现场：%s" % (错误, 备份目录)


def 命令入口(命令行参数, 仓根):
    解析器 = argparse.ArgumentParser(description="三件旧稿受控保护；默认dry-run零写")
    解析器.add_argument("--操作", choices=("保护", "取回", "结清"), default="保护")
    解析器.add_argument("--计划", help="JSON对象：期望提交/替代开工/替代提交/授权件表/确认无独有成果；结清另给合入提交")
    解析器.add_argument("--执行", action="store_true")
    解析器.add_argument("--自测", action="store_true")
    命令行 = 解析器.parse_args(命令行参数)
    if 命令行.自测:
        from .保全主目录样本 import 跑样本
        return 跑样本()
    if not 命令行.计划:
        解析器.error("需要 --计划")
    try:
        参数表 = json.loads(Path(命令行.计划).read_text(encoding="utf-8"))
        核条件(isinstance(参数表, dict), "计划须对象")
        参数表.update({"操作": 命令行.操作, "执行": 命令行.执行})
        退出码, 说明 = 保全操作(参数表, 仓根)
    except (OSError, ValueError, 保全拒绝) as 错误:
        退出码, 说明 = 2, str(错误)
    print(说明)
    return 退出码
