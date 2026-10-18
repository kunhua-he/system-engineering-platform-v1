# -*- coding: utf-8 -*-
"""操作脚本 —— 操作表声明的「固定脚本目录」执行口：定路径 + 5 秒硬顶跑。

**为什么单开一件**（判据 ⑲ 单源文件 ≤400 行）：`参数规范.py` 已接近上限，把**脚本执行**
（路径白名单 + 有界执行）搬出来，`参数规范.py` 只管加载 / 校验 / 信封。

**源码写盘仍只走 `v1_edit`**：脚本写脏的源码件在释放的越界检测处被拒 —— 本口不授权绕记账。
"""
import json
import shlex
from pathlib import Path

# 操作脚本的**固定目录**（白名单根）：操作表声明的脚本只许落在这里面（不接受任意路径）
脚本根 = Path(__file__).resolve().parents[2] / "操作脚本"
# 脚本执行的同步硬顶（秒）：长活不塞这里（走后台作业）
脚本超时秒 = 5


def 定脚本(脚本相对: str) -> str:
    """操作声明的脚本落点 ⇒ 绝对路径；越出**固定脚本目录** / 不存在 ⇒ 空串（拒，不接受任意路径）。"""
    if not 脚本相对 or str(脚本相对).startswith("/") or ".." in Path(str(脚本相对)).parts:
        return ""
    绝对路径 = (脚本根 / str(脚本相对)).resolve()
    根路径 = 脚本根.resolve()
    if 根路径 != 绝对路径 and 根路径 not in 绝对路径.parents:
        return ""
    return str(绝对路径) if 绝对路径.is_file() else ""


def 跑脚本(脚本路径: str, 开工号: str, 操作名: str, 参数表: dict, 仓根路径) -> tuple:
    """执行一个操作脚本 ⇒ `(退出码, 输出文本)`：**5 秒硬顶 · 输出有界 · 完整日志指针**（复用 shell 执行器）。

    脚本从环境拿输入：`V1_操作` · `V1_开工ID` · `V1_参数`（JSON）；工作目录 = 目标树（开工号定工作树）。
    """
    from ..作业执行.shell import 派发 as 终端派
    命令 = "V1_操作=%s V1_开工ID=%s V1_参数=%s sh %s" % (
        shlex.quote(操作名), shlex.quote(开工号),
        shlex.quote(json.dumps(参数表, ensure_ascii=False)), shlex.quote(脚本路径))
    实参 = {"命令": 命令, "超时": 脚本超时秒}
    if 开工号:
        实参["开工ID"] = 开工号
    return 终端派(实参, 仓根路径)
