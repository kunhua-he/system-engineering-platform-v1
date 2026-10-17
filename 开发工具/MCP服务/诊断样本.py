# -*- coding: utf-8 -*-
r"""诊断样本 —— `诊断记录.py` 的正反 · 并发 · 权限 · 不泄密样本。

`自检样本.自检主体` 调本件 `诊断样本`（判据 ㊽ 跑它，退出码非 0 ⇒ 闸 0 当场红）。

**全程把 `<运行数据根>` 指到临时根**（`覆盖变量名` 环境变量）⇒ 仓一个字节都不改，也不碰真诊断日志。
五条断言：
  · 网关**执行后**非 0 ⇒ 恰落一条，行内键集 = `允许字段`、无正文。
  · **预期业务拒绝**（尾非 0 · 退出码 2）⇒ 恰落一条、**定位空**（不输出 traceback）。
  · `tools/call` 内部异常 ⇒ 恰落一条 · **原样 re-raise** · 行含错误类型与有限定位。
  · 不泄密：异常消息里的**假秘密**不得进日志（只取类型名 + 帧位置）。
  · 权限：日志根不可写 ⇒ `记诊断` 回假 · 网关原退出码与原回执**一个字节不变**。
  · 并发：多线并落 ⇒ 行数 = 次数，逐行都是完整 JSON（不交叉）。
"""

import json
import os
import shutil
import tempfile
from pathlib import Path


def 假实现(实参, 仓根):
    """替身实现：抛一条**带假秘密**的异常（证明诊断只取类型名 + 帧位置，绝不带异常消息）。"""
    raise ValueError("token=假秘密-勿泄露-A1B2C3")


def 读诊断行() -> list:
    """读当前运行数据根下的诊断日志 ⇒ 记录表（逐行 JSON；解不动的那行记成 `{"坏行": 原文}`）。"""
    from .诊断记录 import 诊断路径
    件路径 = 诊断路径()
    行表 = []
    if not 件路径.is_file():
        return 行表
    for 源码行 in 件路径.read_text(encoding="utf-8").splitlines():
        if not 源码行.strip():
            continue
        try:
            行表.append(json.loads(源码行))
        except ValueError:
            行表.append({"坏行": 源码行})
    return 行表


def 诊断样本(仓根, 工具表) -> list:
    """⇒ 样本表 `[(说明, 通过), ...]`（临时运行数据根内跑；仓一个字节都不改）。"""
    from unittest.mock import patch

    from 开发工具.运行数据根.口径 import 覆盖变量名

    样本表 = []
    临时根 = Path(tempfile.mkdtemp(prefix="v1诊断样本-"))
    try:
        with patch.dict(os.environ, {覆盖变量名: str(临时根)}):
            样本表 += 网关协议样本(仓根, 工具表)
            样本表 += 并发样本()
            样本表 += 权限样本(仓根, 工具表)
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表


