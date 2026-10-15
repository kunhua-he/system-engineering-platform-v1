"""兼容矩阵 —— 新旧 宿主 / 调用方 / 制品 / 执行模式 四维，以及「旧样本不可变」（架构收敛方案项 F04）。

矩阵本体住 `契约声明/兼容矩阵.json`（声明侧，随版本控制）；本件是**校验口**：
  · 四维齐（宿主 / 调用方 / 制品 / 执行模式），每维要有 `旧` · `新` · `兼容判定` · `落点`
  · 每个 `旧样本` 的指纹必须与盘上那份逐字相符 —— 旧样本一改，历史兼容结论就不再成立 ⇒ 红
四维**各写各的判据来源**（`落点` 指向真实现处），不许只写一句「兼容」糊过去。
"""

import hashlib
import json

from .常量 import 仓根, 兼容矩阵相对路径, 矩阵四维


def 读矩阵() -> tuple:
    契约件 = 仓根 / 兼容矩阵相对路径
    if not 契约件.is_file():
        return None, "%s 不在（兼容矩阵的声明侧唯一存本）" % 兼容矩阵相对路径
    try:
        return json.loads(契约件.read_text(encoding="utf-8")), ""
    except (OSError, json.JSONDecodeError) as 错误:
        return None, "%s 读不动（%s）" % (兼容矩阵相对路径, 错误)


def 查旧样本(旧样本表: list) -> list:
    违规行 = []
    for 声明条目 in 旧样本表:
        相对路径 = str(声明条目.get("相对路径") or "")
        记的指纹 = str(声明条目.get("指纹") or "")
        目标件 = 仓根 / 相对路径
        if not 相对路径 or not 目标件.is_file():
            违规行.append("旧样本 `%s` 在盘上不在 —— 旧样本不可变的前提是它还在" % 相对路径)
            continue
        现算 = hashlib.sha256(目标件.read_bytes()).hexdigest()
        if 现算 != 记的指纹:
            违规行.append(
                "旧样本 `%s` 已变（记 %s · 现 %s）—— 旧样本不可变，改了就必须重走兼容评估"
                % (相对路径, 记的指纹[:12], 现算[:12])
            )
    return 违规行


def 查矩阵() -> tuple:
    """⇒ `(违规行, 矩阵)` —— 空表 = 通过；矩阵为 None = 未判。"""
    矩阵, 未采原因 = 读矩阵()
    if 矩阵 is None:
        return [未采原因], None
    违规行 = []
    行表 = 矩阵.get("四维") or []
    现有维度 = [str(声明条目.get("维度") or "") for 声明条目 in 行表]
    for 维度 in 矩阵四维:
        if 维度 not in 现有维度:
            违规行.append("四维缺「%s」—— 兼容矩阵必须四维齐（架构收敛方案项 F04）" % 维度)
    for 声明条目 in 行表:
        for 键名 in ("旧", "新", "兼容判定", "落点"):
            if not 声明条目.get(键名):
                违规行.append("维度「%s」缺 `%s`" % (声明条目.get("维度"), 键名))
    违规行 += 查旧样本(矩阵.get("旧样本") or [])
    return 违规行, 矩阵
