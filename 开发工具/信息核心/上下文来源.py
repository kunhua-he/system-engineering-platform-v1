# -*- coding: utf-8 -*-
"""上下文来源：只读权威源，活文档复用拆节口径；冻结落点读口另件。"""
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .表定义 import 库路径, 派生库路径
from .建库.条款 import 拆节

默认文档表 = ("项目文档/设计哲学.md", "项目文档/哲学.md", "项目文档/开发规范/开发规范.md")
文档账本件 = "项目文档/文档账本.json"
冻结登记件 = "契约声明/冻结登记.json"
片段窗宽 = 60
临时档名 = "临时文档"

class 上下文失败(Exception):
    """可编程处理的来源或输入失败。"""
    def __init__(self, 错误种类, 说明):
        super().__init__(说明)
        self.错误种类 = 错误种类

def 读指纹(文件路径):
    return hashlib.sha256(文件路径.read_bytes()).hexdigest() if 文件路径.is_file() else "missing"

def 读源JSON(文件路径):
    if not 文件路径.is_file():
        raise 上下文失败("missing", str(文件路径))
    try:
        return json.loads(文件路径.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as 失败原因:
        raise 上下文失败("corrupt", str(失败原因)) from 失败原因

@contextmanager
def 只读连接(文件路径):
    if not 文件路径.is_file():
        raise 上下文失败("missing", str(文件路径))
    for 后缀名 in ("-wal", "-journal"):
        旁件路径 = Path(str(文件路径) + 后缀名)
        if 旁件路径.exists() and 旁件路径.stat().st_size:
            raise 上下文失败("不一致", "来源有活动事务：" + str(旁件路径))
    连接 = sqlite3.connect(文件路径.as_uri() + "?mode=ro&immutable=1", uri=True)
    连接.row_factory = sqlite3.Row
    try:
        查询读数 = 连接.execute("pragma quick_check").fetchone()
        if 查询读数 is None or 查询读数[0] != "ok":
            raise 上下文失败("corrupt", "SQLite完整性检查失败")
        yield 连接
    finally:
        连接.close()

def 安全文档路径(树根, 文档路径):
    相对路径 = Path(文档路径)
    if 相对路径.is_absolute() or ".." in 相对路径.parts or 相对路径.suffix != ".md":
        raise 上下文失败("参数错误", "文档路径必须是仓内相对MD路径")
    文件路径 = 树根 / 相对路径
    if not 文件路径.resolve().is_relative_to(树根.resolve()):
        raise 上下文失败("参数错误", "文档路径越出工作树")
    return 文件路径

def 安全路径前缀(文档路径):
    """列序号用的文档路径：仓内相对、无 `..`、可为前缀（不必以 .md 结尾）。"""
    相对路径 = Path(文档路径)
    if 相对路径.is_absolute() or ".." in 相对路径.parts:
        raise 上下文失败("参数错误", "文档路径必须是仓内相对路径")
    return 文档路径

def 已定档(账本内容, 文档路径):
    """**盘上**这份 md 在 `项目文档/文档账本.json` 里有没有权威定义（`件` 一条，或命中 `按路径定档` 前缀）。

    **口径只此一处** —— 与判据㊶ / 建库 `扫md` 同一谓词。只认 `件` 会把「整目录同类」
    （`开发文档/临时文档/**` · `扩展根目录/**/说明*.md` · `项目文档/决策记录/**`）判成没定档：
    取条款 当场抛 corrupt，而建库 `扫md` 却照收进 `条款` ⇒ 两面口径不一致。

    ★ 本谓词只管「**盘上有件**、它有没有定义」；不能拿它当「这条路径该不该在盘上」——
    那是另一问，主人是 `件`（`取版本件表` 逐件要求 `is_file`）；正文已入库的旧路径不在盘上
    也不在 `件` 里，属 `条款` 镜像，不得报「已登记活文档缺失」。
    """
    if any(定档行["路径"] == 文档路径 for 定档行 in 账本内容.get("件", [])):
        return True
    return any(文档路径.startswith(定档行["前缀"]) for 定档行 in 账本内容.get("按路径定档", []))

def 取文档定档(账本内容, 文档路径):
    for 定档行 in 账本内容.get("件", []):
        if 定档行["路径"] == 文档路径:
            return 定档行["档"]
    for 定档行 in 账本内容.get("按路径定档", []):
        if 文档路径.startswith(定档行["前缀"]):
            return 定档行["档"]
    return "未知"

def 取版本件表(树根, 包含表, 账本路径=None, 操作值=""):
    账本内容 = 读源JSON(树根 / 文档账本件)
    if not isinstance(账本内容, dict) or not isinstance(账本内容.get("件"), list):
        raise 上下文失败("corrupt", "文档账本格式错误")
    件表 = [库路径(树根), 树根 / 文档账本件]
    if "条款" in 包含表 and 操作值 not in ("冻结落点", "文档索引"):
        件表.extend(安全文档路径(树根, 定档行["路径"]) for 定档行 in 账本内容["件"])
        for 文件路径 in 件表[2:]:
            if not 文件路径.is_file():
                raise 上下文失败("missing", "已登记活文档缺失：" + str(文件路径))
    if 操作值 == "文档索引":
        件表.append(派生库路径(树根))
    if "未完成" in 包含表:
        件表.append(库路径(树根))
    if 操作值 == "冻结落点":
        件表.append(树根 / 冻结登记件)
    if 账本路径 is not None:
        件表.append(账本路径)
    if "索引" in 包含表:
        from 代码地图.落点 import 库目录名, 库文件名
        件表.append(树根 / 库目录名 / 库文件名)
    for 文件路径 in 件表:
        if 文件路径 != 账本路径 and not 文件路径.resolve().is_relative_to(树根.resolve()):
            raise 上下文失败("参数错误", "来源路径越出工作树")
    return list(dict.fromkeys(件表)), 账本内容

def 取来源版本(件表):
    指纹表 = {}
    for 文件路径 in 件表:
        指纹表[str(文件路径)] = 读指纹(文件路径)
        for 后缀名 in ("-wal", "-journal"):
            旁件路径 = Path(str(文件路径) + 后缀名)
            指纹表[str(旁件路径)] = 读指纹(旁件路径)
    return 指纹表

def 造条目(类别名, 来源值, 权威档, 内容值, 指纹值, 新鲜度="当前读取", 冲突值=None):
    return {"类型": 类别名, "来源": 来源值, "源派生": "源", "权威档": 权威档,
            "内容": 内容值, "指纹": 指纹值, "新鲜度": 新鲜度, "冲突": 冲突值 or []}

def 取片段(标题值, 正文值, 检索词):
    """检索词在正文（或标题）命中处的前后窗；命中不到退回标题 / 正文开头。"""
    for 文本值 in (正文值 or "", 标题值 or ""):
        命中位置 = 文本值.find(检索词)
        if 命中位置 < 0:
            continue
        窗起, 窗止 = max(0, 命中位置 - 片段窗宽), min(len(文本值), 命中位置 + len(检索词) + 片段窗宽)
        片段值 = " ".join(文本值[窗起:窗止].split())
        return ("…" if 窗起 else "") + 片段值 + ("…" if 窗止 < len(文本值) else "")
    return " ".join((标题值 or 正文值 or "").split())[:120]

def 读条款条目(连接, 树根, 查询参数, 账本内容):
    操作值 = 查询参数["操作"]
    if 操作值 == "文档序号":
        yield from 读文档序号条目(连接, 树根, 查询参数, 账本内容)
        return
    if 操作值 == "取整件":
        yield from 读取整件条目(连接, 树根, 查询参数, 账本内容)
        return
    主题值, 精确表, 检索值 = 查询参数["主题"], 查询参数["文档路径序号表"], 查询参数["检索"]
    检索词 = 检索值 or 主题值
    if 精确表:
        定位集 = {(条款定位["文档路径"], 条款定位["序号"]) for 条款定位 in 精确表}
        def 命中(文档路径, 序号值, 标题值, 正文值):
            return (文档路径, 序号值) in 定位集
        def 内容构造(文档路径, 序号值, 标题值, 正文值):
            return {"标题": 标题值, "正文": 正文值}
        条件文本 = " or ".join("(文档路径=? and 序号=?)" for 条款定位 in 精确表)
        参数表 = [字段值 for 条款定位 in 精确表 for 字段值 in (条款定位["文档路径"], 条款定位["序号"])]
    elif 检索词:
        def 命中(文档路径, 序号值, 标题值, 正文值):
            return 检索词 in 文档路径 + 标题值 + 正文值
        if 检索值:
            def 内容构造(文档路径, 序号值, 标题值, 正文值):
                return {"标题": 标题值, "片段": 取片段(标题值, 正文值, 检索词),
                        "定位": {"文档路径": 文档路径, "序号": 序号值}}
        else:
            def 内容构造(文档路径, 序号值, 标题值, 正文值):
                return {"标题": 标题值, "摘要": 正文值.splitlines()[0] if 正文值 else "",
                        "定位": {"文档路径": 文档路径, "序号": 序号值}}
        条件文本, 参数表 = "instr(文档路径,?)>0 or instr(标题,?)>0 or instr(正文,?)>0", [检索词] * 3
    else:
        默认集 = set(默认文档表)
        def 命中(文档路径, 序号值, 标题值, 正文值):
            return 文档路径 in 默认集
        # ★ 2026-10-08：默认列表**只给标题 + 定位**（不给正文摘要）—— 一次回一叠摘要噪声太大；
        #   要正文就按 `文档路径 + 序号` 精确取（或用 `取整件`）。命中总数由 `上下文读取` 另给 `命中数`。
        def 内容构造(文档路径, 序号值, 标题值, 正文值):
            return {"标题": 标题值, "定位": {"文档路径": 文档路径, "序号": 序号值}}
        条件文本, 参数表 = "文档路径 in (?,?,?)", list(默认文档表)
    文档缓存 = {}
    命中定位集 = set()
    for 定档行 in 账本内容["件"]:
        文档路径 = 定档行["路径"]
        文件路径 = 安全文档路径(树根, 文档路径)
        if not 文件路径.is_file():
            raise 上下文失败("missing", "已登记活文档缺失：" + 文档路径)
        文档缓存[文档路径] = 拆节(文件路径.read_text(encoding="utf-8"))
        for 序号值, (标题值, 正文值) in enumerate(文档缓存[文档路径]):
            if not 命中(文档路径, 序号值, 标题值, 正文值):
                continue
            命中定位集.add((文档路径, 序号值))
            条款行 = 连接.execute("select 标题,正文 from 条款 where 文档路径=? and 序号=?", (文档路径, 序号值)).fetchone()
            冲突表 = ["数据库镜像缺节"] if 条款行 is None else ([] if (标题值, 正文值) == tuple(条款行) else ["活源与数据库镜像内容不同"])
            yield 造条目("条款", {"文件": 文档路径, "序号": 序号值}, 定档行["档"], 内容构造(文档路径, 序号值, 标题值, 正文值), 读指纹(文件路径), 冲突值=冲突表)
    for 条款行 in 连接.execute("select * from 条款 where " + 条件文本 + " order by 文档路径,序号", 参数表):
        文档路径, 序号值 = 条款行["文档路径"], 条款行["序号"]
        命中定位集.add((文档路径, 序号值))
        if 文档路径 in 文档缓存 and 序号值 < len(文档缓存[文档路径]):
            continue
        文件路径 = 安全文档路径(树根, 文档路径)
        if 文件路径.is_file():
            if not 已定档(账本内容, 文档路径):
                raise 上下文失败("corrupt", "活文档没有定档：" + 文档路径)
            if 文档路径 not in 文档缓存:
                文档缓存[文档路径] = 拆节(文件路径.read_text(encoding="utf-8"))
            节表 = 文档缓存[文档路径]
            if 序号值 >= len(节表):
                yield 造条目("条款", {"文件": 文档路径, "序号": 序号值}, 取文档定档(账本内容, 文档路径), {"状态": "活源已无此节"}, 读指纹(文件路径), 冲突值=["镜像存在额外节"])
                continue
            标题值, 正文值 = 节表[序号值]
            冲突表 = [] if (标题值, 正文值) == (条款行["标题"], 条款行["正文"]) else ["活源与数据库镜像内容不同"]
            来源值, 指纹值 = {"文件": 文档路径, "序号": 序号值}, 读指纹(文件路径)
            档位值 = 取文档定档(账本内容, 文档路径)
        else:
            if any(定档行["路径"] == 文档路径 for 定档行 in 账本内容["件"]):
                raise 上下文失败("missing", "已登记活文档缺失：" + 文档路径)
            标题值, 正文值, 档位值 = 条款行["标题"], 条款行["正文"], 条款行["权威档"]
            来源值 = {"文件": str(库路径(树根)), "表": "条款", "主键": [文档路径, 序号值]}
            指纹值, 冲突表 = hashlib.sha256((标题值 + "\n" + 正文值).encode()).hexdigest(), []
        yield 造条目("条款", 来源值, 档位值, 内容构造(文档路径, 序号值, 标题值, 正文值), 指纹值, 冲突值=冲突表)
    if 精确表 and len(命中定位集) != len(定位集):
        raise 上下文失败("missing", "指定条款不存在")

def 读文档序号条目(连接, 树根, 查询参数, 账本内容):
    前缀值 = 查询参数["文档路径"]
    候选表 = {定档行["路径"] for 定档行 in 账本内容["件"]}
    候选表 |= {条款行[0] for 条款行 in 连接.execute("select distinct 文档路径 from 条款")}
    命中表 = sorted(文档路径 for 文档路径 in 候选表 if 文档路径 == 前缀值 or 文档路径.startswith(前缀值))
    if not 命中表:
        yield 造条目("文档", {"文档路径": 前缀值}, "未知", {"文档路径": 前缀值, "在库": False}, "missing")
        return
    for 文档路径 in 命中表:
        文件路径 = 安全文档路径(树根, 文档路径)
        镜像数 = 连接.execute("select count(*) from 条款 where 文档路径=?", (文档路径,)).fetchone()[0]
        已登记 = any(定档行["路径"] == 文档路径 for 定档行 in 账本内容["件"])
        冲突表 = []
        if 文件路径.is_file():
            try:
                节表 = 拆节(文件路径.read_text(encoding="utf-8"))
            except (UnicodeError, OSError) as 失败原因:
                yield 造条目("文档", {"文件": 文档路径}, 取文档定档(账本内容, 文档路径),
                            {"文档路径": 文档路径, "在库": True, "来源": "活文档读取失败", "节数": 镜像数},
                            读指纹(文件路径), 冲突值=["活文档读取失败：" + str(失败原因)[:60]])
                continue
            标题表 = [标题值 for 标题值, 正文值 in 节表]
            来源值, 指纹值 = "活文档", 读指纹(文件路径)
            if len(节表) != 镜像数:
                冲突表 = ["活源节数 %d 与镜像节数 %d 不同" % (len(节表), 镜像数)]
        elif 镜像数:
            标题表 = [条款行[0] for 条款行 in 连接.execute("select 标题 from 条款 where 文档路径=? order by 序号", (文档路径,))]
            来源值, 指纹值 = ("活文档缺失" if 已登记 else "条款镜像"), "missing"
            if 已登记:
                冲突表 = ["已登记活文档缺失，仅有条款镜像"]
        else:
            continue
        yield 造条目("文档", {"文件": 文档路径} if 文件路径.is_file() else {"文件": str(库路径(树根)), "表": "条款", "主键": 文档路径},
                    取文档定档(账本内容, 文档路径),
                    {"文档路径": 文档路径, "在库": True, "来源": 来源值, "节数": len(标题表), "标题表": 标题表},
                    指纹值, 冲突值=冲突表)

def 读文档索引条目(树根, 查询参数):
    """读派生表 `文档索引`（`条款` 的 路径·序号·标题 投影）⇒ 条目：按文档路径（可前缀）列 序号 + 标题。
    **不假绿**：派生库 / 表不在 ⇒ `missing`；与 `条款` 集不一致 ⇒ `不一致`（两种都明说「先跑 `信息核心.py 建库`」）；
    有匹配 ⇒ 逐节给 (文档路径, 序号, 标题)；无匹配 ⇒ 回一条明确「匹配数 = 0」的条目。
    """
    前缀值 = 查询参数["文档路径"]
    派生库件 = 派生库路径(树根)
    if not 派生库件.is_file():
        raise 上下文失败("missing", "派生库不在（%s）⇒ 先跑 `信息核心.py 建库`" % 派生库件)
    with 只读连接(派生库件) as 索引连接:
        if 索引连接.execute(
                "select name from sqlite_master where type='table' and name='文档索引'").fetchone() is None:
            raise 上下文失败("missing", "派生表 `文档索引` 不在 ⇒ 先跑 `信息核心.py 建库`")
        索引行 = 索引连接.execute(
            "select 文档路径, 序号, 标题 from 文档索引 "
            "where 文档路径=? or instr(文档路径, ?)=1 order by 文档路径, 序号",
            (前缀值, 前缀值)).fetchall()
        索引集 = {(文档路径, 序号值, 标题值) for 文档路径, 序号值, 标题值 in
                索引连接.execute("select 文档路径, 序号, 标题 from 文档索引")}
    with 只读连接(库路径(树根)) as 规则连接:
        条款集 = {(文档路径, 序号值, 标题值) for 文档路径, 序号值, 标题值 in
                规则连接.execute("select 文档路径, 序号, 标题 from 条款")}
    if 索引集 != 条款集:
        raise 上下文失败("不一致", "派生表 `文档索引` 与 `条款` 不一致（派生表过期）⇒ 先跑 `信息核心.py 建库`")
    if not 索引行:
        yield 造条目("文档索引", {"文件": str(派生库件), "表": "文档索引"}, "派生表",
                   {"文档路径": 前缀值, "匹配数": 0}, "missing")
        return
    for 文档路径, 序号值, 标题值 in 索引行:
        yield 造条目("文档索引",
                   {"文件": str(派生库件), "表": "文档索引", "主键": [文档路径, 序号值]}, "派生表",
                   {"文档路径": 文档路径, "序号": 序号值, "标题": 标题值 or ""},
                   hashlib.sha256(("%s\n%d\n%s" % (文档路径, 序号值, 标题值 or "")).encode()).hexdigest())

def 读取整件条目(连接, 树根, 查询参数, 账本内容):
    文档路径 = 查询参数["文档路径"]
    段值 = 查询参数["序号段"]
    文件路径 = 安全文档路径(树根, 文档路径)
    已登记 = any(定档行["路径"] == 文档路径 for 定档行 in 账本内容["件"])
    镜像表 = {条款行["序号"]: 条款行 for 条款行 in 连接.execute("select * from 条款 where 文档路径=? order by 序号", (文档路径,))}
    if 文件路径.is_file():
        节表 = 拆节(文件路径.read_text(encoding="utf-8"))
        档位值, 指纹值 = 取文档定档(账本内容, 文档路径), 读指纹(文件路径)
        for 序号值, (标题值, 正文值) in enumerate(节表):
            if 段值 and not (段值[0] <= 序号值 <= 段值[1]):
                continue
            镜像行 = 镜像表.get(序号值)
            冲突表 = ["数据库镜像缺节"] if 镜像行 is None else ([] if (标题值, 正文值) == (镜像行["标题"], 镜像行["正文"]) else ["活源与数据库镜像内容不同"])
            yield 造条目("条款", {"文件": 文档路径, "序号": 序号值}, 档位值, {"标题": 标题值, "正文": 正文值}, 指纹值, 冲突值=冲突表)
        return
    if 已登记:
        raise 上下文失败("missing", "已登记活文档缺失：" + 文档路径)
    if not 镜像表:
        raise 上下文失败("missing", "指定文档不存在：" + 文档路径)
    for 序号值 in sorted(镜像表):
        if 段值 and not (段值[0] <= 序号值 <= 段值[1]):
            continue
        镜像行 = 镜像表[序号值]
        yield 造条目("条款", {"文件": str(库路径(树根)), "表": "条款", "主键": [文档路径, 序号值]}, 镜像行["权威档"],
                    {"标题": 镜像行["标题"], "正文": 镜像行["正文"]},
                    hashlib.sha256((镜像行["标题"] + "\n" + 镜像行["正文"]).encode()).hexdigest())

def 读名字条目(连接, 树根, 查询参数):
    名字值, 上限 = 查询参数["名字"], 查询参数["条数"]
    if 名字值:
        行表 = 连接.execute("select * from 命名登记 where 名字=? order by 名字", (名字值,)).fetchall()
        if not 行表:
            行表 = 连接.execute("select * from 命名登记 where instr(名字,?)>0 order by 名字 limit ?", (名字值, 上限)).fetchall()
    else:
        行表 = 连接.execute("select * from 命名登记 order by 名字 limit ?", (上限,)).fetchall()
    for 名字行 in 行表:
        内容值 = dict(名字行)
        yield 造条目("名字", {"文件": str(库路径(树根)), "表": "命名登记", "主键": 名字行["名字"]}, "命名登记",
                    内容值, hashlib.sha256(json.dumps(内容值, ensure_ascii=False).encode()).hexdigest())


def 开工号命中(检索词: str) -> tuple:
    """检索词像开工号（`v1-` 前缀或纯数字）⇒ `(SQL 片段, 绑定参数)`；否则 `("", [])`。

    `v1-` 前缀按**开工号前缀**命中；纯数字按**开工号尾段**命中（`540` ⇒ `v1-100540`）。
    不是开工号形状 ⇒ 空表，调用方退回原来的按 `工作内容` 子串匹配（口径不变）。
    """
    if 检索词.startswith("v1-"):
        return "(开工号=? or 开工号 like ?)", [检索词, 检索词 + "%"]
    if 检索词.isascii() and 检索词.isdigit():
        return "(开工号=? or 开工号 like ?)", ["v1-" + 检索词, "%" + 检索词]
    return "", []

def 展开台账成员(台账行: dict) -> dict:
    """台账一行的**成员展开**：`缺什么` 与 `落点` 里嵌的「· [号] …」逐条拆出并对照。

    台账把若干成员挤在一格文本里（如「架构工作包」那几行）⇒ 数成员、核「缺落一致」原先只能
    手写脚本。本函数是那条口径的唯一实现：两栏都以 `· [号]` 起一条，`缺什么` 有而 `落点` 无
    ⇒ 记进 `缺落不符`。
    """
    成员明细, 落点号集 = [], set()
    for 源码行 in (台账行.get("缺什么") or "").splitlines():
        命中 = re.match(r"^· \[(\d+)\]\s*(.*)$", 源码行)
        if 命中:
            成员明细.append((int(命中.group(1)), 命中.group(2)))
    for 源码行 in (台账行.get("落点") or "").splitlines():
        命中 = re.match(r"^· \[(\d+)\]", 源码行)
        if 命中:
            落点号集.add(int(命中.group(1)))
    缺落不符 = [号值 for 号值, _ in 成员明细 if 号值 not in 落点号集]
    return {"成员明细": [{"号": 号值, "文本": 摘录值[:80]} for 号值, 摘录值 in 成员明细],
            "成员数": len(成员明细), "缺落一致": not 缺落不符, "缺落不符": 缺落不符}


def 读上下文条目(树根, 查询参数, 账本内容, 账本路径=None, 提交值=""):
    操作值, 包含表 = 查询参数["操作"], 查询参数["包含"]
    if 操作值 == "冻结落点":
        from .上下文冻结落点 import 读冻结落点条目
        yield from 读冻结落点条目(树根, 查询参数)
        return
    if 操作值 == "文档索引":
        yield from 读文档索引条目(树根, 查询参数)
        return
    检索词 = 查询参数["检索"] or 查询参数["主题"]
    # 纯数字检索词（台账号形状）按台账号精确命中台账那一条，不再退回模糊检索（见下方 未完成 段）。
    命中台账号 = 检索词 if ("未完成" in 包含表 and 检索词.isascii() and 检索词.isdigit()) else ""
    with 只读连接(库路径(树根)) as 连接:
        if "条款" in 包含表 and not (命中台账号 and not 查询参数["文档路径序号表"]):
            yield from 读条款条目(连接, 树根, 查询参数, 账本内容)
        if "规则" in 包含表 and not 命中台账号:
            条件文本 = "instr(类,?)>0 or instr(名,?)>0 or instr(内容,?)>0" if 检索词 else "类=?"
            参数表 = [检索词] * 3 if 检索词 else ["命名口径"]
            for 规则行 in 连接.execute("select * from 规则 where " + 条件文本 + " order by 编号", 参数表):
                内容值 = dict(规则行)
                yield 造条目("规则", {"文件": str(库路径(树根)), "表": "规则", "主键": 规则行["编号"]}, "规则库", 内容值, hashlib.sha256(json.dumps(内容值, ensure_ascii=False).encode()).hexdigest())
        if "名字" in 包含表:
            yield from 读名字条目(连接, 树根, 查询参数)
    if "未完成" in 包含表:
        # ★ 2026-10-13：台账改「库即存本」（仓内源件 `未完成.json` 已删）⇒ 从库读，不再读 JSON。
        #   形状照同件上面 `规则` 那一支：文件 = 库路径 · 表 = 未完成 · 主键 = 号 · 指纹 = 内容 sha。
        #   库的 missing / corrupt 由 `只读连接` 统一报，不再有「源格式错误」这一支。
        with 只读连接(库路径(树根)) as 连接:
            台账行表 = 连接.execute(
                "select 号, 缺什么, 落点, 验证命令 from 未完成 order by 号").fetchall()
        现有号表 = [台账行["号"] for 台账行 in 台账行表]
        for 台账行 in 台账行表:
            内容值 = dict(台账行)
            if 查询参数.get("展开成员"):
                内容值.update(展开台账成员(内容值))
            if 命中台账号 != str(台账行["号"]) and (
                命中台账号
                or (检索词 and 检索词 not in json.dumps(内容值, ensure_ascii=False))
            ):
                continue
            未完成条目 = 造条目(
                "未完成",
                {"文件": str(库路径(树根)), "表": "未完成", "主键": 台账行["号"]},
                "台账",
                内容值,
                hashlib.sha256(json.dumps(内容值, ensure_ascii=False).encode()).hexdigest(),
            )
            未完成条目["提交"] = 提交值
            yield 未完成条目
        if 命中台账号 and 命中台账号 not in [str(台账号) for 台账号 in 现有号表]:
            yield 造条目(
                "未完成",
                {"文件": str(库路径(树根)), "表": "未完成", "主键": 检索词},
                "台账",
                {"号": 检索词, "状态": "台账无此号", "现有号": 现有号表[:50]},
                hashlib.sha256(检索词.encode()).hexdigest(),
            )
    if "开工" in 包含表:
        号条件, 号参数 = 开工号命中(检索词)
        if 号条件:
            筛选, 筛选参数 = 号条件, 号参数
        else:
            筛选, 筛选参数 = "(?='' or instr(工作内容,?)>0)", [检索词, 检索词]
        with 只读连接(账本路径) as 连接:
            for 开工行 in 连接.execute(
                    "select * from 开工 where " + 筛选 + " and (?='' or 开工号=?) order by 开工号 desc",
                    筛选参数 + [查询参数["开工ID"], 查询参数["开工ID"]]):
                开工条目 = 造条目("开工", {"文件": str(账本路径), "表": "开工", "主键": 开工行["开工号"]}, "开工记录", dict(开工行), 读指纹(账本路径))
                开工条目["提交"] = 提交值
                yield 开工条目
    if "索引" in 包含表:
        from 代码地图.落点 import 库目录名, 库文件名
        from 代码地图.查询 import 可读说明
        索引路径 = 树根 / 库目录名 / 库文件名
        with 只读连接(索引路径) as 连接:
            for 名称 in ("nodes", "edges", "files", "project_metadata"):
                if 连接.execute("select name from sqlite_master where type='table' and name=?", (名称,)).fetchone() is None:
                    raise 上下文失败("corrupt", "索引缺少必要表：" + 名称)
            新鲜提示 = 可读说明(根目录=树根, 库路径=索引路径)
        索引读数 = {"查询工具": "v1_symbol", "能力限制": "只返回已有新鲜度能力和指针；计数查询的mode=ro可能写SQLite旁件，故此口不调用"}
        索引条目 = 造条目("索引", {"文件": str(索引路径)}, "代码地图", 索引读数, 读指纹(索引路径), "陈旧" if 新鲜提示 else "新鲜")
        索引条目.update({"源派生": "派生", "说明": 新鲜提示})
        yield 索引条目
