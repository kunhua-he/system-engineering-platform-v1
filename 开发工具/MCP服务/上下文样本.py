# -*- coding: utf-8 -*-
"""上下文工具正反样本：临时源与真实MCP子进程。"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from 开发工具.信息核心 import 上下文读取, 上下文来源
from 开发工具.信息核心.表定义 import 派生库路径
from 开发工具.MCP服务.上下文 import 派发
from 开发工具.MCP服务.合主干有界跑 import 干净环境


def 读盘状态(树根):
    return {str(文件路径.relative_to(树根)): (文件路径.stat().st_mtime_ns, 文件路径.read_bytes())
            for 文件路径 in 树根.rglob("*") if 文件路径.is_file()}


def 建上下文夹具(树根):
    (树根 / "开发工具/信息核心").mkdir(parents=True)
    (树根 / "项目文档").mkdir()
    (树根 / "README.md").write_text("# 宪法\n活源主题\n## 新节\n新增内容\n", encoding="utf-8")
    (树根 / "临时.md").write_text("# 草案\n临时主题正文\n", encoding="utf-8")
    (树根 / 上下文来源.文档账本件).write_text(json.dumps({"件": [{"路径": "README.md", "档": "宪法"}, {"路径": "临时.md", "档": "临时文档"}]}, ensure_ascii=False), encoding="utf-8")
    (树根 / 上下文来源.未完成件).write_text(json.dumps({"行": [[307, "活源主题缺口", "落点", "验证"]]}, ensure_ascii=False), encoding="utf-8")
    with sqlite3.connect(树根 / "开发工具/信息核心/信息核心.db") as 连接:
        连接.execute("create table 条款(文档路径 text,序号 integer,标题 text,正文 text,权威档 text)")
        连接.execute("create table 规则(编号 text,类 text,名 text,内容 text,依据 text)")
        连接.execute("create table 命名登记(名字 text primary key,语义 text,模式 text,来源 text,状态 text,出现次数 integer,创建时间 text)")
        连接.execute("insert into 条款 values(?,?,?,?,?)", ("README.md", 0, "宪法", "旧镜像主题", "宪法"))
        连接.execute("insert into 条款 values(?,?,?,?,?)", ("临时.md", 0, "草案", "临时主题正文", "临时文档"))
        连接.executemany("insert into 条款 values(?,?,?,?,?)", [("项目文档/设计哲学.md", 序号值, "哲学", "主题" * 2000 if 序号值 == 4 else "核心唯一物", "设计原则") for 序号值 in range(12)])
        连接.execute("insert into 规则 values(?,?,?,?,?)", ("规则-1", "命名口径", "规则主题", "中文命名", "规范"))
        连接.execute("insert into 命名登记 values(?,?,?,?,?,?,?)", ("规则主题", "样本命名", "对象+说明", "新定义", "合格", 0, "样本"))
    # 派生库：`文档索引` 是 `条款` 的 (文档路径 · 序号 · 标题) 投影 —— 与上面那几条 `条款` 逐行对齐。
    with sqlite3.connect(派生库路径(树根)) as 派生连接:
        派生连接.execute("create table 文档索引(文档路径 text, 序号 integer, 标题 text)")
        派生连接.executemany(
            "insert into 文档索引 values(?,?,?)",
            [("README.md", 0, "宪法"), ("临时.md", 0, "草案")]
            + [("项目文档/设计哲学.md", 序号值, "哲学") for 序号值 in range(12)])


def 上下文样本(仓根, 工具表=None):
    输出缓冲 = []
    def 记样本(名称, 条件值):
        输出缓冲.append((名称, bool(条件值)))
    with tempfile.TemporaryDirectory(prefix="v1上下文-") as 临时目录:
        树根 = Path(临时目录) / "夹具"
        建上下文夹具(树根)
        def 读夹具原文(参数表):
            return 上下文读取.读取上下文(树根, 参数表, "样本", "样本HEAD")
        def 读夹具(参数表):
            return json.loads(读夹具原文(参数表))
        def 失败样本(参数表, 错误种类):
            写前状态 = 读盘状态(树根)
            with patch("开发工具.MCP服务.上下文.跑命令", return_value=(0, "样本")):
                退出码, 输出文本 = 派发(参数表, 树根)
            记样本(错误种类 + "零写", 退出码 != 0 and json.loads(输出文本)["错误"]["种类"] == 错误种类 and 写前状态 == 读盘状态(树根))
        写前状态 = 读盘状态(树根)
        读数 = 读夹具({})
        记样本("空主题有界并含状态", len(读夹具原文({}).encode()) < 8192 and any(条款行["类型"] == "未完成" for 条款行 in 读数["条目"]))
        读数 = 读夹具({"主题": "活源主题", "包含": ["条款"]})
        记样本("活源匹配镜像不重复且冲突可见", len(读数["条目"]) == 1 and 读数["条目"][0]["冲突"] and 读数["条目"][0]["来源"]["文件"] == "README.md")
        读数 = 读夹具({"包含": ["条款"], "文档路径序号表": [{"文档路径": "README.md", "序号": 1}]})
        记样本("活源新节不依赖镜像", len(读数["条目"]) == 1 and "镜像缺节" in 读数["条目"][0]["冲突"][0])
        记样本("正向调用零写", 写前状态 == 读盘状态(树根))
        工作树 = Path(临时目录) / "异树"
        建上下文夹具(工作树)
        (工作树 / "README.md").write_text("# 宪法\n异树主题\n", encoding="utf-8")
        查询结果 = json.loads(上下文读取.读取上下文(工作树, {"主题": "活源主题", "包含": ["条款"]}, "异树", "异树HEAD"))
        记样本("不同树不串源", not 查询结果["条目"] and 查询结果["树绝对路径"] == str(工作树.resolve()))
        失败样本({"包含": ["索引"]}, "missing")
        from 代码地图.落点 import 库目录名, 库文件名
        索引路径 = 树根 / 库目录名 / 库文件名
        索引路径.parent.mkdir()
        索引路径.write_bytes(b"corrupt")
        失败样本({"包含": ["索引"]}, "corrupt")
        索引路径.unlink()
        with sqlite3.connect(索引路径) as 连接:
            连接.execute("create table nodes(编号 integer)")
            连接.execute("create table edges(编号 integer)")
            连接.execute("create table files(编号 integer)")
            连接.execute("create table project_metadata(key text,value text)")
        文件路径 = 树根 / "样例.py"
        文件路径.write_text("样例名称 = 1\n", encoding="utf-8")
        os.utime(索引路径, (1, 1))
        写前状态 = 读盘状态(树根)
        读数 = 读夹具({"包含": ["索引"]})
        记样本("陈旧索引可见零写", 读数["条目"][0]["新鲜度"] == "陈旧" and 写前状态 == 读盘状态(树根))
        for 参数表 in ({"条数": True}, {"条数": 51}, {"字节预算": 16385}, {"包含": ["SQL"]}, {"开工ID": "../秘密"}, {"文档路径序号表": [{"文档路径": "../秘密.md", "序号": 0}]}, {"操作": "不存在"}, {"操作": "条款检索"}, {"操作": "取整件", "文档路径": "README.md", "序号段": [2, 1]}, {"操作": "名字全文"}, {"不存在的字段": 1}, {"条数": "20"}):
            失败样本(参数表, "参数错误")
        from 开发工具.信息核心.上下文读取 import 数值约束, 数值参, 约束说明, 数值范围文本
        from 开发工具.MCP服务 import 操作_上下文
        数值参例 = {名称: 数值约束[名称][2] for 名称 in 数值参}
        记样本("默认与显式缺省逐字节同", 读夹具原文({}) == 读夹具原文(dict(数值参例)))
        for 名称 in 数值参:
            下限值, 上限值, 默认值 = 数值约束[名称]
            范围文本 = 数值范围文本(名称)
            for 边界参表 in ({名称: 下限值}, {名称: 上限值}):
                try:
                    上下文读取.读取上下文(树根, 边界参表, "样本", "样本HEAD")
                    记样本("边界合法" + 名称 + str(边界参表[名称]), True)
                except 上下文来源.上下文失败 as 失败原因:
                    记样本("边界合法" + 名称 + str(边界参表[名称]), 失败原因.错误种类 != "参数错误")
            for 坏参表 in ({名称: 下限值 - 1}, {名称: 上限值 + 1}):
                写前状态 = 读盘状态(树根)
                with patch("开发工具.MCP服务.上下文.跑命令", return_value=(0, "样本")):
                    退出码, 输出文本 = 派发(坏参表, 树根)
                读数 = json.loads(输出文本)
                记样本("越界回执给上下限与缺省" + 名称 + str(坏参表[名称]),
                      退出码 != 0 and 读数["错误"]["说明"] == "超出范围：" + 约束说明(名称)
                      and 范围文本 in 读数["错误"]["说明"] and 写前状态 == 读盘状态(树根))
        操作表读数 = 操作_上下文.操作表
        说明单源 = all(("合法范围" in 样本条目["说明"] and "开工ID" in 样本条目["说明"]
                     and all(约束说明(名称) in 样本条目["说明"] for 名称 in 样本条目["可选"] if 名称 in 数值参))
                   for 样本条目 in 操作表读数.values())
        记样本("操作说明复用数值单源", 说明单源)
        失败样本({"包含": ["条款"], "文档路径序号表": [{"文档路径": "项目文档/缺失.md", "序号": 0}]}, "missing")
        失败样本({"操作": "取整件", "文档路径": "项目文档/缺失.md"}, "missing")
        失败样本({"操作": "冻结落点", "路径": "不存在的落点.md"}, "missing")
        参数表 = {"包含": ["条款"], "条数": 2, "字节预算": 2048}
        读数 = 读夹具(参数表)
        游标值 = 读数["游标"]
        查询结果 = 读夹具(dict(参数表, 游标=游标值))
        记样本("分页无重复", 读数["条目"][0]["来源"] != 查询结果["条目"][0]["来源"])
        try:
            读夹具(dict(参数表, 游标="不是游标"))
            记样本("非法游标给照抄提示", False)
        except 上下文来源.上下文失败 as 失败原因:
            记样本("非法游标给照抄提示", 失败原因.错误种类 == "参数错误" and "重取第一页" in str(失败原因))
        try:
            读夹具(dict(参数表, 主题="活源主题", 游标=游标值))
            记样本("游标绑查询与来源版本", False)
        except 上下文来源.上下文失败 as 失败原因:
            记样本("游标绑查询与来源版本", 失败原因.错误种类 == "游标过期")
        for 预算值 in (1024, 1536, 2048, 8192, 16384):
            try:
                输出文本 = 上下文读取.读取上下文(树根, {"字节预算": 预算值, "条数": 50}, "样本", "样本HEAD")
                记样本("UTF8预算" + str(预算值), len(输出文本.encode()) <= 预算值)
            except 上下文来源.上下文失败 as 失败原因:
                记样本("UTF8预算" + str(预算值), 失败原因.错误种类 == "预算不足")
        读数 = 读夹具({"包含": ["条款"], "字节预算": 2048, "文档路径序号表": [{"文档路径": "项目文档/设计哲学.md", "序号": 4}]})
        记样本("长条完整来源投影", 读数.get("投影") == 1 and "状态" in 读数["条目"][0]["内容"])
        记样本("信封精简与提交绑定", "读取时刻" not in 读数 and "输出字节" not in 读数 and "语义冲突能力" not in 读数 and "来源版本" in 读数 and 读数.get("提交") == "样本HEAD")
        检索读数 = 读夹具({"操作": "条款检索", "检索": "活源主题", "包含": ["条款"]})
        记样本("条款检索给片段", len(检索读数["条目"]) == 1 and "活源主题" in 检索读数["条目"][0]["内容"].get("片段", ""))
        文档读数 = 读夹具({"操作": "文档序号", "文档路径": "README.md"})
        记样本("文档序号存在性", 文档读数["条目"][0]["内容"]["在库"] is True and 文档读数["条目"][0]["内容"]["节数"] >= 1)
        缺档读数 = 读夹具({"操作": "文档序号", "文档路径": "项目文档/缺失.md"})
        记样本("文档序号报不在", 缺档读数["条目"][0]["内容"]["在库"] is False)
        索引读数 = 读夹具({"操作": "文档索引", "文档路径": "README"})
        记样本("文档索引列序号与标题",
              len(索引读数["条目"]) == 1 and 索引读数["条目"][0]["内容"]["序号"] == 0
             and 索引读数["条目"][0]["内容"]["标题"] == "宪法")
        索引段读数 = 读夹具({"操作": "文档索引", "文档路径": "项目文档/设计哲学.md"})
        记样本("文档索引按路径列多节",
              len(索引段读数["条目"]) == 12
             and 索引段读数["条目"][0]["内容"]["序号"] == 0
             and 索引段读数["条目"][11]["内容"]["序号"] == 11)
        索引空读数 = 读夹具({"操作": "文档索引", "文档路径": "项目文档/不存在"})
        记样本("文档索引无匹配空且明确",
              len(索引空读数["条目"]) == 1 and 索引空读数["条目"][0]["内容"].get("匹配数") == 0)
        派生库件 = 派生库路径(树根)
        派生原件 = 派生库件.read_bytes()
        派生库件.unlink()
        with patch("开发工具.MCP服务.上下文.跑命令", return_value=(0, "样本")):
            退出码, 输出文本 = 派发({"操作": "文档索引", "文档路径": "README"}, 树根)
        错读数 = json.loads(输出文本)["错误"]
        记样本("文档索引派生库不在报missing且提示建库",
             退出码 != 0 and 错读数["种类"] == "missing" and "建库" in 错读数["说明"])
        派生库件.write_bytes(派生原件)
        with sqlite3.connect(派生库件) as 连接:
            连接.execute("insert into 文档索引 values(?,?,?)", ("项目文档/幽灵.md", 0, "幽灵"))
        with patch("开发工具.MCP服务.上下文.跑命令", return_value=(0, "样本")):
            退出码, 输出文本 = 派发({"操作": "文档索引", "文档路径": "README"}, 树根)
        错读数 = json.loads(输出文本)["错误"]
        记样本("文档索引派生表过期报不一致且提示建库",
             退出码 != 0 and 错读数["种类"] == "不一致" and "建库" in 错读数["说明"])
        派生库件.write_bytes(派生原件)
        整件读数 = 读夹具({"操作": "取整件", "文档路径": "项目文档/设计哲学.md", "序号段": [0, 1]})
        记样本("取整件序号段", len(整件读数["条目"]) == 2 and "正文" in 整件读数["条目"][0]["内容"])
        名字读数 = 读夹具({"操作": "名字全文", "名字": "规则主题"})
        记样本("名字精确取全文", 名字读数["条目"][0]["内容"]["名字"] == "规则主题")
        临时读数 = 读夹具({"主题": "临时主题", "包含": ["条款"]})
        记样本("临时档降权提示", "提示" in 临时读数 and any(样本条目["权威档"] == "临时文档" for 样本条目 in 临时读数["条目"]))
        过滤读数 = 读夹具({"包含": ["条款"], "权威档": "设计原则"})
        记样本("权威档过滤", bool(过滤读数["条目"]) and all(样本条目["权威档"] == "设计原则" for 样本条目 in 过滤读数["条目"]))
        提交读数 = 读夹具({})
        记样本("历史证据绑提交", all(样本条目.get("提交") == "样本HEAD" for 样本条目 in 提交读数["条目"] if 样本条目["类型"] == "未完成"))
        账本件 = 树根 / "开工账本.db"
        连接 = sqlite3.connect(str(账本件))
        连接.execute("create table 开工(开工号 text, 工作内容 text, 工作树 text)")
        连接.executemany("insert into 开工 values(?,?,?)",
                     [("v1-100540", "改读配置", "树"), ("v1-100541", "改写日志", "树")])
        连接.commit()
        连接.close()
        def 读开工夹具(主题值):
            return json.loads(上下文读取.读取上下文(树根, {"包含": ["开工"], "主题": 主题值}, "样本", "样本HEAD", 账本件))
        读数 = 读开工夹具("540")
        记样本("取开工按开工号尾号命中", len(读数["条目"]) == 1 and 读数["条目"][0]["内容"]["开工号"] == "v1-100540")
        读数 = 读开工夹具("v1-1005")
        记样本("取开工按开工号前缀命中", {样本条目["内容"]["开工号"] for 样本条目 in 读数["条目"]} == {"v1-100540", "v1-100541"})
        读数 = 读开工夹具("改写日志")
        记样本("取开工按工作内容子串命中（口径不变）", len(读数["条目"]) == 1 and 读数["条目"][0]["内容"]["开工号"] == "v1-100541")
        记样本("取开工反向：不存在的开工号 ⇒ 0 条", not 读开工夹具("999")["条目"])
        try:
            读数 = 读开工夹具(307)
            记样本("取开工：主题给整数（台账号惯用）也收", isinstance(读数, dict))
        except 上下文来源.上下文失败:
            记样本("取开工：主题给整数（台账号惯用）也收", False)
        冻结读数 = 读夹具({"操作": "冻结落点"})
        记样本("冻结落点可读", any(样本条目["类型"] == "冻结件" for 样本条目 in 冻结读数["条目"]) and any(样本条目["类型"] == "落点" for 样本条目 in 冻结读数["条目"]))
        文件路径 = 树根 / "README.md"
        文件路径.write_text("# 宪法\n已变\n", encoding="utf-8")
        try:
            读夹具(dict(参数表, 游标=游标值))
            记样本("版本变化拒续页", False)
        except 上下文来源.上下文失败 as 失败原因:
            记样本("版本变化拒续页", 失败原因.错误种类 == "游标过期")
        真读取 = 上下文读取.读上下文条目
        def 变更来源(*参数表):
            yield from 真读取(*参数表)
            文件路径.write_text("# 并发变化\n", encoding="utf-8")
        with patch.object(上下文读取, "读上下文条目", 变更来源):
            try:
                读夹具({})
                记样本("跨源变化拒不一致", False)
            except 上下文来源.上下文失败 as 失败原因:
                记样本("跨源变化拒不一致", 失败原因.错误种类 == "不一致")
        库件 = 树根 / "开发工具/信息核心/信息核心.db"
        写前内容 = 库件.read_bytes()
        库件.unlink()
        失败样本({}, "missing")
        库件.write_bytes(b"corrupt")
        失败样本({}, "corrupt")
        库件.write_bytes(写前内容)
        (树根 / 上下文来源.未完成件).write_text("{", encoding="utf-8")
        失败样本({}, "corrupt")
        (树根 / 上下文来源.未完成件).write_text('{"行":[]}', encoding="utf-8")
        库件.with_name(库件.name + "-wal").write_bytes("活动事务".encode())
        失败样本({}, "不一致")
        库件.with_name(库件.name + "-wal").unlink()
        with sqlite3.connect(库件) as 连接:
            连接.execute("pragma journal_mode=wal")
            连接.execute("pragma wal_autocheckpoint=0")
            连接.execute("insert into 规则 values(?,?,?,?,?)", ("规则-WAL", "命名口径", "未检查点", "活动WAL内容", "样本"))
            连接.commit()
            写前状态 = 读盘状态(树根)
            失败样本({}, "不一致")
            记样本("真实WAL未检查点不报当前且零写", 库件.with_name(库件.name + "-wal").stat().st_size > 0 and 写前状态 == 读盘状态(树根))
    回执 = subprocess.run(["git", "branch", "--show-current"], cwd=仓根, capture_output=True, text=True, env=干净环境(), timeout=5)
    分支值 = 回执.stdout.strip()
    开工号 = 分支值.split("/")[-1] if 分支值.startswith("腿/v1-") else "v1-000000"
    命令表 = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "v1_context", "arguments": {"操作": "取条款"}}},
             {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "v1_context", "arguments": {"开工ID": 开工号, "操作": "取条款"}}}]
    回执 = subprocess.run([sys.executable, "-B", "开发工具/MCP服务.py"], cwd=仓根, input="".join(json.dumps(命令行参数, ensure_ascii=False) + "\n" for 命令行参数 in 命令表), capture_output=True, text=True, timeout=5)
    响应表 = [json.loads(源码行) for 源码行 in 回执.stdout.splitlines() if 源码行.startswith("{")]
    记样本("真实MCP发现工具", 回执.returncode == 0 and any(工具项["name"] == "v1_context" for 工具项 in 响应表[0]["result"]["tools"]))
    信封 = json.loads(响应表[1]["result"]["content"][0]["text"])
    记样本("真实MCP数据与预算", not 响应表[1]["result"]["isError"] and 信封["结果"]["条目"]
          and len(信封["说明"].encode()) <= 8192 and "条目" not in 信封["说明"])
    信封 = json.loads(响应表[2]["result"]["content"][0]["text"])
    读数 = 信封["结果"]
    记样本("正式开工树解析", (not 响应表[2]["result"]["isError"] and 读数["树绝对路径"].endswith(开工号)) if 开工号 != "v1-000000" else (响应表[2]["result"]["isError"] and 读数["错误"]["种类"] == "missing"))
    # —— 同态镜像复核：同一调用经 HTTP 长驻路径（真实传输处理器）与 stdio 独立进程 ⇒ 信封同态 ——
    from 开发工具.MCP服务 import http传输样本
    from 开发工具.MCP服务.工具 import 工具表 as 登记工具表
    服务对象, 监听端口 = http传输样本._起环回(仓根, 登记工具表)
    try:
        标准头 = dict(http传输样本.标准头)
        # 无状态（548）：服务端不再回 Mcp-Session-Id ⇒ 不再把它塞进标准头（否则发出 None 头值）。
        http传输样本._调用(监听端口, "POST", http传输样本._报文(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "同态镜像", "version": "0"}}}), 标准头)
        镜像信封 = json.loads(json.loads(http传输样本._调用(监听端口, "POST", http传输样本._报文(
            命令表[1]), 标准头)[3])["result"]["content"][0]["text"])
        对照信封 = json.loads(响应表[1]["result"]["content"][0]["text"])
        记样本("HTTP与stdio长驻同态镜像（对象结果·说明短元信息·不重复正文·两路一致）",
             镜像信封["成功"] and isinstance(镜像信封["结果"], dict)
             and bool(镜像信封["结果"].get("条目")) and "条目" not in 镜像信封["说明"]
             and 镜像信封["说明"] == 对照信封["说明"]
             and type(镜像信封["结果"]) is type(对照信封["结果"]))
        文本信封 = json.loads(json.loads(http传输样本._调用(监听端口, "POST", http传输样本._报文(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "v1_shell", "arguments": {"操作": "执行",
                                                          "参数": {"命令": "echo 同态镜像固定词"}}}}),
            标准头)[3])["result"]["content"][0]["text"])
        记样本("HTTP长驻纯文本（结果 None·说明保全文）",
             文本信封["结果"] is None and "同态镜像固定词" in 文本信封["说明"])
        错误信封 = json.loads(json.loads(http传输样本._调用(监听端口, "POST", http传输样本._报文(
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "v1_context", "arguments": {"操作": "取条款",
                                                             "参数": {"游标": "坏游标原文xyz"}}}}),
            标准头)[3])["result"]["content"][0]["text"])
        记样本("HTTP长驻错误（退出码非零·说明保原文·游标原文不丢）",
             not 错误信封["成功"] and "游标无法解码" in 错误信封["说明"])
    finally:
        服务对象.shutdown()
        服务对象.server_close()
    return 输出缓冲
