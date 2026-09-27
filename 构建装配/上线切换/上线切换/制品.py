"""制品 —— 身份 · 不可变判据 · 端口来源。"""

import json
import os
from pathlib import Path

from .常量 import 仓根, 制品落点


def 制品目录(标识: str) -> Path:
    return 制品落点 / 标识


def 读清单(标识: str) -> dict:
    路 = 制品目录(标识) / "制品清单.json"
    if not 路.is_file():
        raise SystemExit("制品不存在或没有清单：{}\n可用的制品：{}".format(路, " · ".join(列制品()) or "（一份都没有）"))
    return json.loads(路.read_text(encoding="utf-8"))


def 列制品() -> list:
    if not 制品落点.is_dir():
        return []
    return sorted(路.name for 路 in 制品落点.iterdir() if (路 / "制品清单.json").is_file())


def 不可变读数(标识: str) -> tuple:
    """重算制品清单里的每个文件指纹（判据：0 处不符 · 0 个清单外文件 · 0 个缺件）。"""
    import hashlib

    目录 = 制品目录(标识)
    记的 = 读清单(标识).get("文件清单", {})
    现在 = {}
    for 路 in sorted(目录.rglob("*")):
        if 路.is_file() and 路.name != "制品清单.json":
            现在[路.relative_to(目录).as_posix()] = hashlib.sha256(路.read_bytes()).hexdigest()
    不符 = [键 for 键, 值 in 记的.items() if 现在.get(键) != 值]
    多余 = [键 for 键 in 现在 if 键 not in 记的]
    缺件 = [键 for 键 in 记的 if 键 not in 现在]
    return 不符, 多余, 缺件


def 流量端口() -> int:
    """流量端口 = 契约里的默认端口（唯一定义处：`契约声明/常量表.json`），可用
    `V1_GATEWAY_PORT` 覆盖（**统一名，唯一一处** —— 与前端命令行界面同读它，
    见 `项目文档/设计文档/接口面形状.md` §六 第 6 条；台账 #50 收口）。"""
    if os.environ.get("V1_GATEWAY_PORT"):
        return int(os.environ["V1_GATEWAY_PORT"])
    表 = json.loads((仓根 / "契约声明" / "常量表.json").read_text(encoding="utf-8"))
    return int(next(条["值"] for 条 in 表["常量"] if 条["名"] == "接口端口"))
