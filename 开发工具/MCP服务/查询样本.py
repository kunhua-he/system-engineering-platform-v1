# -*- coding: utf-8 -*-
"""查询样本 —— `v1_task` 查询的**降噪正反样本**（临时账本 + 临时工作树，跑完即删）。

★ v1-100569 腿由 v1-100576（7b7ebd81）正式继承：查询走**真 Git**（提速，使闸 1 入五秒硬顶）⇒ 经 v1_edit 正式认领。

`自检样本.跑自检` 调它（判据 ㊽ 跑自检，退出码非 0 ⇒ 闸 0 当场红）。**仓一个字节都不改**：
账本连口与支线问口都走替身。

口径（与 `查询渲染` / `开工.查询开工` 同一份）：
  正向 —— 单号**只给本号**（不附「工作树仍在」全局段）；全局**保留诊断**但「工作树仍在」
  默认折成计数（`展开` 前不列号、`展开` = 真 才逐号列）；关键词命中仍有效；上限合法可调；
  查完**只读账本不翻状态**。
  反向 —— 关键词无命中**补一句**「查单号请用顶层 `开工ID`」；上限非法（非数 / 越界）⇒ 退出码 2。
"""
import re
import subprocess
from pathlib import Path


def 查询样本(仓根, 工具表) -> list:
    """跑查询正反样本 ⇒ 样本表。"""
    import shutil
    import sqlite3
    import tempfile

    from . import 开工, 开工账本

    临时根 = Path(tempfile.mkdtemp(prefix="v1查询自检-"))
    try:
        主树 = 临时根 / "主树"
        旁树 = 临时根 / "旁树"
        主树.mkdir()
        旁树.mkdir()
        # 主树 必须是**真 Git 仓**：单号查询按 《查询渲染.拼单号明细》 现读真 `分支/HEAD`（40 位哈希）。
        # 夹具若不建仓，`读树头` 只能给空串 ⇒ 该正向断言永不可过（曾漏成假红，退回一步）。
        _跑Git(主树, "init", "-b", "腿/v1-自检主")
        _跑Git(主树, "config", "user.name", "样本")
        _跑Git(主树, "config", "user.email", "fixture@example.invalid")
        (主树 / "样本.txt").write_text("样本基线\n", encoding="utf-8")
        _跑Git(主树, "add", "样本.txt")
        _跑Git(主树, "commit", "-m", "样本基线")
        主树头 = _跑Git(主树, "rev-parse", "HEAD").strip()
        账本路径 = 临时根 / "账本.db"
        连接 = sqlite3.connect(str(账本路径))
        连接.row_factory = sqlite3.Row
        for 建表行 in 开工账本.建表语句:
            连接.execute(建表行)
        开工账本.登记开工(连接, "v1-自检主", "查询样本主", "腿/v1-自检主", str(主树))
        开工账本.登记开工(连接, "v1-自检旁", "查询样本旁", "腿/v1-自检旁", str(旁树))
        开工账本.登记开工(连接, "v1-自检僵尸", "查询样本僵尸", "腿/v1-自检僵尸", str(临时根 / "不在"))
        连接.commit()
        连接.close()

        def 开账():
            新连接 = sqlite3.connect(str(账本路径))
            新连接.row_factory = sqlite3.Row
            return 新连接

        真连, 真支线 = 开工账本.连账本, 开工.支线在吗
        开工账本.连账本 = 开账
        开工.支线在吗 = lambda 忽略仓根, 忽略开工号: False
        出口 = 工具表["v1_task"][0]
        样本表 = []
        try:
            退出码, 回执 = 出口({"开工ID": "v1-自检主", "操作": "查询"}, 仓根)
            单号净 = ("v1-自检主" in 回执 and "v1-自检旁" not in 回执
                   and "工作树仍在" not in 回执 and "僵尸开工" not in 回执)
            分支头对 = re.search(r"分支 HEAD：%s %s\b" % (re.escape("腿/v1-自检主"), 主树头), 回执) is not None
            样本表.append(("v1_task 查询 单号：退出码 %d · 只给本号%s · 不附全局诊断%s · 分支HEAD 真读(腿/v1-自检主 %s)%s"
                    % (退出码, "" if ("v1-自检主" in 回执 and "v1-自检旁" not in 回执) else "**没**",
                       "" if ("工作树仍在" not in 回执 and "僵尸开工" not in 回执) else "**仍附**",
                       主树头[:12], "是" if 分支头对 else "否"),
                     退出码 == 0 and 单号净 and 分支头对
                     and "Traceback" not in 回执))
            退出码, 回执 = 出口({"开工ID": "v1-自检僵尸", "操作": "查询"}, 仓根)
            样本表.append(("v1_task 查询 单号（工作树不在 ⇒ 分支HEAD 读不到 · 不崩）：退出码 %d · 报读不到%s"
                    % (退出码, "是" if "分支 HEAD：（读不到" in 回执 else "否"),
                     退出码 == 0 and "分支 HEAD：（读不到" in 回执 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 1}}, 仓根)
            折叠 = ("工作树仍在的开工 2 条" in 回执 and "默认折叠" in 回执
                  and "v1-自检主" not in 回执 and "僵尸开工 1 条" in 回执)
            样本表.append(("v1_task 查询 全局（上限=1 · 默认折叠）：退出码 %d · 计数%s · 折叠提示%s · "
                    "未列树在号%s · 僵尸计数%s"
                    % (退出码, "在" if "工作树仍在的开工 2 条" in 回执 else "**缺**",
                       "在" if "默认折叠" in 回执 else "**缺**",
                       "（对）" if "v1-自检主" not in 回执 else "**仍列**",
                       "在" if "僵尸开工 1 条" in 回执 else "**缺**"),
                     退出码 == 0 and 折叠 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 1, "展开": True}}, 仓根)
            展开齐 = ("默认折叠" not in 回执 and "v1-自检主" in 回执 and "v1-自检旁" in 回执)
            样本表.append(("v1_task 查询 全局（展开=真）：退出码 %d · 逐号列树在%s · 不再折叠%s"
                    % (退出码, "" if ("v1-自检主" in 回执 and "v1-自检旁" in 回执) else "**没**",
                       "" if "默认折叠" not in 回执 else "**仍折叠**"),
                     退出码 == 0 and 展开齐 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"关键词": "查询样本旁"}}, 仓根)
            样本表.append(("v1_task 查询 关键词命中：退出码 %d · 命中 v1-自检旁 %s"
                    % (退出码, "是" if "v1-自检旁" in 回执 else "否"),
                     退出码 == 0 and "命中 1 条" in 回执 and "v1-自检旁" in 回执
                     and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"关键词": "绝无此词样本"}}, 仓根)
            样本表.append(("v1_task 查询 关键词无命中：退出码 %d · 补「查单号请用顶层 `开工ID`」%s"
                    % (退出码, "是" if "查单号请用顶层" in 回执 else "否"),
                     退出码 == 0 and "没有命中" in 回执 and "查单号请用顶层" in 回执
                     and "Traceback" not in 回执))
            for 坏上限 in ("abc", 0, 10 ** 9):
                退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 坏上限}}, 仓根)
                样本表.append(("v1_task 查询 上限非法（%r）：退出码 %d（期望 2 · 不崩）"
                        % (坏上限, 退出码),
                         退出码 == 2 and "Traceback" not in 回执))
            # ── 倒排样本：旧时间大号 vs 新时间小号（按开工时间稳定倒排，不许被号段大号盖住）──
            连接 = 开账()
            for 数据行 in (("v1-900006", "倒排样本旧大号", "2026-10-10T20:01:43+0800"),
                         ("v1-101000", "倒排样本新小号", "2099-01-01T00:00:00+0800")):
                连接.execute("insert into 开工 (开工号, 工作内容, 分支名, 工作树, 状态, 开工时间, 开工种类)"
                          " values (?, ?, ?, ?, ?, ?, ?)",
                          (数据行[0], 数据行[1], "腿/" + 数据行[0], str(主树),
                           开工账本.状态_已释放, 数据行[2], 开工账本.种类_原腿))
            连接.commit()
            连接.close()
            退出码, 回执 = 出口({"操作": "查询", "参数": {"上限": 2}}, 仓根)
            号序 = _解析回执号序(回执)
            首条 = 号序[:1] == ["v1-101000"] and "v1-900006" not in 号序
            样本表.append(("v1_task 查询 全局倒排（旧时间大号 v1-900006 · 新时间小号 v1-101000 · 上限=2）："
                    "退出码 %d · 真实列表首条 %s（期望 v1-101000）%s"
                    % (退出码, 号序[0] if 号序 else "（无记录行）", "是" if 首条 else "**否**"),
                     退出码 == 0 and 首条 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"操作": "查询", "参数": {"关键词": "倒排样本", "上限": 2}}, 仓根)
            号序 = _解析回执号序(回执)
            首条 = 号序[:2] == ["v1-101000", "v1-900006"]
            样本表.append(("v1_task 查询 关键词倒排（同关键词两条 · 上限=2）：退出码 %d · 真实列表首条 %s（期望 v1-101000）%s"
                    % (退出码, 号序[0] if 号序 else "（无记录行）", "是" if 首条 else "**否**"),
                     退出码 == 0 and 首条 and "Traceback" not in 回执))
            退出码, 回执 = 出口({"开工ID": "v1-900006", "操作": "查询"}, 仓根)
            号序 = _解析回执号序(回执)
            样本表.append(("v1_task 查询 明确ID 不受倒排影响（v1-900006 只给本号）：退出码 %d · 真实列表号序 %r%s"
                    % (退出码, 号序, "是" if 号序 == ["v1-900006"] else "**否**"),
                     退出码 == 0 and 号序 == ["v1-900006"] and "Traceback" not in 回执))
            连接 = 开账()
            状态没翻 = 连接.execute("select 状态 from 开工 where 开工号 = ?",
                              ("v1-自检主",)).fetchone()[0] == 开工账本.状态_进行中
            连接.close()
            样本表.append(("v1_task 查询 只读账本：查完 v1-自检主 状态仍「进行中」%s"
                    % ("是" if 状态没翻 else "**否**"), 状态没翻))
        finally:
            开工账本.连账本, 开工.支线在吗 = 真连, 真支线
        return 样本表
    finally:
        shutil.rmtree(临时根, ignore_errors=True)


