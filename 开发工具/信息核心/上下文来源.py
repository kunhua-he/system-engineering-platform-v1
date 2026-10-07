# -*- coding: utf-8 -*-
"""上下文来源：只读权威源，活文档复用拆节口径。"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .表定义 import 库路径
from .建库.条款 import 拆节

默认文档表 = ("项目文档/设计哲学.md", "项目文档/哲学.md", "项目文档/开发规范/开发规范.md")
文档账本件 = "项目文档/文档账本.json"
未完成件 = "开发工具/信息核心/未完成.json"


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


def 取文档定档(账本内容, 文档路径):
    for 定档行 in 账本内容.get("件", []):
        if 定档行["路径"] == 文档路径:
            return 定档行["档"]
    for 定档行 in 账本内容.get("按路径定档", []):
        if 文档路径.startswith(定档行["前缀"]):
            return 定档行["档"]
    return "未知"


def 取版本件表(树根, 包含表, 账本路径=None):
    账本内容 = 读源JSON(树根 / 文档账本件)
    if not isinstance(账本内容, dict) or not isinstance(账本内容.get("件"), list):
        raise 上下文失败("corrupt", "文档账本格式错误")
    件表 = [库路径(树根), 树根 / 文档账本件]
    if "条款" in 包含表:
        件表.extend(安全文档路径(树根, 定档行["路径"]) for 定档行 in 账本内容["件"])
        for 文件路径 in 件表[2:]:
            if not 文件路径.is_file():
                raise 上下文失败("missing", "已登记活文档缺失：" + str(文件路径))
    if "未完成" in 包含表:
        件表.append(树根 / 未完成件)
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


def 读条款条目(连接, 树根, 查询参数, 账本内容):
    主题值, 精确表 = 查询参数["主题"], 查询参数["文档路径序号表"]
    if 精确表:
        条件文本 = " or ".join("(文档路径=? and 序号=?)" for 条款定位 in 精确表)
        参数表 = [字段值 for 条款定位 in 精确表 for 字段值 in (条款定位["文档路径"], 条款定位["序号"])]
    elif 主题值:
        条件文本, 参数表 = "instr(文档路径,?)>0 or instr(标题,?)>0 or instr(正文,?)>0", [主题值] * 3
    else:
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
            if 精确表:
                if not any(条款定位 == {"文档路径": 文档路径, "序号": 序号值} for 条款定位 in 精确表):
                    continue
            elif 主题值:
                if 主题值 not in 文档路径 + 标题值 + 正文值:
                    continue
            else:
                continue
            命中定位集.add((文档路径, 序号值))
            条款行 = 连接.execute("select 标题,正文 from 条款 where 文档路径=? and 序号=?", (文档路径, 序号值)).fetchone()
            冲突表 = ["数据库镜像缺节"] if 条款行 is None else ([] if (标题值, 正文值) == tuple(条款行) else ["活源与数据库镜像内容不同"])
            内容值 = {"标题": 标题值, "正文": 正文值} if 精确表 else {"标题": 标题值, "摘要": 正文值.splitlines()[0] if 正文值 else "", "定位": {"文档路径": 文档路径, "序号": 序号值}}
            yield 造条目("条款", {"文件": 文档路径, "序号": 序号值}, 定档行["档"], 内容值, 读指纹(文件路径), 冲突值=冲突表)
    for 条款行 in 连接.execute("select * from 条款 where " + 条件文本 + " order by 文档路径,序号", 参数表):
        文档路径, 序号值 = 条款行["文档路径"], 条款行["序号"]
        命中定位集.add((文档路径, 序号值))
        if 文档路径 in 文档缓存 and 序号值 < len(文档缓存[文档路径]):
            continue
        文件路径 = 安全文档路径(树根, 文档路径)
        if 文件路径.is_file():
            if not any(定档行["路径"] == 文档路径 for 定档行 in 账本内容["件"]):
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
        内容值 = {"标题": 标题值, "正文": 正文值} if 精确表 else {"标题": 标题值, "摘要": 正文值.splitlines()[0] if 正文值 else "", "定位": {"文档路径": 文档路径, "序号": 序号值}}
        yield 造条目("条款", 来源值, 档位值, 内容值, 指纹值, 冲突值=冲突表)
    if 精确表 and len(命中定位集) != len({(条款定位["文档路径"], 条款定位["序号"]) for 条款定位 in 精确表}):
        raise 上下文失败("missing", "指定条款不存在")


def 读上下文条目(树根, 查询参数, 账本内容, 账本路径=None):
    主题值, 包含表 = 查询参数["主题"], 查询参数["包含"]
    # 纯数字主题（台账号形状）按台账号精确命中，不再退回模糊检索（见下方 未完成 段）。
    命中台账号 = 主题值 if ("未完成" in 包含表 and 主题值.isascii() and 主题值.isdigit()) else ""
    with 只读连接(库路径(树根)) as 连接:
        if "条款" in 包含表 and not (命中台账号 and not 查询参数["文档路径序号表"]):
            yield from 读条款条目(连接, 树根, 查询参数, 账本内容)
        if "规则" in 包含表 and not 命中台账号:
            条件文本 = "instr(类,?)>0 or instr(名,?)>0 or instr(内容,?)>0" if 主题值 else "类=?"
            参数表 = [主题值] * 3 if 主题值 else ["命名口径"]
            for 规则行 in 连接.execute("select * from 规则 where " + 条件文本 + " order by 编号", 参数表):
                内容值 = dict(规则行)
                yield 造条目("规则", {"文件": str(库路径(树根)), "表": "规则", "主键": 规则行["编号"]}, "规则库", 内容值, hashlib.sha256(json.dumps(内容值, ensure_ascii=False).encode()).hexdigest())
    if "未完成" in 包含表:
        台账内容 = 读源JSON(树根 / 未完成件)
        if not isinstance(台账内容, dict) or not isinstance(台账内容.get("行"), list):
            raise 上下文失败("corrupt", "未完成源格式错误")
        for 台账行 in 台账内容["行"]:
            if not isinstance(台账行, list) or len(台账行) != 4:
                raise 上下文失败("corrupt", "未完成行须有四栏")
            if 命中台账号:
                if str(台账行[0]) == 命中台账号:
                    yield 造条目("未完成", {"文件": 未完成件, "主键": 台账行[0]}, "台账", dict(zip(("号", "缺什么", "落点", "验证命令"), 台账行)), 读指纹(树根 / 未完成件))
            elif not 主题值 or 主题值 in json.dumps(台账行, ensure_ascii=False):
                yield 造条目("未完成", {"文件": 未完成件, "主键": 台账行[0]}, "台账", dict(zip(("号", "缺什么", "落点", "验证命令"), 台账行)), 读指纹(树根 / 未完成件))
        if 命中台账号 and not any(str(台账行[0]) == 命中台账号 for 台账行 in 台账内容["行"]):
            yield 造条目("未完成", {"文件": 未完成件, "主键": 主题值}, "台账",
                         {"号": 主题值, "状态": "台账无此号", "现有号": [台账行[0] for 台账行 in 台账内容["行"]][:50]},
                         读指纹(树根 / 未完成件))
    if "开工" in 包含表:
        with 只读连接(账本路径) as 连接:
            for 开工行 in 连接.execute("select * from 开工 where (?='' or instr(工作内容,?)>0) and (?='' or 开工号=?) order by 开工号 desc", (主题值, 主题值, 查询参数["开工ID"], 查询参数["开工ID"])):
                yield 造条目("开工", {"文件": str(账本路径), "表": "开工", "主键": 开工行["开工号"]}, "开工记录", dict(开工行), 读指纹(账本路径))
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
