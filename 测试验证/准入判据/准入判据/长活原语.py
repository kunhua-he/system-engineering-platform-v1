"""长活原语考题 —— 真编一道 Rust 考题、真跑它，给 `跨语言适配/边界协议/边界协议.md`
§四 判据 7–10 出**真读数**（长活原语要的那件）。

**为什么本 runner 能在「不许跑 cargo」的纪律下出读数**：`rustc --test <单文件>` 不需要 cargo
—— 不读工作区、不解析依赖、不抢构建锁；实测编译 ~0.2 s、跑 ~0.5 s，都在 5 秒硬顶内。
两档照 `构建装配/上线切换/构建制品.py` 的形状：编归环境步（`--预编`），跑归命令体
（缺失 / 与源不符即 fail-closed 指路）。

**考题本体**（`扩展根目录/原子支持库/编译器支持库/src/测试用例/长活原语考题.rs`）含一稿
**真实的「扩展自持任务表」**：句柄由表分配 · 取消是表的终态 · 超时给结构化码，全在**扩展侧**；
内核不持表（判据 10）。

本模块只做三件事：编（`预编`）· 跑并把三道断言映射成判据号（`判定`）· 自测（`自测`）。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import 世界

考题相对路径 = "扩展根目录/原子支持库/编译器支持库/src/测试用例/长活原语考题.rs"
缓存目录相对 = "构建环境/构建缓存/长活原语考题"
内核扫描面相对 = "运行内核"

# 判据 10 认的词：内核一旦持一张任务注册表，至少命中其一。
任务表词 = ("任务表", "任务注册表", "任务表项", "任务句柄表")

# ≤5 秒硬顶；单位进名字（判据 ㊲ 认这个形）。
编译超时毫秒 = 4000
跑测超时毫秒 = 4000

# Rust 侧测试名 ⇒ 判据号（三道考题各一条；名字逐字对齐考题源）。
测名到判据 = {
    "判据7_句柄过边界不失真_八字节原值逐字节不变": 7,
    "判据8_立刻返回_第一次调用一秒内拿到句柄": 8,
    "判据9_取消后结构化失败_得到码而不是panic": 9,
}


def 找仓根() -> Path:
    """仓根的**唯一实现**在 `世界.py`（2026-09-30 收口：本件原先自带一份「契约声明 且
    扩展装载」的**硬写串**搜索）。本模块各口按 `Path` 收 ⇒ 只把它的 `str` 转成 `Path`。"""
    return Path(世界.找仓根())


def 考题路径(根目录: Path) -> Path:
    return 根目录 / 考题相对路径


def 缓存目录(根目录: Path) -> Path:
    return 根目录 / 缓存目录相对


def 源指纹(根目录: Path) -> str:
    """考题源的 sha256 —— 戳与它比对，源变了即判「产物与源不符」。"""
    节点件 = 考题路径(根目录)
    if not 节点件.is_file():
        return ""
    return hashlib.sha256(节点件.read_bytes()).hexdigest()


def 读戳(根目录: Path) -> dict:
    节点件 = 缓存目录(根目录) / "戳.json"
    try:
        return json.loads(节点件.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def 预编(根目录: Path) -> int:
    """环境步：`rustc --test` 编**单文件**考题 ⇒ 缓存目录里的二进制 + 源指纹戳。

    **不碰 cargo 锁**（不读工作区、不解析依赖）：这是本 runner 能在「不许跑 cargo」的纪律下
    出读数的唯一原因。编译耗时照实报（它在本命令的墙钟里）。
    """
    缓存 = 缓存目录(根目录)
    缓存.mkdir(parents=True, exist_ok=True)
    二进制 = 缓存 / "考题"
    区间起点 = time.monotonic()
    结果 = subprocess.run(
        # `--edition 2024` 与扩展 crate 的 `Cargo.toml` 逐字一致（否则「真跑」跑的不是它的真版本）。
        ["rustc", "--test", "--edition", "2024", str(考题路径(根目录)), "-o", str(二进制)],
        cwd=str(根目录),
        capture_output=True,
        text=True,
        timeout=编译超时毫秒 / 1000,
    )
    耗时毫秒 = int((time.monotonic() - 区间起点) * 1000)
    if 结果.returncode != 0:
        sys.stderr.write(f"✗ 考题编不出来（rustc 退出码 {结果.returncode}）：\n{结果.stderr.strip()}\n")
        return 1
    (缓存 / "戳.json").write_text(
        json.dumps(
            {"源指纹": 源指纹(根目录), "二进制": 二进制.name, "编译毫秒": 耗时毫秒},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"环境步：单文件考题已编（rustc --test · 耗时 {耗时毫秒} ms · 不碰 cargo 锁）")
    return 0


def 解测果(输出: str) -> dict:
    """从测试输出里解出 `测试名 ⇒ 通过与否`（只认 `test <名> ... ok|FAILED` 这一形）。"""
    项表 = {}
    for 源码行 in 输出.splitlines():
        净文本 = 源码行.strip()
        if not 净文本.startswith("test ") or " ... " not in 净文本:
            continue
        名称, _, 尾部 = 净文本[5:].partition(" ... ")
        项表[名称.strip()] = 尾部.strip().startswith("ok")
    return 项表


def 扫内核任务表(根目录: Path) -> list:
    """判据 10：`运行内核/` 下 0 处任务表（状态在扩展侧，内核不持）。返回命中处。"""
    命中 = []
    扫描面 = 根目录 / 内核扫描面相对
    if not 扫描面.is_dir():
        return 命中
    for 节点件 in sorted(扫描面.rglob("*.rs")):
        try:
            文本 = 节点件.read_text(encoding="utf-8")
        except OSError:
            continue
        for 关键词 in 任务表词:
            if 关键词 in 文本:
                命中.append(f"{节点件.relative_to(根目录)}::{关键词}")
    return 命中


def 判定(根目录: Path) -> int:
    """命令体：跑已编好的考题，把三道断言映射成 判据 7 · 8 · 9，另静态扫 判据 10。"""
    指纹戳 = 读戳(根目录)
    二进制 = 缓存目录(根目录) / str(指纹戳.get("二进制") or "考题")
    if not 指纹戳 or not 二进制.is_file():
        print("✗ 产物缺失：先跑环境步 —— python3 测试验证/准入判据/长活原语.py --预编")
        return 1
    if 指纹戳.get("源指纹") != 源指纹(根目录):
        print("✗ 产物与源不符（考题被改过，戳是旧的）：先跑 --预编 刷新")
        return 1
    try:
        结果 = subprocess.run(
            [str(二进制), "--test-threads=1"],
            cwd=str(根目录),
            capture_output=True,
            text=True,
            timeout=跑测超时毫秒 / 1000,
        )
    except (OSError, subprocess.TimeoutExpired) as 错误:
        print(f"✗ 考题跑不起来：{错误}")
        return 1
    测果 = 解测果(结果.stdout + 结果.stderr)
    行表 = []
    失败 = 0
    for 测名, 号值 in sorted(测名到判据.items(), key=lambda 一项: 一项[1]):
        过了 = 测果.get(测名)
        if 过了 is None:
            行表.append((号值, "未判", f"考题里没有这条测试：{测名}"))
            失败 += 1
        elif 过了:
            行表.append((号值, "通过", 测名))
        else:
            行表.append((号值, "失败", f"{测名} 红了"))
            失败 += 1
    命中 = 扫内核任务表(根目录)
    if 命中:
        行表.append((10, "失败", "运行内核/ 下出现任务表：" + " · ".join(命中)))
        失败 += 1
    else:
        行表.append((10, "通过", "运行内核/ 下 0 处任务表（状态在扩展侧）"))
    print("─" * 78)
    print("边界协议 §四 判据 7–10 真读数（长活原语考题 runner · 真编真跑）")
    for 号值, 结论, 证据 in 行表:
        标记 = {"通过": "✓", "失败": "✗", "未判": "○"}[结论]
        print(f"  {标记} 判据 {号值} ｜ {结论} ｜ {证据}")
    过了数 = sum(1 for _, 结论, _ in 行表 if 结论 == "通过")
    print(f"考题真跑退出码 {结果.returncode} · 通过 {过了数} / {len(行表)}")
    return 0 if 失败 == 0 else 1


def 自测() -> int:
    """runner 自身的**成对样本**（正向 + 反向）—— 证明这些口不是空转。

    三组：① `解测果` 认得出 ok 与 FAILED ② `扫内核任务表` 植入即抓得到 · 干净即 0
    ③ `源指纹` 对源的变化敏感（不敏感 ⇒ 戳形同虚设）。
    """
    错误 = []
    项表 = 解测果("test 通过样例 ... ok\ntest 失败样例 ... FAILED\n")
    if 项表.get("通过样例") is not True or 项表.get("失败样例") is not False:
        错误.append("解测果 把 ok / FAILED 判反了")
    with tempfile.TemporaryDirectory() as 临时:
        根目录 = Path(临时)
        (根目录 / 内核扫描面相对).mkdir(parents=True)
        if 扫内核任务表(根目录):
            错误.append("干净树上报出了任务表（假红）")
        (根目录 / 内核扫描面相对 / "植入.rs").write_text("static mut 任务表: u32 = 0;\n", encoding="utf-8")
        if not 扫内核任务表(根目录):
            错误.append("植入了任务表却抓不到（漏判）")
    with tempfile.TemporaryDirectory() as 临时:
        根目录 = Path(临时)
        节点件 = 考题路径(根目录)
        节点件.parent.mkdir(parents=True)
        节点件.write_text("// 旧内容\n", encoding="utf-8")
        旧指纹 = 源指纹(根目录)
        节点件.write_text("// 新内容\n", encoding="utf-8")
        if not 旧指纹 or 旧指纹 == 源指纹(根目录):
            错误.append("源指纹对源变化不敏感（戳形同虚设）")
    if 错误:
        print("✗ runner 自测红：" + "；".join(错误))
        return 1
    print("✓ runner 自测全过（解测果 · 内核零任务表 · 源指纹 三组正/反向样本）")
    return 0
