# -*- coding: utf-8 -*-
"""记条款 —— 往规则库的 `条款` 表记 / 改写**一行**（一行一节）。

用法：
    python3 开发工具/信息核心/信息核心.py 记条款 --文档路径 <仓内相对路径> --序号 <整数> \\
        [--标题 <节标题>] --正文 <散文> [--权威档 <档位>]

**为何要它**：`条款` 表是**全部 md 正文的唯一存本**（一行一节，md 已全量入库并删净）。可它的
写口只有「源件在场就重抽、源件不在就保住旧行」——**没有仓内源件的文档**（md 已删）那一行
**改不动**（改 `测试验证/案例/形状.md` 的 §八 / §10.2 就卡在这）。本命令就是那条正路：
形状照 `记规则` 的 `--编号`（就地 `insert or replace`，主键 `(文档路径, 序号)` 不变）——
参数解析**复用 `记规则.解析参数`**（不许写第二套）。写库 + 记账走 `v1_task` 功能 = 6（库是源）。

**源件在场的文档不走它**：那份 md 才是权威，改 md 重跑 `建库` 即刷新（`建库` 的分片源件会
把这一行抽回去，本命令的改动会被覆盖）⇒ 故对 `文档路径` 在盘上存在的，本命令**拒写**。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402
import 记规则  # noqa: E402  （复用它的参数解析 —— 不许写第二套）

用法文本 = ("用法：信息核心.py 记条款 --文档路径 <仓内相对路径> --序号 <整数> "
      "[--标题 <节标题>] [--正文 <散文> | --正文文件 <仓内相对路径>] [--权威档 <档位>]")


def 记条款(字段表: dict) -> int:
    """往 `条款` 表就地写一行（主键 `(文档路径, 序号)`）⇒ 退出码。

    给了 `--序号` 就是**就地改写那一行**（主键不变）；`--权威档` 不给 ⇒ 保住库里已有的那一档。

    **正文两形**：`--正文` 走 `记规则.解析参数`（空白折成单空格 —— 适合一行小结）；**散文**
    （多段落）用 `--正文文件 <仓内相对路径>`，逐字节读入（**保住换行**，条款正文都是这种）。
    `--文档路径` / `--正文文件` 都过仓内相对路径闸（空 / 绝对 / `..` ⇒ 拒）；正文文件读不到
    是**结构化拒**（退出码 2），不是 traceback。
    """
    文档路径 = (字段表.get("文档路径") or "").strip()
    序号 = (字段表.get("序号") or "").strip()
    标题 = (字段表.get("标题") or "").strip()
    正文文件 = (字段表.get("正文文件") or "").strip()
    正文 = (字段表.get("正文") or "").strip()
    权威档 = (字段表.get("权威档") or "").strip()
    if not 文档路径 or not 序号.isdigit() or not (正文 or 正文文件):
        print(用法文本, file=sys.stderr)
        return 2
    if Path(文档路径).is_absolute() or ".." in Path(文档路径).parts:
        print(f"拒：`--文档路径 {文档路径}` 该是仓内相对路径（不许绝对路径 / `..`）。",
              file=sys.stderr)
        return 2
    if 正文文件:
        if Path(正文文件).is_absolute() or ".." in Path(正文文件).parts:
            print(f"拒：`--正文文件 {正文文件}` 该是仓内相对路径（不许绝对路径 / `..`）。",
                  file=sys.stderr)
            return 2
        try:
            正文 = (仓根 / 正文文件).read_text(encoding="utf-8").strip()
        except OSError as 错误:
            print(f"拒：读 `--正文文件 {正文文件}` 失败 —— {错误}", file=sys.stderr)
            return 2
    if not 正文:
        print("拒：正文是空的（`--正文` 空串 / `--正文文件` 抽出空）。", file=sys.stderr)
        return 2
    if (仓根 / 文档路径).is_file():
        print(f"拒：`{文档路径}` 在盘上还有源件（md）—— 那份 md 才是权威，"
              f"改 md 重跑 `建库` 即刷新（`建库` 的分片源件会把本行抽回去）。", file=sys.stderr)
        return 1
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        已有 = 连接.execute("select 权威档 from 条款 where 文档路径 = ? and 序号 = ?",
                          (文档路径, int(序号))).fetchone()
        连接.execute("insert or replace into 条款 values(?,?,?,?,?)",
                   (文档路径, int(序号), 标题, 正文, 权威档 or (已有[0] if 已有 else "")))
        连接.commit()
    finally:
        连接.close()
    print(f"记条款：{文档路径} §{序号} · {标题}")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0
