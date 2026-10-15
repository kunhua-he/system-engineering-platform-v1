"""采集材料 —— 四类正式材料的取数（源码指纹 · 契约指纹 · 制品指纹 · 工具链）。

四类**各有真源**，不许在本件里另造一套口径：
  · 源码指纹 = 制品清单的 `构建指纹`（装配器按「逐源件 sha256」算出来的那一串）
  · 契约指纹 = `契约声明/冻结登记.json` 冻结项逐条的 `形状指纹`（按名称排序后整串哈希）
  · 制品指纹 = 制品清单的 `文件清单`（逐件 sha256，按路径排序后整串哈希）
  · 工具链   = 构建工具链 + 构建平台 + 依赖版本（`Cargo.lock` 的 sha256）

缺任何一类 ⇒ 该键为空串（阻断口据此报缺；本件不抛、不降级）。
"""

import hashlib
import json
import subprocess

from .常量 import 仓根, 冻结登记相对路径, 制品产物目录, 制品清单名, 依赖锁件相对路径


def _整串哈希(行表: list) -> str:
    return hashlib.sha256("\n".join(行表).encode("utf-8")).hexdigest()


def 取制品清单() -> tuple:
    """最新一份制品（按清单件修改时刻）的清单 ⇒ `(制品清单, 制品目录, 未采原因)`。"""
    if not 制品产物目录.is_dir():
        return None, None, "制品产物目录不在（%s）—— 还没构建过制品" % 制品产物目录
    候选表 = [
        制品目录 for 制品目录 in 制品产物目录.iterdir()
        if 制品目录.is_dir() and (制品目录 / 制品清单名).is_file()
    ]
    if not 候选表:
        return None, None, "制品产物目录里没有带 %s 的制品" % 制品清单名
    最新 = max(候选表, key=lambda 制品目录: (制品目录 / 制品清单名).stat().st_mtime)
    try:
        return json.loads((最新 / 制品清单名).read_text(encoding="utf-8")), 最新, ""
    except (OSError, json.JSONDecodeError) as 错误:
        return None, None, "%s 读不动（%s）" % (最新 / 制品清单名, 错误)


def 源码指纹(制品清单: dict) -> str:
    return str(制品清单.get("构建指纹") or "")


def 契约指纹() -> str:
    契约件 = 仓根 / 冻结登记相对路径
    try:
        登记 = json.loads(契约件.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    行表 = sorted(
        "%s=%s" % (声明条目.get("名称", ""), 声明条目.get("形状指纹", ""))
        for 声明条目 in 登记.get("冻结项", [])
    )
    return _整串哈希(行表) if 行表 else ""


def 制品指纹(制品清单: dict) -> str:
    行表 = sorted(
        "%s=%s" % (件名, 指纹) for 件名, 指纹 in (制品清单.get("文件清单") or {}).items()
    )
    return _整串哈希(行表) if 行表 else ""


def 构建平台() -> str:
    """构建机平台三元组 —— 清单里没记（旧制品）时现问一次 `rustc -vV` 的 host 行。"""
    try:
        正文文本 = subprocess.run(
            ["rustc", "-vV"], cwd=str(仓根), capture_output=True, text=True, timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    for 源码行 in 正文文本.splitlines():
        if 源码行.startswith("host:"):
            return 源码行.split(":", 1)[1].strip()
    return ""


def 工具链(制品清单: dict) -> dict:
    锁件 = 仓根 / 依赖锁件相对路径
    工具链分项 = {
        "构建工具链": str(制品清单.get("构建工具链") or ""),
        "构建平台": str(制品清单.get("构建平台") or "") or 构建平台(),
        "依赖版本": hashlib.sha256(锁件.read_bytes()).hexdigest() if 锁件.is_file() else "",
    }
    return 工具链分项


def 采集() -> tuple:
    """⇒ `(材料, 缺项, 制品目录)`；缺项逐条是人话（阻断口直接打印）。"""
    制品清单, 制品目录, 未采原因 = 取制品清单()
    if 制品清单 is None:
        return {}, ["制品：" + 未采原因], None
    工具链材料 = 工具链(制品清单)
    缺工具链项 = [材料名 for 材料名 in ("构建工具链", "构建平台", "依赖版本") if not 工具链材料[材料名]]
    材料 = {
        "源码指纹": 源码指纹(制品清单),
        "契约指纹": 契约指纹(),
        "制品指纹": 制品指纹(制品清单),
        "工具链": " · ".join(工具链材料[材料名] for 材料名 in ("构建工具链", "构建平台", "依赖版本")),
    }
    缺项 = ["%s（%s 里取不到）" % (材料名, 制品清单名) for 材料名, 材料值 in 材料.items() if not 材料值]
    if 缺工具链项:
        缺项.append("工具链的分项：" + " / ".join(缺工具链项))
    return 材料, 缺项, 制品目录
