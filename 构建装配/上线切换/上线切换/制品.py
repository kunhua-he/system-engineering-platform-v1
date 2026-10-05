"""制品 —— 身份 · 不可变判据 · 端口来源。"""

import json
import os
from pathlib import Path

from .常量 import 仓根, 制品落点
from 构建制品.制品 import 检查制品  # 制品不可变判据的唯一实现（装配侧写清单 / --检查 同一条）


def 制品目录(标识: str) -> Path:
    return 制品落点 / 标识


def 读清单(标识: str) -> dict:
    路径 = 制品目录(标识) / "制品清单.json"
    if not 路径.is_file():
        raise SystemExit("制品不存在或没有清单：{}\n可用的制品：{}".format(路径, " · ".join(列制品()) or "（一份都没有）"))
    return json.loads(路径.read_text(encoding="utf-8"))


def 列制品() -> list:
    if not 制品落点.is_dir():
        return []
    return sorted(路径.name for 路径 in 制品落点.iterdir() if (路径 / "制品清单.json").is_file())


def 制品不可变读数(标识: str) -> tuple:
    """重算制品清单里的每个文件指纹（判据：0 处不符 · 0 个清单外文件 · 0 个缺件）。

    实现**只有一份**：`构建装配/上线切换/构建制品/制品.py::检查制品`（装配侧写清单、装配档
    `--检查`、装载前校验都走它）。本件不再自留 `rglob` 一套 —— 两套的差别正是「跳过目录
    （`__pycache__` / `target` 等）过不过滤」：rglob 那套对含跳过目录的制品会给出与装配侧相反的
    结论（`--检查` 绿而 `装载` 拒），违「同一职责一套实现」（第 4 轮审计点名）。
    """
    return 检查制品(制品目录(标识))


def 流量端口() -> int:
    """流量端口 = 契约里的默认端口（唯一定义处：`契约声明/常量表.json`），可用
    `V1_GATEWAY_PORT` 覆盖（**统一名，唯一一处** —— 与前端命令行界面同读它，
    见 `项目文档/设计文档/接口面形状.md` §六 第 6 条）。"""
    if os.environ.get("V1_GATEWAY_PORT"):
        return int(os.environ["V1_GATEWAY_PORT"])
    项表 = json.loads((仓根 / "契约声明" / "常量表.json").read_text(encoding="utf-8"))
    return int(next(一条["值"] for 一条 in 项表["常量"] if 一条["名"] == "接口端口"))
