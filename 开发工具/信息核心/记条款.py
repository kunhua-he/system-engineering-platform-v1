# -*- coding: utf-8 -*-
"""记条款 —— 往规则库的 `条款` 表记 / 改写**一行**（一行一节）。

用法：
    python3 开发工具/信息核心/信息核心.py 记条款 --文档路径 <仓内相对路径> --序号 <整数> \\
        [--标题 <节标题>] --正文 <散文> [--权威档 <档位>]
    python3 开发工具/信息核心/信息核心.py 记条款 --删 --文档路径 <仓内相对路径> [--序号 <整数>]
        （给了 `--序号` 删那一行；不给 ⇒ 删该 `文档路径` 的**全部行**）

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
      "[--标题 <节标题>] [--正文 <散文> | --正文文件 <仓内相对路径>] [--权威档 <档位>] "
      "[--允许空正文]")


def 删条款(字段表: dict) -> int:
    """把 `条款` 表里的行**删掉** ⇒ 退出码。

    两个**互相排斥**的指名形（同形照 `记规则.删规则` 的 `--删 --编号` 那个口）：
      · `--文档路径 P --序号 N` ⇒ 删那一行；
      · `--全部路径 P`       ⇒ 删 `P` 的**全部行**（明确写「全部」，不靠省略参数表达）。

    ★ **不许通配 / 不许「删某前缀」**（`开发规范 §八.8`：「删生成物要显式指名，不许通配」）——
      条款是正文的**唯一存本**，比制品更不可逆。故**先打印「将删 N 节 + 每节标题」**：
      不给 `--确认` = 只预览、**不删**（退出码 1，fail-closed，免得当成功）；给了 `--确认` 才真删。
    """
    文档路径 = (字段表.get("文档路径") or "").strip()
    全部路径 = (字段表.get("全部路径") or "").strip()
    序号 = (字段表.get("序号") or "").strip()
    确认 = "确认" in 字段表
    if 文档路径 and 全部路径:
        print("拒：`--文档路径`（删一行）与 `--全部路径`（删整份）互斥，只能给一个。",
              file=sys.stderr)
        return 2
    目标路径 = 全部路径 or 文档路径
    if not 目标路径:
        print("拒：`--删` 要给 `--文档路径 P --序号 N`（删一行）或 `--全部路径 P`（删整份）。",
              file=sys.stderr)
        return 2
    if Path(目标路径).is_absolute() or ".." in Path(目标路径).parts:
        print(f"拒：`{目标路径}` 该是仓内相对路径（不许绝对路径 / `..`）。", file=sys.stderr)
        return 2
    if 文档路径 and not 序号:
        print("拒：`--文档路径` 这一形必须配 `--序号`（删一行）；要删整份请用 `--全部路径`。",
              file=sys.stderr)
        return 2
    if 序号 and not 序号.isdigit():
        print(f"拒：`--序号 {序号}` 该是整数。", file=sys.stderr)
        return 2
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        if 全部路径:
            行表 = list(连接.execute(
                "select 序号, 标题 from 条款 where 文档路径 = ? order by 序号", (目标路径,)))
        else:
            行表 = list(连接.execute(
                "select 序号, 标题 from 条款 where 文档路径 = ? and 序号 = ?",
                (目标路径, int(序号))))
        预览 = (f"{目标路径}" + (f" §{序号}" if 文档路径 else "（全部行）") +
                f"：将删 {len(行表)} 节")
        if not 行表:
            print(f"拒：`条款` 表里没有 {预览}（没删到东西）。", file=sys.stderr)
            return 1
        for 号值, 标题 in 行表:
            预览 += f"\n    §{号值} · {标题}"
        print(预览)
        if not 确认:
            print("★ 未给 `--确认` ⇒ **只预览、不删**（条款是正文唯一存本，删除不可逆）"
                  "——要真删请重跑并加 `--确认`。", file=sys.stderr)
            return 1
        if 全部路径:
            行数 = 连接.execute("delete from 条款 where 文档路径 = ?", (目标路径,)).rowcount
        else:
            行数 = 连接.execute("delete from 条款 where 文档路径 = ? and 序号 = ?",
                            (目标路径, int(序号))).rowcount
        连接.commit()
    finally:
        连接.close()
    print(f"记条款：删 {目标路径}" + (f" §{序号}" if 文档路径 else "（全部行）") +
          f"（{行数} 行）")
    print("★ 库变了 ⇒ 收口前记得 `v1_task` 功能=6 记账"
          "（`源件` = `开发工具/信息核心/信息核心.db`），否则释放的越界检测会拒")
    return 0


def 记条款(字段表: dict) -> int:
    """往 `条款` 表就地写一行（主键 `(文档路径, 序号)`）⇒ 退出码。

    给了 `--序号` 就是**就地改写那一行**（主键不变）；`--权威档` 不给 ⇒ 保住库里已有的那一档。

    **正文两形**：`--正文` 走 `记规则.解析参数`（空白折成单空格 —— 适合一行小结）；**散文**
    （多段落）用 `--正文文件 <仓内相对路径>`，逐字节读入（**保住换行**，条款正文都是这种）。
    `--文档路径` / `--正文文件` 都过仓内相对路径闸（空 / 绝对 / `..` ⇒ 拒）；正文文件读不到
    是**结构化拒**（退出码 2），不是 traceback。

    给了 `--删` ⇒ 先走 `--删` 分支（`删条款`）。
    """
    if "删" in 字段表:
        return 删条款(字段表)
    文档路径 = (字段表.get("文档路径") or "").strip()
    序号 = (字段表.get("序号") or "").strip()
    标题 = (字段表.get("标题") or "").strip()
    正文文件 = (字段表.get("正文文件") or "").strip()
    正文 = (字段表.get("正文") or "").strip()
    权威档 = (字段表.get("权威档") or "").strip()
    # ★ 空正文是**合法形**（`建库` 的 `拆节` 对「只有标题的节」就产空体；库里已有这类行）⇒
    #   要写这类行得显式声明 `--允许空正文`，免得手滑把真正的空写当成正常写入。
    允许空 = "允许空正文" in 字段表
    if not 文档路径 or not 序号.isdigit() or not (正文 or 正文文件 or 允许空):
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
            正文 = (仓根 / 正文文件).read_text(encoding="utf-8").rstrip("\n")
        except OSError as 错误:
            print(f"拒：读 `--正文文件 {正文文件}` 失败 —— {错误}", file=sys.stderr)
            return 2
    if not 正文 and not 允许空:
        print("拒：正文是空的（`--正文` 空串 / `--正文文件` 抽出空）。", file=sys.stderr)
        return 2
    if (仓根 / 文档路径).is_file():
        print(f"拒：`{文档路径}` 在盘上还有源件（md）—— 那份 md 才是权威，"
              f"改 md 重跑 `建库` 即刷新（`建库` 的分片源件会把本行抽回去）。", file=sys.stderr)
        return 1
    连接 = sqlite3.connect(表定义.库路径(仓根))
    try:
        # ★ 2026-10-10：防**孤儿行** —— 只过「仓内相对路径闸」还不够：一个拼错的新路径
        #   （盘上没 md、库里也别处没有）写进去，就成了 `条款` 表里一行无主正文。
        #   合法用法是「改**已入库**的某节」，所以库里必须已有这份文档的行。
        别处 = 连接.execute("select 1 from 条款 where 文档路径 = ? limit 1",
                          (文档路径,)).fetchone()
        if not 别处:
            print(f"拒：库里 `{文档路径}` 一行都没有（盘上也没这份 md）—— "
                  f"新文档路径得先有 md（放进仓里跑 `建库`）才能记条款，"
                  f"否则这一笔只会在 `条款` 表里落一条**孤儿行**。先核路径是否拼错。",
                  file=sys.stderr)
            return 2
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