def 网关协议样本(仓根, 工具表) -> list:
    """网关尾非 0 与 `tools/call` 内部异常：各恰落一条、键集合规、原结果不变、假秘密不泄。"""
    from . import 协议, 参数规范
    from .诊断记录 import 允许字段

    输出表 = []
    起点条数 = len(读诊断行())
    退出码, 回执 = 工具表["v1_shell"][0]({"操作": "执行", "参数": {"命令": "exit 7"}}, 仓根)
    新增 = 读诊断行()[起点条数:]
    末行 = 新增[-1] if 新增 else {}
    键集合规 = set(末行) == set(允许字段)
    字段值齐 = (末行.get("工具") == "v1_shell" and 末行.get("操作") == "执行"
            and 末行.get("错误类型") == "网关非零" and 末行.get("退出码") == 1)
    正文未泄 = "exit 7" not in json.dumps(末行, ensure_ascii=False)
    输出表.append(("诊断 网关尾非 0（v1_shell exit 7）：退出码 %d（期望 1）· 恰落 %d 条（期望 1）· "
             "键集合规 %s · 字段值齐 %s · 正文未泄 %s"
             % (退出码, len(新增), "是" if 键集合规 else "否", "是" if 字段值齐 else "否",
                "是" if 正文未泄 else "否"),
             退出码 == 1 and len(新增) == 1 and 键集合规 and 字段值齐 and 正文未泄))

    起点条数 = len(读诊断行())
    退出码, 回执 = 工具表["v1_shell"][0](
        {"开工ID": "v1-999999", "操作": "执行", "参数": {"命令": "echo x"}}, 仓根)
    新增 = 读诊断行()[起点条数:]
    末行 = 新增[-1] if 新增 else {}
    输出表.append(("诊断 预期业务拒绝（非法开工 ⇒ 尾非 0）：退出码 %d（期望 2）· 恰落 %d 条（期望 1）· "
             "定位空（无 traceback）%s"
             % (退出码, len(新增), "是" if not 末行.get("定位") else "否"),
             退出码 == 2 and len(新增) == 1 and not 末行.get("定位")))

    起点条数 = len(读诊断行())
    假工具表 = {"v1-假工具": (假实现, "假工具", "假工具", 参数规范.统一模式)}
    原样抛 = False
    try:
        协议.派发("tools/call",
                 {"name": "v1-假工具", "arguments": {"开工ID": "v1-100549", "操作": "假操作"}},
                仓根, 假工具表)
    except ValueError:
        原样抛 = True
    新增 = 读诊断行()[起点条数:]
    末行 = 新增[-1] if 新增 else {}
    泄密 = "假秘密" in json.dumps(新增, ensure_ascii=False)
    输出表.append(("诊断 tools/call 内部异常：原样 re-raise %s · 恰落 %d 条（期望 1）· "
             "错误类型 %s（期望 ValueError）· 有限定位 %s · 假秘密未泄 %s"
             % ("是" if 原样抛 else "否", len(新增), 末行.get("错误类型"),
                "有" if 末行.get("定位") else "无", "是" if not 泄密 else "**泄了**"),
             原样抛 and len(新增) == 1 and 末行.get("错误类型") == "ValueError"
             and bool(末行.get("定位")) and not 泄密))

    return 输出表


def 并发样本() -> list:
    """多线并落 ⇒ 行数 = 次数 · 逐行键集合规 ⇒ 不同请求的行不交叉。"""
    import threading

    from .诊断记录 import 允许字段, 记诊断

    起点条数 = len(读诊断行())
    并发条数 = 24

    def 落一条(序号):
        记诊断("工具-%d" % 序号, "操作-%d" % 序号, "", "并发")

    线程表 = [threading.Thread(target=落一条, args=(序号,)) for 序号 in range(并发条数)]
    for 线程项 in 线程表:
        线程项.start()
    for 线程项 in 线程表:
        线程项.join()
    新增 = 读诊断行()[起点条数:]
    键集合规 = all(set(诊断行) == set(允许字段) for 诊断行 in 新增)
    名字集 = {诊断行.get("工具") for 诊断行 in 新增}
    期望集 = {"工具-%d" % 序号 for 序号 in range(并发条数)}
    return [("诊断 并发不交叉：落 %d 条（期望 %d）· 逐行键集合规 %s · 工具名集齐 %s"
             % (len(新增), 并发条数, "是" if 键集合规 else "否", "是" if 名字集 == 期望集 else "否"),
             len(新增) == 并发条数 and 键集合规 and 名字集 == 期望集)]


def 权限样本(仓根, 工具表) -> list:
    """日志根不可写 ⇒ `记诊断` 回假 · 网关原退出码与原回执一个字节不变（本件失败不改调用结果）。"""
    from unittest.mock import patch

    from 开发工具.运行数据根.口径 import 覆盖变量名
    from .诊断记录 import 记诊断

    坏根 = Path(tempfile.mkdtemp(prefix="v1诊断坏根-")) / "冒充根"
    坏根.write_text("这不是目录", encoding="utf-8")
    try:
        with patch.dict(os.environ, {覆盖变量名: str(坏根)}):
            落了 = 记诊断("v1_shell", "执行", "", "网关非零", 退出码=1)
            退出码, 回执 = 工具表["v1_shell"][0]({"操作": "执行", "参数": {"命令": "exit 7"}}, 仓根)
    finally:
        shutil.rmtree(坏根.parent, ignore_errors=True)
    return [("诊断 日志根不可写：记诊断回假 %s · 网关退出码 %d（期望 1）· 原回执带「退出码：7」%s"
             % ("是" if not 落了 else "**没回假**", 退出码, "是" if "退出码：7" in 回执 else "否"),
             (not 落了) and 退出码 == 1 and "退出码：7" in 回执)]
