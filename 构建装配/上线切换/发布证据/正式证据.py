"""正式证据 —— 把四类材料收成**一份**证据件（含证据指纹），可重跑、可对账。

口径（架构收敛方案项 W07 · 发布验收）：正式证据 = 源码指纹 + 契约指纹 + 制品指纹 + 工具链 **四类同证**。
四类原先散在 `契约声明/冻结登记.json` 与 `测试验证/准入判据/故障取证样本/` 里 —— 没人能
一次回答「这份发布绑的是哪份源、哪份契约、哪个制品、哪套工具链」。本件把四类并成一份，
并给整份算一个 `证据指纹`：同一份材料重跑必得同一个指纹（**可复现**），材料换一项则指纹必变
（**不冒充通过**）。

缺材料**不写件** —— 缺件冒充通过正是 369 要堵的那一条。
"""

import hashlib
import json

from .证据落点常量 import 证据落点, 四类材料
from .采集材料 import 采集


def 算证据指纹(材料: dict) -> str:
    行表 = ["%s=%s" % (材料名, 材料.get(材料名, "")) for 材料名 in 四类材料]
    return hashlib.sha256("\n".join(行表).encode("utf-8")).hexdigest()


def 出证据() -> tuple:
    """⇒ `(证据, 缺项)`；缺项非空时证据必为 None（不落件）。"""
    材料, 缺项, 制品目录 = 采集()
    if 缺项:
        return None, 缺项
    证据 = {
        "说明": "正式证据 —— 一次发布的四类材料同证（架构收敛方案项 W07 · 发布验收）。落盘件是生成物，改它请改 构建装配/上线切换/发布证据.py（源）。",
        "材料": {材料名: 材料[材料名] for 材料名 in 四类材料},
        "制品目录": 制品目录.name if 制品目录 is not None else "",
        "证据指纹": 算证据指纹(材料),
    }
    return 证据, []


def 写证据(证据: dict) -> str:
    证据落点.parent.mkdir(parents=True, exist_ok=True)
    落盘文本 = json.dumps(证据, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    证据落点.write_text(落盘文本, encoding="utf-8")
    return str(证据落点)
