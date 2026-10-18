# -*- coding: utf-8 -*-
"""放行结果 —— 把「提交放行」跑过的**全量验证**按**树内容指纹**记一笔，给「释放」复用。

**为什么要有它**（债务 573）：一次完整收口链 ≈ 2.5 分钟、等待占九成 —— 提交放行（闸 0 + 自测 +
案例）跑完，释放**又跑一遍闸 0**（实测约 13 秒/腿）。同一开工、同一棵树、**内容一字未变**时，
那一遍是重复劳动。

**口径（fail-safe：只省重复劳动，不放松门禁）**：
  · 键 = **树内容指纹**（`取树指纹`：树根 + HEAD + 索引 + `git status --porcelain -z -uall`）。
    不按「开工号」也不按「HEAD」—— 脏改动改了内容而 HEAD 不动，按 HEAD 复用就是假绿；
  · 只在放行链**真跑到尾且全绿**时才记（链上每一步都在 `&&` 之后 ⇒ 走到记账那一步即全绿）；
  · 读的时候指纹对不上 / 记录不在 / 读不动 / 记录格式不是本版 ⇒ **一律当没记**（回落到真跑闸 0）；
  · **不设时长上限**（判据只有「内容一字未变」一条）：同一份内容上跑的同一批判据 ⇒ 读数就是同一份，
    挂钟不参与判定（`时刻` 只作留痕）；原先给 3600 秒既撞判据 ㊲ 的秒级上限、对正确性又无贡献；
  · 落点走 `运行数据根` 包的 `缓存` 子目录（不自拼路径，判据 ㉕）。

**读了它的人**：`仓操作.跑验证` —— 命中就跳过闸 0 并在回执里逐字报「复用」（读数可见，不静默）。
"""

import hashlib
import json
import time
from pathlib import Path

from ..施工管理.仓操作 import 变更路径表, 跑命令   # 先导仓操作：它把 开发工具/ 挂上 sys.path
from 代码地图 import 文件指纹              # noqa: E402
from 运行数据根 import 确保子目录, 解析当前环境   # noqa: E402

放行目录名 = "放行结果"              # `<运行数据根>/缓存/` 下那一层子目录名
放行记录格式 = 2                    # 记录件的形状版本：形状一变 ⇒ 旧记录一律当没记（不靠挂钟）


def 取树指纹(树根) -> str:
    """这棵树**当前内容**的指纹 ⇒ sha256 十六进制；任一条 git 问句答不出 ⇒ 空串（**不猜**）。

    三个面各取一份：HEAD（已提交的）· 索引（暂存的）· **每个脏件的内容指纹**。
    ★ 只取 `git status` 的**状态行**不够（实测）：新建的未跟踪件在状态行里恒是 `??`，
      改它的内容状态行一字不变 ⇒ 指纹不动、复用就成假绿。所以脏件一律取**内容指纹**。
    """
    指纹摘要 = hashlib.sha256()
    指纹摘要.update(str(Path(树根).resolve()).encode("utf-8"))
    退出码, 头提交 = 跑命令(["git", "rev-parse", "HEAD"], cwd=树根)
    if 退出码 != 0:
        return ""
    退出码, 索引行 = 跑命令(["git", "ls-files", "-s", "-z"], cwd=树根)
    if 退出码 != 0:
        return ""
    退出码, 变更表 = 变更路径表(树根)
    if 退出码 != 0:
        return ""
    指纹摘要.update(b"\0" + 头提交.encode("utf-8", "replace"))
    指纹摘要.update(b"\0" + 索引行.encode("utf-8", "replace"))
    for 路径 in 变更表:
        件路径 = Path(树根) / 路径
        指纹摘要.update(b"\0" + 路径.encode("utf-8", "replace"))
        指纹摘要.update(b"\0" + (文件指纹(str(件路径)) if 件路径.is_file() else "").encode("utf-8"))
    return 指纹摘要.hexdigest()


def 记录路径(树根):
    """这棵树当前内容对应的放行记录件 ⇒ `Path`；指纹算不出 ⇒ `None`。"""
    指纹 = 取树指纹(树根)
    if not 指纹:
        return None
    return 确保子目录(解析当前环境(), "缓存") / 放行目录名 / (指纹 + ".json")


def 记放行(树根, 开工号: str = "") -> str:
    """放行链**全绿**时记一笔 ⇒ 树指纹（记不上给空串）。"""
    路径 = 记录路径(树根)
    if 路径 is None:
        return ""
    try:
        路径.parent.mkdir(parents=True, exist_ok=True)
        路径.write_text(json.dumps({"树指纹": 路径.stem, "开工号": str(开工号 or ""),
                                 "格式": 放行记录格式, "时刻": time.time()}, ensure_ascii=False),
                        encoding="utf-8")
    except OSError:
        return ""
    return 路径.stem


def 有放行(树根) -> bool:
    """这棵树**现在这个内容**有没有一笔有效的全绿放行记录。任何一点对不上 ⇒ 假（回落真跑）。"""
    路径 = 记录路径(树根)
    if 路径 is None or not 路径.is_file():
        return False
    try:
        放行记录 = json.loads(路径.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(放行记录, dict) or 放行记录.get("树指纹") != 路径.stem:
        return False
    return 放行记录.get("格式") == 放行记录格式
