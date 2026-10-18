# -*- coding: utf-8 -*-
"""死腿检测 —— 只读扫子代理元数据，列出「疑似死腿」。

**为何要它**：`~/.zcode/cli/agents/*/agent_*/metadata.json` 的 `status` 会撒谎
（实测 4 条死腿全写 `running`）。审计给出的**可直接判死**判据：`status == "running"`
且 `createdAt` 距今 > 阈值（默认 900 秒）且同目录无 `output.txt`。本件是那份判据的
唯一实现：`扫描死腿` 是**纯函数**（注入 `现在秒` 即可复现），入口 `死腿.py` 只做路由。

**只读**：零写盘 · 不杀进程 · 不发消息 —— 只扫 `metadata.json` 与 `output.txt` 的存在性。
**输出有界**：超过 `上限条数` 截断并给总数（`截断` 标志 + 未列出条数）。
"""
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

默认判死秒数 = 900
默认上限条数 = 20
默认代理根 = Path.home() / ".zcode" / "cli" / "agents"


def 解析时刻(文本值):
    """ISO 时刻文本（含尾 `Z`）⇒ 纪元秒；空值 / 解不动 ⇒ None。"""
    if not 文本值:
        return None
    try:
        return datetime.fromisoformat(文本值.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def 兄弟有输出(代理目录):
    """同批（同会话目录）里的**别的**子代理目录有没有 `output.txt`（旁证）。"""
    for 兄弟目录 in 代理目录.parent.glob("agent_*"):
        if 兄弟目录 != 代理目录 and (兄弟目录 / "output.txt").is_file():
            return True
    return False


def 读元数据(元数据路径):
    """读一份 `metadata.json` ⇒ 字典；读不动 / 不是 JSON ⇒ None。"""
    try:
        return json.loads(Path(元数据路径).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def 扫描死腿(代理根=None, 判死秒数=默认判死秒数, 上限条数=默认上限条数, 当前纪元秒数=None):
    """纯函数 ⇒ `{总数, 条数, 截断, 记录, 扫描数}`。只读。

    疑似死腿 = `status == "running"` ∧ 距今 > `判死秒数` ∧ 同目录无 `output.txt`。
    `当前纪元秒数` 留空取当前时刻（自测注入固定值 ⇒ 可复现）。
    """
    扫描根 = Path(代理根) if 代理根 else 默认代理根
    当前时刻 = 当前纪元秒数 if 当前纪元秒数 is not None else datetime.now().timestamp()
    疑似表 = []
    扫描数 = 0
    for 元数据路径 in sorted(扫描根.glob("*/agent_*/metadata.json")):
        扫描数 += 1
        元数据 = 读元数据(元数据路径)
        if not 元数据 or 元数据.get("status") != "running":
            continue
        代理目录 = 元数据路径.parent
        if (代理目录 / "output.txt").is_file():
            continue
        创建纪元秒数 = 解析时刻(元数据.get("createdAt"))
        if 创建纪元秒数 is None:
            continue
        距今秒数 = 当前时刻 - 创建纪元秒数
        if 距今秒数 <= 判死秒数:
            continue
        疑似表.append({"描述": 元数据.get("description", ""), "代理目录": str(代理目录),
                   "创建时刻": 元数据.get("createdAt", ""), "距今秒": int(距今秒数),
                   "兄弟有输出": 兄弟有输出(代理目录)})
    疑似表.sort(key=lambda 记录条: 记录条["距今秒"], reverse=True)
    return {"总数": len(疑似表), "条数": min(len(疑似表), 上限条数),
            "截断": len(疑似表) > 上限条数, "记录": 疑似表[:上限条数], "扫描数": 扫描数}


def 渲染读数(读数):
    """把扫描读数渲染成有界文本 ⇒ 打印，返 0。"""
    行表 = ["疑似死腿 %d 条（共扫 %d 份元数据）：" % (读数["总数"], 读数["扫描数"])]
    for 记录条 in 读数["记录"]:
        行表.append("  · %s  距今 %d 秒  兄弟有输出=%s\n      %s"
                  % (记录条["描述"], 记录条["距今秒"],
                     "是" if 记录条["兄弟有输出"] else "否", 记录条["代理目录"]))
    if 读数["截断"]:
        行表.append("  …还有 %d 条未列出（上限 %d）" % (读数["总数"] - 读数["条数"], 读数["条数"]))
    print("\n".join(行表))
    return 0


def 跑一遍(代理根=None, 判死秒数=默认判死秒数, 上限条数=默认上限条数):
    """扫一遍并渲染（入口只调这一个）。"""
    return 渲染读数(扫描死腿(代理根, 判死秒数, 上限条数))


def 跑自测():
    """反向样本：造夹具元数据树，断言抓得住死腿、放得过活腿。"""
    夹具根 = Path(tempfile.mkdtemp(prefix="死腿自测_"))
    try:
        会话目录 = 夹具根 / "sess_样例"
        死腿目录 = 会话目录 / "agent_死腿"
        活腿目录 = 会话目录 / "agent_活腿"
        死腿目录.mkdir(parents=True)
        活腿目录.mkdir(parents=True)
        (死腿目录 / "metadata.json").write_text(
            json.dumps({"status": "running", "createdAt": "2020-01-01T00:00:00.000Z",
                        "description": "样例死腿"}), encoding="utf-8")
        (活腿目录 / "metadata.json").write_text(
            json.dumps({"status": "running", "createdAt": "2020-01-01T00:00:00.000Z",
                        "description": "样例活腿"}), encoding="utf-8")
        (活腿目录 / "output.txt").write_text("done", encoding="utf-8")
        读数 = 扫描死腿(夹具根, 判死秒数=900, 当前纪元秒数=1600000000.0)
        通过 = (读数["总数"] == 1 and 读数["记录"][0]["描述"] == "样例死腿"
              and 读数["记录"][0]["兄弟有输出"] is True)
        print("死腿自测：%s（总数=%d）" % ("通过" if 通过 else "失败", 读数["总数"]))
        return 0 if 通过 else 1
    finally:
        shutil.rmtree(夹具根, ignore_errors=True)
