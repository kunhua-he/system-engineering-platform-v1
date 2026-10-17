# -*- coding: utf-8 -*-
"""`--编译自检`：一条命令把 Rust 面与 Python 面的静态检查各跑一遍（用户主动命令）。

依据：华哥原话「编译器运行一个命令，就能快速静态编译，可以知道哪里报错」——
本仓此前没有这个入口。本件是它唯一的实现；`主流程.py` 只加一个分支调用它。

**两面**：

  · **Rust 面**：在仓根跑 `cargo check --workspace --locked`，覆盖 workspace 全部成员。
    成员清单**实测**取自 `cargo metadata --no-deps --format-version 1`（不照抄任何数字：
    workspace 成员会变，写死数字就是第二个事实源）。诊断按 cargo 的 `--> 路径:行:列` 定位
    逐条打印 —— 本件用 `--message-format=json` 读同一份 span（`file_name` / `line_start` /
    `column_start`），比逐行解析人读文本稳。只把 `level=error` 当失败。
  · **Python 面**：先找现成 lint 配置（`ruff.toml` / `.ruff.toml` / `pyproject.toml` /
    `setup.cfg` / `tox.ini` / `.flake8`，从仓根逐级上溯）。**一件都没有就不自造** ——
    如实报「未做」并标成下一轮（自造一套 lint 规则 = 造第二个事实源，本仓禁止）。

**超时**：本命令是**用户主动命令**，墙钟可以 > 5 秒（同 `--承重证明` 的先例：5 秒硬顶约束的是
判据内部起的子进程，不是用户主动命令）⇒ **不给 cargo 套 5 秒超时**。暖缓存约几十毫秒，
冷编译（`target/` 被清之后）可能远超 5 秒，套 5 秒会把正常的冷编译判成「超时失败」。耗时如实报出。

退出码：Rust 面有 error ⇒ 1；只有 warning ⇒ 0（warning 条数照实报）；cargo 起不来 ⇒ 2。
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

# 仓内 lint 配置的候选件名（**只查，不造**）：一件都没有 ⇒ Python 面如实报「未做」。
配置候选 = ("ruff.toml", ".ruff.toml", "pyproject.toml", "setup.cfg", "tox.ini", ".flake8")
# 具名件（本身就是 lint 配置）· 容器件（`pyproject.toml` 一类）要真含一段 lint 配置才算 ——
# 一个空 `pyproject.toml` 不是 lint 配置，拿它当配置去跑就是自造规则。
直认件名 = ("ruff.toml", ".ruff.toml", ".flake8")
lint段标记 = (
    "[tool.ruff", "[tool.flake8", "[tool.pylint",
    "[flake8]", "[pylint]", "[tool:pylint]", "[tool:flake8]",
)


def _跑(命令: list, 仓根: Path) -> tuple:
    """跑一条命令 ⇒ `(退出码, 标准输出, 标准错误)`；**不设超时**（理由见文件头「超时」段）。"""
    try:
        判定汇总 = subprocess.run(
            命令, cwd=str(仓根), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as 错误:
        return 127, "", f"命令起不来（{type(错误).__name__}：{错误}）"
    return 判定汇总.returncode, 判定汇总.stdout or "", 判定汇总.stderr or ""


def 读工作区成员(仓根: Path) -> tuple:
    """`cargo metadata --no-deps` ⇒ `([(包名, 清单路径)], 错误或 None)`。"""
    退出码, 标准输出, 标准错误 = _跑(
        ["cargo", "metadata", "--no-deps", "--format-version", "1"], 仓根
    )
    if 退出码 != 0:
        return [], f"cargo metadata 退出码 {退出码}：{标准错误.strip()[:200]}"
    try:
        配置表 = json.loads(标准输出)
    except json.JSONDecodeError as 错误:
        return [], f"cargo metadata 输出解不开（{错误}）"
    return [
        (str(包项.get("name")), str(包项.get("manifest_path")))
        for 包项 in 配置表.get("packages") or []
    ], None


def _包名(包标识: str) -> str:
    """`path+file:///…#v1-adapter@0.1.0` ⇒ `v1-adapter`（取 `#` 之后、`@` 之前那一段）。"""
    尾段 = str(包标识 or "").rsplit("#", 1)[-1]
    return 尾段.rsplit("@", 1)[0] or str(包标识 or "")


def _取位置(消息: dict) -> tuple:
    """诊断消息 ⇒ `(文件, 行, 列)`：优先主 span，没有就取第一个带文件名的 span。

    cargo 人读输出里 `--> 路径:行:列` 那一段，就是这里三个字段的渲染形 —— 读 JSON 面拿到
    同一份 span，比逐行解析人读文本稳（人读文本的换行与缩进会变，JSON 的字段名不会）。
    """
    片段表 = 消息.get("spans") or []
    主片段 = next((片段项 for 片段项 in 片段表 if 片段项.get("is_primary")), None)
    if 主片段 is None:
        主片段 = next((片段项 for 片段项 in 片段表 if 片段项.get("file_name")), None)
    if 主片段 is None:
        return "", 0, 0
    return (
        str(主片段.get("file_name") or ""),
        int(主片段.get("line_start") or 0),
        int(主片段.get("column_start") or 0),
    )


def 解析诊断(标准输出: str) -> tuple:
    """cargo 的 JSON 流 ⇒ `(错误表, 警告表, 制品包集)`。

    每条诊断 = `{包, 文件, 行, 列, 级别, 代号, 文案}`。只认 `level=error` 为失败；
    `level=warning` 照实计数但**不改退出码**（仓内现有一条无害 warning 是已知现状）。
    """
    错误表, 警告表, 制品包集 = [], [], set()
    for 行文本 in 标准输出.splitlines():
        行文本 = 行文本.strip()
        if not 行文本:
            continue
        try:
            配置表 = json.loads(行文本)
        except json.JSONDecodeError:
            continue  # 不是 JSON 行（人读摘要一类）⇒ 跳过
        因由 = 配置表.get("reason")
        if 因由 == "compiler-artifact":
            制品包集.add(_包名(配置表.get("package_id")))
            continue
        if 因由 != "compiler-message":
            continue
        消息 = 配置表.get("message") or {}
        级别 = str(消息.get("level") or "")
        if 级别 not in ("error", "warning"):
            continue
        件路径, 行号, 列号 = _取位置(消息)
        单条诊断 = {
            "包": _包名(配置表.get("package_id")),
            "文件": 件路径, "行": 行号, "列": 列号,
            "级别": 级别,
            "代号": str((消息.get("code") or {}).get("code") or ""),
            "文案": str(消息.get("message") or "").strip(),
        }
        (错误表 if 级别 == "error" else 警告表).append(单条诊断)
    return 错误表, 警告表, 制品包集


def 跑Rust面(仓根: Path) -> dict:
    """Rust 面：workspace 全量 `cargo check` ⇒ 读数（成员 / 制品 / 错误 / 警告 / 说明）。

    `--locked` 与仓内别处一致；若它因锁文件缺失跑不动，**如实说明并退回不带 `--locked`**，
    不静默改口径。
    """
    成员表, 元数据错误 = 读工作区成员(仓根)
    命令 = ["cargo", "check", "--workspace", "--locked", "--message-format=json"]
    退出码, 标准输出, 标准错误 = _跑(命令, 仓根)
    说明 = ""
    锁相关 = ("--locked" in 标准错误) or ("lock file" in 标准错误) or ("Cargo.lock" in 标准错误)
    if 退出码 != 0 and 锁相关:
        命令 = [命令行参数 for 命令行参数 in 命令 if 命令行参数 != "--locked"]
        退出码, 标准输出, 标准错误 = _跑(命令, 仓根)
        说明 = "`--locked` 跑不动（锁文件缺失或过期）⇒ 改用 `cargo check --workspace`（不带 --locked）"
    错误表, 警告表, 制品包集 = 解析诊断(标准输出)
    return {
        "成员表": 成员表, "元数据错误": 元数据错误,
        "错误表": 错误表, "警告表": 警告表, "制品包集": 制品包集,
        "退出码": 退出码, "标准错误": 标准错误, "说明": 说明,
        "命令": " ".join(命令),
    }


def 是lint配置(节点件: Path, 件名: str) -> bool:
    """这一件**真**是 lint 配置吗 —— 具名件（`ruff.toml` 一类）直认；容器件要真含一段 lint 配置。

    一个空 `pyproject.toml`（只有构建元数据、没有 lint 段）不是 lint 配置 ⇒ 不当配置。
    """
    if 件名 in 直认件名:
        return True
    try:
        源文本 = 节点件.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(段标记 in 源文本 for 段标记 in lint段标记)


def 找Python配置(起点: Path) -> list:
    """从起点逐级上溯找**现成** lint 配置 ⇒ 命中的绝对路径表（一件都没有 ⇒ 空表）。"""
    命中 = []
    当前路径 = 起点.resolve()
    while True:
        for 件名 in 配置候选:
            节点件 = 当前路径 / 件名
            if 节点件.is_file() and 是lint配置(节点件, 件名):
                命中.append(str(节点件))
        if 当前路径.parent == 当前路径:
            break
        当前路径 = 当前路径.parent
    return 命中


def 跑Python面(仓根: Path) -> dict:
    """Python 面：先找现成 lint 配置；**没有就不自造**（自造规则 = 第二个事实源）。

    有配置时按 `ruff check` 跑（本件只认 ruff 这一条现成跑法）；ruff 不在 PATH 就如实报「未做」。
    """
    配置表 = 找Python配置(仓根)
    if not 配置表:
        return {"状态": "未做", "配置表": [], "输出": "", "原因": "仓内无 lint 配置，不自造配置"}
    退出码, 标准输出, 标准错误 = _跑(["ruff", "check", "."], 仓根)
    if 退出码 == 127:
        return {"状态": "未做", "配置表": 配置表, "输出": 标准错误,
                "原因": "发现了配置，但 ruff 起不来"}
    return {"状态": "已跑", "配置表": 配置表, "退出码": 退出码,
            "输出": (标准输出 + 标准错误).strip(), "原因": "按现成配置跑 ruff check"}


def _打印Rust面(读数: dict) -> tuple:
    """打印 Rust 面读数 ⇒ `(成员名表, 报错包集, 错误表)`。"""
    成员名表 = [标识符 for 标识符, _路径 in 读数["成员表"]]
    print(f"  workspace 成员（实测 cargo metadata --no-deps）：{len(成员名表)} 个")
    for 标识符 in 成员名表:
        print(f"    - {标识符}")
    if 读数["元数据错误"]:
        print(f"  ！成员清单读不到：{读数['元数据错误']}")
    制品名表 = sorted(读数["制品包集"])
    print(f"  本次实际产出制品的包（实测）：{len(制品名表)} 个：{' · '.join(制品名表) or '（无）'}")
    多出 = sorted(set(制品名表) - set(成员名表))
    if 多出:
        print(
            f"  ★ 与成员数不一致：多出 {len(多出)} 个非成员包（{' · '.join(多出)}）——"
            f"它们是 workspace 成员的 path 依赖，`cargo check --workspace` 会一并检查 ⇒"
            f"「实际被检查的包」多于「workspace 成员数」。"
        )
    elif not 制品名表:
        print(
            "  ★ 暖缓存下 cargo 可能只回放诊断、不再报 `compiler-artifact` ⇒ 制品数为 0"
            "不代表没检查；覆盖由 `--workspace` 与上面的成员清单背书。"
        )
    错误表, 警告表 = 读数["错误表"], 读数["警告表"]
    报错包集 = {单条诊断["包"] for 单条诊断 in 错误表}
    if 错误表:
        print(f"  error {len(错误表)} 条（{len(报错包集)} 个 crate）：")
        for 单条诊断 in 错误表:
            代号 = f"[{单条诊断['代号']}]" if 单条诊断["代号"] else ""
            print(f"    ✗ {单条诊断['包']} ｜ {单条诊断['文件']}:{单条诊断['行']}:{单条诊断['列']} ｜ error{代号}: {单条诊断['文案']}")
    else:
        print("  error 0 条")
    if 警告表:
        print(f"  warning {len(警告表)} 条（不判失败，如实报出）：")
        for 单条诊断 in 警告表:
            代号 = f"[{单条诊断['代号']}]" if 单条诊断["代号"] else ""
            print(f"    - {单条诊断['包']} ｜ {单条诊断['文件']}:{单条诊断['行']}:{单条诊断['列']} ｜ warning{代号}: {单条诊断['文案']}")
    else:
        print("  warning 0 条")
    if 读数["退出码"] != 0 and not 错误表:
        print(
            f"  ！cargo 退出码 {读数['退出码']}，但没解析到 error 诊断；"
            f"标准错误尾部：{读数['标准错误'].strip()[-300:]}"
        )
    if 读数["说明"]:
        print(f"  说明：{读数['说明']}")
    return 成员名表, 报错包集, 错误表


def 编译自检(仓根: Path) -> int:
    """`--编译自检`：一次覆盖 Rust（workspace 全量 cargo check）与 Python（现成 lint 配置）两面。"""
    起始 = time.perf_counter()
    print("编译自检（用户主动命令：墙钟可 > 5 秒，耗时如实报出）")
    print("")
    print("【Rust 面】workspace 全量 cargo check")
    读数 = 跑Rust面(仓根)
    print(f"  命令：{读数['命令']}")
    成员名表, 报错包集, 错误表 = _打印Rust面(读数)
    print("")
    print("【Python 面】仓内 lint 配置扫描（只查，不造）")
    面读数 = 跑Python面(仓根)
    if 面读数["配置表"]:
        print(f"  找到配置 {len(面读数['配置表'])} 件：{' · '.join(面读数['配置表'])}")
        print(f"  状态：{面读数['状态']}（{面读数['原因']}）")
        if 面读数["输出"]:
            print(f"  输出尾部：{面读数['输出'][-500:]}")
    else:
        print("  查过（仓根并逐级上溯）：" + " · ".join(配置候选))
        print("  结论：一件都没有")
    print("")
    print("【汇总】")
    总数 = len(成员名表)
    报错数 = len(报错包集)
    通过数 = max(总数 - 报错数, 0)
    报错位置 = "；".join(
        f"{单条诊断['包']} ｜ {单条诊断['文件']}:{单条诊断['行']}:{单条诊断['列']} ｜ {单条诊断['文案']}" for 单条诊断 in 错误表
    )
    print(
        f"  Rust 编译：{总数} 个 crate，{通过数} 个通过，{报错数} 个报错"
        + (f"（{报错位置}）" if 报错位置 else "")
    )
    if 面读数["状态"] == "未做" and not 面读数["配置表"]:
        print("  Python 静态检查：未做（仓内无 lint 配置，不自造配置）")
    else:
        print(f"  Python 静态检查：{面读数['状态']}（{面读数['原因']}）")
    耗时毫秒 = int((time.perf_counter() - 起始) * 1000)
    print(f"  耗时：{耗时毫秒} ms")
    if 读数["退出码"] == 127:
        return 2
    return 1 if 错误表 else 0
