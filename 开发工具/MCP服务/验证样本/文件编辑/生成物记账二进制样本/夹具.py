# -*- coding: utf-8 -*-
"""夹具 —— 造一棵**真 git 仓** + 一本**隔离账本**（样本只在隔离夹具里跑，绝不开真账本）。

隔离靠运行数据根那个**覆盖变量**（`运行数据根.覆盖变量名`，不在本件重写它的字面）一个口：
账本路径由 `开工账本.开工账本路径` 解析运行数据根得出，本件把该变量指到夹具目录
⇒ `记生成物账` 用的就是夹具账本，真账本一个字节都不碰。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))   # 开发工具：取 MCP服务
from MCP服务 import 开工账本 as 账本    # noqa: E402
from 运行数据根 import 覆盖变量名        # noqa: E402 —— 覆盖变量名只从解析器那一份取

运行数据根环境变量 = 覆盖变量名
样本开工号 = "v1-900001"
样本模块名 = "子"
样本制品相对 = "扩展根目录/组合模块库/子/子.模块制品"
样本文本相对 = "扩展根目录/组合模块库/子/说明.md"
样本生成器名 = "生成器.py"
样本文本生成器名 = "文本生成器.py"
样本边界 = "扩展根目录/组合模块库"
样本模板 = "扩展根目录/组合模块库/<模块>/<模块>.模块制品"
旧字节 = b"CNWTEPRG\x00" + bytes(range(64))
新字节 = b"CNWTEPRG\x00" + bytes(range(200, 256))
夹具身份 = {"GIT_AUTHOR_NAME": "样本", "GIT_AUTHOR_EMAIL": "样本@example.invalid",
        "GIT_COMMITTER_NAME": "样本", "GIT_COMMITTER_EMAIL": "样本@example.invalid"}


def 跑git(仓根: Path, 参数表: list) -> tuple:
    """在夹具仓里跑一条 git ⇒ (退出码, 合并输出)。身份走环境变量，不读全局 git 配置。"""
    环境 = dict(os.environ)
    环境.update(夹具身份)
    回执 = subprocess.run(["git"] + 参数表, cwd=str(仓根), capture_output=True, text=True, env=环境)
    return 回执.returncode, (回执.stdout or "") + (回执.stderr or "")


def 写二进制(路径: Path, 字节: bytes) -> None:
    """写一个件（父目录一并建出）。"""
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_bytes(字节)


def 声明表(生成器名: str, 模板表=None, 输出表=None, 边界表=None) -> dict:
    """一条生成物声明（模板缺省 = 那条同名规则；实例表缺省 = 空）。"""
    return {
        "生成器": 生成器名,
        "边界": list(边界表 or [样本边界]),
        "二进制输出": list(输出表) if 输出表 else [],
        "二进制输出模板": [样本模板] if 模板表 is None else list(模板表),
    }


def 生成器源(声明表: dict, 制品路径: str = 样本制品相对, 字节: bytes = 新字节,
        退出码: int = 0) -> str:
    """生成器源：带一行机器可读声明，正文把制品写成**新字节**（真变化），末行给退出码。"""
    return ("# -*- coding: utf-8 -*-\n"
            "# 生成物声明：" + json.dumps(声明表, ensure_ascii=False) + "\n"
            "import pathlib\n"
            "目标 = pathlib.Path(%r)\n"
            "目标.parent.mkdir(parents=True, exist_ok=True)\n"
            "目标.write_bytes(%r)\n"
            "raise SystemExit(%d)\n" % (制品路径, 字节, 退出码))


def 文本生成器源() -> str:
    """文本产物的老机制：产物**自身**带头标（生成物 / 禁手改 / 生成器：<路径>）。"""
    return ("# -*- coding: utf-8 -*-\n"
            "import pathlib\n"
            "目标 = pathlib.Path(%r)\n"
            "目标.write_text('# 生成物\\n禁手改\\n生成器：%s\\n', encoding='utf-8')\n"
            % (样本文本相对, 样本文本生成器名))


def 造隔离仓(夹具根: Path, 声明: dict, 制品路径: str = 样本制品相对,
         退出码: int = 0) -> Path:
    """造一棵真 git 仓：带声明的生成器 + 已提交的旧制品 + 文本件（基线已 commit）。"""
    样本仓根 = 夹具根 / "仓"
    if 样本仓根.exists():
        shutil.rmtree(样本仓根)
    样本仓根.mkdir(parents=True)
    写二进制(样本仓根 / 样本制品相对, 旧字节)
    (样本仓根 / 样本文本相对).write_text("# 旧说明\n", encoding="utf-8")
    (样本仓根 / 样本生成器名).write_text(生成器源(声明, 制品路径, 新字节, 退出码), encoding="utf-8")
    (样本仓根 / 样本文本生成器名).write_text(文本生成器源(), encoding="utf-8")
    跑git(样本仓根, ["init", "-q"])
    跑git(样本仓根, ["add", "-A"])
    提交码, 提交输出 = 跑git(样本仓根, ["commit", "-qm", "夹具基线"])
    if 提交码 != 0:
        raise RuntimeError("夹具建不起来（git commit 退出码 %d）：%s" % (提交码, 提交输出))
    return 样本仓根


def 造隔离账本(夹具根: Path, 样本仓根: Path, 认领表: dict = None) -> str:
    """把运行数据根指到夹具里，登记一条开工 + 认领 ⇒ 开工号（真账本一个字节都不碰）。"""
    os.environ[运行数据根环境变量] = str(夹具根 / "运行数据根")
    if 认领表 is None:
        认领表 = {样本制品相对: "夹具指纹", 样本文本相对: "夹具指纹"}
    连接 = 账本.连账本()
    try:
        账本.登记开工(连接, 样本开工号, "样本：声明式二进制产物记账", "样本/夹具", str(样本仓根))
        账本.认领文件(连接, 样本开工号, 认领表)
    finally:
        连接.close()
    return 样本开工号


def 读账本改动(夹具根: Path) -> list:
    """隔离账本里本开工的改动行 ⇒ `[dict]`（样本用它判「记了几件 / 写后指纹」）。"""
    连接 = 账本.连账本()
    try:
        return 账本.读改动(连接, 样本开工号)
    finally:
        连接.close()


def 造目录链接(样本仓根: Path, 仓外目录: Path) -> None:
    """把样本制品的父目录换成**符号链接**指向 `仓外目录`（父核探针 P4 的形状）。

    目录本身是链接 ⇒ `is_symlink()` 只看末段看不见它；写入经它落到仓外。
    """
    制品路径 = 样本仓根 / 样本制品相对
    仓外目录.mkdir(parents=True, exist_ok=True)
    (仓外目录 / 制品路径.name).write_bytes(旧字节)
    shutil.rmtree(制品路径.parent)
    制品路径.parent.symlink_to(仓外目录, target_is_directory=True)


def 清理夹具(夹具根: Path) -> None:
    """删掉夹具（含隔离账本）；不碰真账本。"""
    shutil.rmtree(夹具根, ignore_errors=True)
