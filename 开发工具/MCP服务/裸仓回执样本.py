# -*- coding: utf-8 -*-
"""裸仓回执样本 —— `v1_shell` 的 **Git 目标回执** 自检（判据 ㊽ 经 `自检样本.跑自检` 跑它）。

**为什么要单开一件**：`自检样本.py` 已顶 400 行硬数（判据 ⑲），照先例（`http 传输样本`）把本面
挪成同级件。

**为什么必须有这一档**：目标树是 **bare 仓根**（`core.bare=true`）时，`v1_shell` 会给子
进程注入**进程级** `GIT_DIR`/`GIT_WORK_TREE`（不注入则那棵树里 git 报「must be run in a work tree」）
—— 这两键会把该回执里**所有** git（含 `git -C <别的树>`）都带回本仓。故回执**必须**明说「Git 目标＝
本仓 · `git -C` 不切目标」并给跨树指引（顶层 `开工ID` / `v1_tree` / 显式 `--git-dir`）；非 bare 目标
**不许**出现该提示（不给正常树加噪声）。夹具只搭临时 bare 根 + 普通目录，不碰真仓、不落仓。
"""
import shutil
import tempfile
from pathlib import Path


def 样本列表(仓根, 工具表):
    """`v1_shell` 的 Git 目标回执 正反样本 ⇒ 样本表（临时夹具，跑完即删）。"""
    出口 = 工具表["v1_shell"][0]
    临时根 = Path(tempfile.mkdtemp(prefix="v1裸仓回执自检-"))
    样本表 = []
    try:
        裸仓根 = 临时根 / "裸仓"
        (裸仓根 / ".git").mkdir(parents=True)
        (裸仓根 / ".git" / "config").write_text("[core]\n\tbare = true\n", encoding="utf-8")
        普通仓根 = 临时根 / "普通仓"
        普通仓根.mkdir()
        退出码, 裸回执 = 出口({"操作": "执行", "参数": {"命令": "echo v1裸仓回执固定词"}}, 裸仓根)
        样本表.append(("v1_shell bare 仓根：退出码 %d · 带「Git 目标」提示 %s · 带跨树指引（v1_tree） %s"
                 % (退出码, "是" if "Git 目标" in 裸回执 else "否",
                    "是" if "v1_tree" in 裸回执 else "否"),
                退出码 == 0 and "v1裸仓回执固定词" in 裸回执
                and "Git 目标" in 裸回执 and "v1_tree" in 裸回执))
        退出码, 普通回执 = 出口({"操作": "执行", "参数": {"命令": "echo x"}}, 普通仓根)
        样本表.append(("v1_shell 非 bare 目标：回执**不**带「Git 目标」提示 %s（不给正常树加噪声）"
                 % ("是" if "Git 目标" not in 普通回执 else "否"),
                退出码 == 0 and "Git 目标" not in 普通回执))
    finally:
        shutil.rmtree(临时根, ignore_errors=True)
    return 样本表