def _解析回执号序(回执: str) -> list:
    """工具回执（统一信封 = **一行 JSON**）⇒ **真实列表号序**（逐行首 `v1-<6位>`）。

    ★ 先解析信封再取正文（`结果` 优先，退回 `说明`），**绝不对整段回执做包含判断**：
    单行 JSON 里两个号都在 ⇒ 包含判断恒真，倒排样本曾因此假绿（10106104）。
    解析不出正文 ⇒ 空表（fail-closed：样本红，不假绿）。
    """
    import json
    正文 = 回执
    try:
        信封 = json.loads(回执)
    except Exception:
        信封 = None
    if isinstance(信封, dict):
        for 信封键 in ("结果", "说明"):
            信封值 = 信封.get(信封键)
            if isinstance(信封值, str) and 信封值.strip():
                正文 = 信封值
                break
    号序 = []
    for 记录行 in 正文.splitlines():
        命中 = re.match(r"^\s*(?:开工号\s+)?(v1-\S+)", 记录行)
        if 命中:
            号序.append(命中.group(1))
    return 号序


def _跑Git(工作树, *命令表) -> str:
    """夹具里跑一条 git ⇒ stdout；**干净环境**（剔 Git 定位变量）⇒ 不动外仓索引。"""
    from .合主干有界跑 import 干净环境
    回执 = subprocess.run(["git", *命令表], cwd=str(工作树), capture_output=True, text=True,
                       env=干净环境(), timeout=5)
    assert 回执.returncode == 0, (命令表, 回执.stdout, 回执.stderr)
    return 回执.stdout
