# -*- coding: utf-8 -*-
"""批量预检样本：子进程走真实MCP帧，断言拒绝汇总、顺序模拟与零写。"""
import contextlib
import functools
import hashlib
import json
import os
import select
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def 扫一遍(仓根: Path) -> list:
    """夹具账本与源码均隔离；实际写口另验拒绝码及部分完成语义。"""
    from . import 开工账本 as 账本
    from . import 修改

    输出表 = []
    with tempfile.TemporaryDirectory(prefix="v1预检样本-") as 临时根, contextlib.ExitStack() as 真连:
        临时根 = Path(临时根)
        工作树 = 临时根 / "工作树"
        工作树.mkdir()
        (工作树 / "开发工具/信息核心").mkdir(parents=True)
        库件 = 工作树 / "开发工具/信息核心/信息核心.db"
        连接 = sqlite3.connect(str(库件))
        连接.execute("create table 命名登记(名字 text, 状态 text)")
        连接.execute("create table 命名例外(名字 text)")
        连接.execute("insert into 命名登记 values ('配置文件','合格')")
        连接.commit()
        连接.close()
        (工作树 / "构建装配/一键验证").mkdir(parents=True)
        (工作树 / "构建装配/一键验证/入口白名单.json").write_text('{"白名单": []}', encoding="utf-8")
        (工作树 / ".codegraph").mkdir()
        (工作树 / ".codegraph/索引样本.db").write_bytes(b"index-sentinel")
        (工作树 / "漂移.py").write_text("配置文件 = 1\n", encoding="utf-8")
        (工作树 / "未认领.py").write_text("配置文件 = 1\n", encoding="utf-8")
        (工作树 / "重复.py").write_text("print(1)\nprint(1)\n", encoding="utf-8")
        (工作树 / "生成.py").write_text("# 生成物，禁手改\nprint(1)\n", encoding="utf-8")
        (工作树 / "二进制.db").write_bytes(b"\xff\x00")
        (工作树 / "语法.py").write_text("配置文件 = 0\n", encoding="utf-8")
        (工作树 / "删语法.py").write_text("  配置文件 = 0\n", encoding="utf-8")
        库件 = 账本.子目录路径(临时根 / "运行根", 账本.子目录类别) / 账本.库文件名
        库件.parent.mkdir(parents=True)
        连接 = sqlite3.connect(str(库件))
        for 文本行 in 账本.建表语句:
            连接.execute(文本行)
        连接.execute("insert into 开工 values (?,?,?,?,?,?,?)",
                   ("v1-样本", "样本", "样本", str(工作树), 账本.状态_进行中, "样本", None))
        连接.executemany("insert into 认领 values (?,?,?)", [
            ("v1-样本", "漂移.py", "旧指纹"),
            ("v1-样本", "重复.py", 修改.文件指纹(str(工作树 / "重复.py"))),
            ("v1-样本", "生成.py", 修改.文件指纹(str(工作树 / "生成.py"))),
            ("v1-样本", "二进制.db", 修改.文件指纹(str(工作树 / "二进制.db"))),
            ("v1-样本", "语法.py", 修改.文件指纹(str(工作树 / "语法.py"))),
            ("v1-样本", "删语法.py", 修改.文件指纹(str(工作树 / "删语法.py")))])
        语法件 = 工作树 / "语法.py"
        连接.commit()
        连接.close()
        from 运行数据根.口径 import 覆盖变量名
        环境表 = dict(os.environ)
        环境表.update({覆盖变量名: str(临时根 / "运行根"), "PYTHONDONTWRITEBYTECODE": "1"})
        文件句柄 = 真连.enter_context(subprocess.Popen(
            [sys.executable, "-B", str(仓根 / "开发工具/MCP服务.py")], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=环境表, cwd=仓根))
        真连.callback(文件句柄.kill)
        跑命令 = functools.partial(sys.modules[__name__].跑命令, 文件句柄=文件句柄)
        参数表 = {"开工ID": "v1-样本", "操作": "只检查", "参数": {"改动表": [
            {"路径": "漂移.py", "操作": "修改", "旧内容": "不存在", "新内容": "未登记配置 = 2\n未登记日志 = 3\n"},
            {"路径": "未认领.py", "操作": "修改", "旧内容": "不存在", "新内容": "未登记路径 = 4\n"},
            {"路径": "重复.py", "操作": "修改", "旧内容": "print(1)", "新内容": "print(2)"},
            {"路径": "生成.py", "操作": "修改", "旧内容": "print(1)", "新内容": "print(2)"},
            {"路径": "二进制.db", "操作": "修改", "旧内容": "不存在", "新内容": "存在"},
            {"路径": "../越界.py", "操作": "新建", "新内容": "print(1)"}]}}
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("多名字/认领/指纹/旧文/禁写/字段同回执", 退出码 == 0 and 查询读数["isError"]
                      and all(文本行 in 说明 for 文本行 in
                              ("未登记配置", "未登记日志", "认领拒绝", "指纹拒绝", "出现 0 次", "出现 2 次",
                               "禁写拒绝", "文本拒绝", "字段拒绝"))))
        参数表["参数"]["改动表"] = [
            {"路径": "新建.py", "操作": "新建", "新内容": "配置文件 = 1"},
            {"路径": "新建.py", "操作": "修改", "旧内容": "配置文件 = 1", "新内容": "配置文件 = 2"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("先建后改两条顺序模拟且真实写口前置拒绝仍明示", 退出码 == 0
                      and 说明.count("顺序内存模拟完成") == 2 and "真实写口前置拒绝" in 说明
                      and not (工作树 / "新建.py").exists()))
        参数表["参数"]["改动表"] = [{"路径": "新建.py", "操作": "新建", "新内容": "配置文件 = 1"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("合规候选预检0但不放行", 退出码 == 0 and not 查询读数["isError"]
                      and "预检不等放行" in 查询读数["content"][0]["text"]))
        参数表["参数"]["改动表"] = [{"路径": "__init__.py", "操作": "新建",
                           "新内容": "def 配置文件():\n    pass\n" + "# 占位\n" * 120}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("入口实现与行数仅报正式闸预警", 退出码 == 0 and "入口含实现" in 说明
                      and "入口行数" in 说明 and "正式闸预警" in 说明))
        参数表["参数"]["乱键"] = 1
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("未知参数键拒绝", 退出码 == 0 and 查询读数["isError"]
                      and "未知参数键" in 查询读数["content"][0]["text"]))
        参数表["参数"].pop("乱键")
        参数表["操作"] = "改"
        参数表["参数"]["改动表"] = [{"路径": "漂移.py", "操作": "修改",
                           "旧内容": "配置文件 = 1", "新内容": "配置文件 = 2"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("实际写入仍严格指纹拒绝且不给重认领洗白建议", 退出码 == 0 and 查询读数["isError"]
                      and "第 ③ 道闸" in 查询读数["content"][0]["text"]
                      and "不会为已有改动记账" in 查询读数["content"][0]["text"]))
        # 合规预检之后再漂移，真实写口仍重新对账。
        连接 = sqlite3.connect(str(库件))
        连接.execute("update 认领 set 指纹=? where 路径=?",
                   (修改.文件指纹(str(工作树 / "漂移.py")), "漂移.py"))
        连接.commit()
        连接.close()
        参数表["操作"] = "只检查"
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("真实目标预检通过", 退出码 == 0 and not 查询读数["isError"]))
        (工作树 / "漂移.py").write_text("配置文件 = 9\n", encoding="utf-8")
        参数表["操作"] = "改"
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("预检后漂移仍严格拒写", 退出码 == 0 and 查询读数["isError"]
                      and "第 ③ 道闸" in 查询读数["content"][0]["text"]))
        def 开账():
            连接 = sqlite3.connect(str(库件))
            连接.row_factory = sqlite3.Row
            return 连接
        真连, 真索引 = 账本.连账本, 修改.同步索引
        账本.连账本 = 开账
        修改.同步索引 = lambda _根: (0, "样本空索引")
        try:
            退出码, 说明 = 修改.派发({"开工ID": "v1-样本", "改动表": [
                {"路径": "重复.py", "功能": 1, "旧内容": "print(1)", "新内容": "print(2)"}]}, 仓根)
            输出表.append(("实际旧文不唯一仍4且0条完成", 退出码 == 4 and "改了 0/1" in 说明))
            退出码, 说明 = 修改.派发({"开工ID": "v1-样本", "改动表": [
                {"路径": "部分.py", "功能": 0, "新内容": "配置文件 = 1"},
                {"路径": "重复.py", "功能": 1, "旧内容": "不存在", "新内容": "配置文件 = 2"}]}, 仓根)
            输出表.append(("实际部分完成仍4且已写如实记账", 退出码 == 4 and "改了 1/2" in 说明
                          and (工作树 / "部分.py").read_text() == "配置文件 = 1\n"))
            退出码, 说明 = 修改.派发({"开工ID": "v1-样本", "改动表": [
                {"路径": "部分.py", "功能": 1, "旧内容": "配置文件 = 1", "新内容": "未登记配置 = 2"}]}, 仓根)
            输出表.append(("实际命名拒绝仍5", 退出码 == 5 and "未登记配置" in 说明))
            语法件.write_text("配置文件 = 0\n", encoding="utf-8")
            连接 = 开账()
            连接.execute("update 认领 set 指纹=? where 路径=?",
                      (修改.文件指纹(str(语法件)), "语法.py"))
            连接.commit()
            连接.close()
            退出码, 说明 = 修改.派发({"开工ID": "v1-样本", "改动表": [
                {"路径": "语法.py", "功能": 1, "旧内容": "配置文件 = 0",
                 "新内容": "  配置文件 = 7"}]}, 仓根)
            输出表.append(("语法闸·真实写·坏缩进终态 ⇒ 退出码3且0字节落盘",
                     退出码 == 3 and "第 ⑦ 道闸" in 说明
                     and 语法件.read_text(encoding="utf-8") == "配置文件 = 0\n"))
            退出码, 说明 = 修改.派发({"开工ID": "v1-样本", "改动表": [
                {"路径": "语法.py", "功能": 1, "旧内容": "配置文件 = 0",
                 "新内容": "配置文件 = \"未闭合"},
                {"路径": "语法.py", "功能": 1, "旧内容": "配置文件 = \"未闭合",
                 "新内容": "配置文件 = 8"}]}, 仓根)
            输出表.append(("语法闸·真实写·中间不合法终态合法 ⇒ 退出码0且落盘",
                     退出码 == 0 and 语法件.read_text(encoding="utf-8") == "配置文件 = 8\n"))
            语法件.write_text("配置文件 = 0\n", encoding="utf-8")
            连接 = 开账()
            连接.execute("update 认领 set 指纹=? where 路径=?",
                      (修改.文件指纹(str(语法件)), "语法.py"))
            连接.commit()
            连接.close()
        finally:
            账本.连账本, 修改.同步索引 = 真连, 真索引
        参数表["操作"] = "只检查"
        参数表["参数"]["改动表"] = [
            {"路径": "新建.py", "操作": "新建", "新内容": "配置文件 = 1"},
            {"路径": "新建.py", "操作": "修改", "旧内容": "不存在", "新内容": "配置文件 = 2"},
            {"路径": "新建.py", "操作": "修改", "旧内容": "配置文件 = 1", "新内容": "配置文件 = 3"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("同件定位失败后后条未判且不猜候选", 退出码 == 0 and "顺序模拟未判" in 说明
                      and "第 3 条 `新建.py` · 顺序内存模拟完成" not in 说明))
        # 第 ⑦ 道闸（语法）· 只检查：只看**每件最终态**。7 条同件，第 7 条引入坏缩进 ⇒ 报语法拒。
        参数表["操作"] = "只检查"
        参数表["参数"]["改动表"] = [
            {"路径": "语法.py", "操作": "修改", "旧内容": "配置文件 = %d" % 号值,
             "新内容": ("  配置文件 = %d" % (号值 + 1)) if 号值 == 6 else ("配置文件 = %d" % (号值 + 1))}
            for 号值 in range(7)]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("语法闸·只检查·第7条坏缩进 ⇒ 报最终态语法拒且零写",
                 退出码 == 0 and "语法拒绝" in 说明 and "语法.py" in 说明
                 and 语法件.read_text(encoding="utf-8") == "配置文件 = 0\n"))
        # 中间不合法、最后修正 ⇒ 最终态合法可过（不逐条 parse，不误拒正常暂态）。
        参数表["参数"]["改动表"] = [
            {"路径": "语法.py", "操作": "修改", "旧内容": "配置文件 = 0",
             "新内容": "配置文件 = \"未闭合"},
            {"路径": "语法.py", "操作": "修改", "旧内容": "配置文件 = \"未闭合",
             "新内容": "配置文件 = 9"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("语法闸·只检查·中间不合法终态合法 ⇒ 无语法拒",
                 退出码 == 0 and "语法拒绝" not in 说明))
        # 删掉的件不 parse：盘上带坏缩进的件被删 ⇒ 终态 None ⇒ 不当语法报（不误拒）。
        参数表["参数"]["改动表"] = [
            {"路径": "删语法.py", "操作": "删除", "旧内容": "  配置文件 = 0\n"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        说明 = 查询读数["content"][0]["text"]
        输出表.append(("语法闸·只检查·删除坏缩进件 ⇒ 不 parse 已删件、无语法拒",
                 退出码 == 0 and "语法拒绝" not in 说明))
        连接 = sqlite3.connect(str(库件))
        连接.execute("drop table 改动")
        连接.commit()
        连接.close()
        参数表["参数"]["改动表"] = [{"路径": "新建.py", "操作": "新建", "新内容": "配置文件 = 1"}]
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("只读预检不依赖改动表且不迁移", 退出码 == 0 and not 查询读数["isError"]))
        连接 = sqlite3.connect(str(库件))
        连接.execute("drop table 认领")
        连接.commit()
        连接.close()
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("缺认领表未判且不补表", 退出码 == 0 and 查询读数["isError"]
                      and "账本未判" in 查询读数["content"][0]["text"]))
        # 缺账本时不得创造目录/文件。
        库件.unlink()
        库件.parent.rmdir()
        参数表["操作"] = "只检查"
        退出码, 查询读数 = 跑命令(仓根, 临时根, 参数表)
        输出表.append(("缺账本未判且不建库", 退出码 == 0 and 查询读数["isError"]
                      and "账本未判" in 查询读数["content"][0]["text"] and not 库件.parent.exists()))
        文件句柄.stdin.close()
        assert 文件句柄.wait(timeout=5) == 0
    return 输出表


def 跑命令(仓根: Path, 临时根: Path, 参数表: dict, 文件句柄) -> tuple:
    """每帧走同一新MCP进程；全树哈希含账本/库/索引，缓存不许刷新写入凭据。"""
    指纹表 = {路径: hashlib.sha256(路径.read_bytes()).hexdigest()
             for 路径 in 临时根.rglob("*") if 路径.is_file()}
    路径表 = {路径 for 路径 in 临时根.rglob("*")}
    请求 = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
          "params": {"name": "v1_edit", "arguments": 参数表}}
    文件句柄.stdin.write(json.dumps(请求, ensure_ascii=False) + "\n")
    文件句柄.stdin.flush()
    assert select.select([文件句柄.stdout], [], [], 5)[0], "MCP帧超时"
    查询读数 = json.loads(文件句柄.stdout.readline())
    assert 路径表 == {路径 for 路径 in 临时根.rglob("*")}, "目录或件集合改变"
    assert 指纹表 == {路径: hashlib.sha256(路径.read_bytes()).hexdigest()
                    for 路径 in 临时根.rglob("*") if 路径.is_file()}, "预检/拒绝发生写入"
    return 0, 查询读数["result"]
