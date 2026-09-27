# -*- coding: utf-8 -*-
"""第 1、2 步 —— 编扩展 cdylib · 装到扫描点（暂存目录 + 指向它的扩展根声明）。

转调纪律见 `起演示.py` 模块注释：编 dylib **转调** `构建制品.py::扩展产物`（进程内 import
后调函数本体，cargo 命令一行不重写）；网关可执行件**转调产物**，只在缺失时同形补编一条。
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from 常量 import 仓根, 扩展根声明源, 网关产物, 暂存根  # noqa: E402


def 载入构建制品():
    """进程内加载 `构建装配/上线切换/构建制品.py`（转调它的扩展产物节点，不复制它的 cargo 命令）。"""
    清单 = 仓根 / "构建装配" / "上线切换" / "构建制品.py"
    规格 = importlib.util.spec_from_file_location("构建制品", 清单)
    模 = importlib.util.module_from_spec(规格)
    规格.loader.exec_module(模)
    return 模


def 符号导出读数(库: Path) -> dict:
    """`nm -gU` 取全局导出，验接缝符号 `GetPlatformInfo` 在（那次实证的同一验法）。"""
    成 = subprocess.run(["/usr/bin/nm", "-gU", str(库)], capture_output=True, text=True)
    if 成.returncode != 0:
        return {"命令成了": False, "接缝符号在": False, "说明": 成.stderr.strip()[:200]}
    导出 = [行.split()[-1] for 行 in 成.stdout.splitlines() if 行.strip()]
    # macOS 的 C 符号带前导下划线（_GetPlatformInfo），Linux 不带 —— 两种都认。
    在 = any(名.lstrip("_") == "GetPlatformInfo" for 名 in 导出)
    return {"命令成了": True, "接缝符号在": 在, "全局导出数": len(导出)}


def 清扫残部() -> list:
    """扫掉**本演示自己**早先失败留下的残部：旧暂存目录 + 可能还活着的旧演示网关。

    匹配只按旧暂存目录的**完整独有路径**（每个 run 一个，路径里带时间与 pid）——
    常驻网关的命令行里没有这个路径，碰不到它。只扫地皮**十分钟前**的旧目录：
    更新的可能是另一场正在跑的演示，不碰。
    """
    清了的 = []
    if not 暂存根.is_dir():
        return 清了的
    for 旧 in sorted(暂存根.iterdir()):
        if not 旧.is_dir():
            continue
        if time.time() - 旧.stat().st_mtime < 600:
            continue
        成 = subprocess.run(["/usr/bin/pkill", "-f", str(旧)], capture_output=True, text=True)
        清了的.append("{}（pkill 退出码 {}）".format(旧.name, 成.returncode))
        shutil.rmtree(旧, ignore_errors=True)
    return 清了的


def 搭暂存(库: Path) -> Path:
    """搭这次的暂存目录：网关 + 扩展树 + 指向扩展树的扩展根声明（每次跑全新一份）。"""
    暂存 = 暂存根 / "演示-{}-pid{}".format(time.strftime("%Y%m%d-%H%M%S"), os.getpid())
    扩展树 = 暂存 / "扩展"
    (扩展树 / "原子支持库" / "编译器支持库").mkdir(parents=True)
    (扩展树 / "组合模块库").mkdir()
    (扩展树 / "技能封装库").mkdir()
    # 扩展目录内**恰好一个**可装载库文件（扫描判据①：按后缀找，不按名字找）。
    shutil.copy2(库, 扩展树 / "原子支持库" / "编译器支持库" / "编译器支持库.dylib")
    shutil.copy2(网关产物, 暂存 / "网关")
    (暂存 / "网关").chmod(0o755)

    源 = json.loads(扩展根声明源.read_text(encoding="utf-8"))
    声明 = dict(源)
    声明["说明"] = (
        "演示暂存副本（在系统临时目录，仓内一字未改）：种类[].目录 改指本次暂存下编出的扩展，"
        "形状与 扩展装载/扩展根声明.json 一致。生成器：构建装配/演示/起演示.py"
    )
    声明["种类"] = [
        dict(类, 目录=str(扩展树 / Path(类.get("目录", "")).name)) for 类 in 源.get("种类", [])
    ]
    (暂存 / "扩展根声明.json").write_text(
        json.dumps(声明, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 暂存


def 备网关产物() -> dict:
    """网关可执行件**转调启动网关.rs 的产物**：产物在就直接用；缺失才按 构建制品.py::main
    里那一处同形补编（逐字同参；该步骤无节点可转调 ⇒ 待收编，见模块注释）。"""
    if 网关产物.is_file():
        return {"转调产物": True, "路径": str(网关产物), "字节数": 网关产物.stat().st_size, "现编": False}
    环境 = dict(os.environ)
    成 = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--release", "-p", "v1-gateway",
         "--example", "启动网关"],
        cwd=str(仓根), capture_output=True, text=True, env=环境,
    )
    if 成.returncode != 0 or not 网关产物.is_file():
        raise RuntimeError(
            "网关产物缺失且补编失败（退出码 {}）：{}\n{}".format(
                成.returncode, 成.stdout[-500:], 成.stderr[-500:]
            )
        )
    return {"转调产物": True, "路径": str(网关产物), "字节数": 网关产物.stat().st_size, "现编": True}
