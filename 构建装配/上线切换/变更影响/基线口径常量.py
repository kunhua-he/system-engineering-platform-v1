"""常量 —— 基线读法与扫描口径（都在这一处，别处只引不抄）。"""

from pathlib import Path

仓根 = Path(__file__).resolve().parents[3]
冻结登记相对路径 = "契约声明/冻结登记.json"
# 允许的三种演进：`契约声明/冻结登记.json` 的 `说明` 只认这三样 —— 别的形状变化必须冻结例外登记。
允许演进种类 = ("新增号段", "新增段类型号", "新增外延字段")
# git 路径：铁律点名 CommandLineTools 那一份（PATH 上的可能是别的分发）。
git命令路径 = "/Library/Developer/CommandLineTools/usr/bin/git"
# 影响面的扫描面 = **代码面**（谁依赖这个形状）；文档面不算。
扫描后缀 = (".rs", ".py", ".json", ".toml")
跳过目录 = {"构建环境", "target", "__pycache__", ".git", ".codegraph", "制品产物", "node_modules"}
# 本评估面自身：数引用件时跳过（本面引本面不算「谁依赖它」）。
本评估面 = "构建装配/上线切换/变更影响"
