#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息核心 · 查看 —— 一个只读页面端口（默认 43130）。

华哥 2026-09-28：「你给所有权威的定义，单独开一个端口，然后放 html 页面。」·「这个端口，
主页是整个内核的咬合流程图。只需要实时流程图，内核延展出来，他连接什么，和什么连在一起。
然后每一个节点的细节。全部需要梳理出来。」

**它是开发工具，不是底座的一部分** —— 不进底座代码树 ⇒ 不触判据 ⑪（对外监听恰好 1 处）。
**页面是实时的**：每次请求都从库里现查（库本身是 `建库.py` 从仓内源现建的）⇒ 不会读到旧快照。

用法：
    python3 开发工具/信息核心/查看.py            # 起页面（Ctrl-C 退）
    python3 开发工具/信息核心/查看.py --端口 8080
"""
import html
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(仓根 / "开发工具"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import 表定义  # noqa: E402
import 验证  # noqa: E402

页面样式 = """
body{font:13px/1.7 -apple-system,"Songti SC",serif;margin:0;color:#000;background:#fff}
header{background:#f0f0f0;border-bottom:1px solid #a0a0a0;padding:8px 12px}
header b{margin-right:14px}
header a{margin-right:12px;color:#000080;text-decoration:none}
header a:hover{text-decoration:underline}
main{padding:12px}
h2{font-size:15px;margin:14px 0 6px;border-left:4px solid #000080;padding-left:6px}
table{border-collapse:collapse;width:100%;font-size:12px;margin:4px 0 12px}
th,td{border:1px solid #e3e3e3;padding:3px 6px;text-align:left;vertical-align:top}
th{background:#ececec;position:sticky;top:0}
.红{color:#c00;font-weight:bold}
.好{color:#060}
.灰{color:#888}
层{display:inline-block;vertical-align:top;margin:6px;padding:0 6px 6px;border:1px solid #a0a0a0;background:#fafafa;min-width:170px}
层 h3{font-size:13px;margin:6px -6px;padding:3px 6px;background:#e6e6e6}
点{display:block;border:1px solid #ccc;background:#fff;margin:4px 0;padding:3px 6px}
点 a{color:#000080;text-decoration:none}
边{display:block;font-size:11px;color:#555;margin-left:6px}
输入{width:100%;font:12px monospace;padding:6px}
"""

导航栏 = """<header><b>信息核心</b>
<a href="/">内核咬合图</a><a href="/命名">命名</a><a href="/规则">规则</a>
<a href="/条款">条款</a><a href="/文档">文档账本</a><a href="/未完成">未完成</a>
<a href="/接口">接口</a><a href="/查询">查询</a></header>"""


# ── 小工具 ─────────────────────────────────────────────────────────
def 页面壳(标题: str, 正文: str) -> bytes:
    文档 = (f"<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(标题)} · 信息核心</title><style>{页面样式}</style></head>"
            f"<body>{导航栏}<main>{正文}</main></body></html>")
    return 文档.encode("utf-8")


def 表格(列名: tuple, 数据行: list, 红列: set = (), 原样: set = ()) -> str:
    """`原样` 列不转义（该列的值已是 HTML，如一个链接）。"""
    表头 = "".join(f"<th>{html.escape(str(一列))}</th>" for 一列 in 列名)
    表体 = ""
    for 一行 in 数据行:
        单元格 = ""
        for 列号, 单元值 in enumerate(一行):
            类名 = ' class="红"' if 列号 in 红列 else ""
            文本值 = str(单元值 if 单元值 is not None else '')
            单元格 += f"<td{类名}>{文本值 if 列号 in 原样 else html.escape(文本值)}</td>"
        表体 += f"<tr>{单元格}</tr>"
    return f"<table><tr>{表头}</tr>{表体}</table>"


# ── 页 ─────────────────────────────────────────────────────────────
def 库现状(连接) -> str:
    """库现状：每张表的行数 + 命名覆盖读数 —— 让内核咬合图页**自身**回答「库弄好了没」。"""
    表名表 = [表名 for (表名,) in 连接.execute(
        "select name from sqlite_master where type='table' and name<>'元' order by name")]
    行数表 = [(表名, 连接.execute(f"select count(*) from {表名}").fetchone()[0])
              for 表名 in 表名表]
    结果 = 验证.查命名(连接)
    未登记处数 = sum(结果["未登记处数"].values())
    return ("<h2>库现状</h2><p>表 %d 张 —— %s</p>"
            % (len(行数表),
               " · ".join(f"{html.escape(表名)} <b>{行数}</b>" for 表名, 行数 in 行数表))
            + ("<p>命名覆盖：三面 %d 处（%s）—— <b>已登记 %d 处</b> · "
               "<b class=\"红\">未登记 %d 处 / %d 个名</b>"
               "（<a href=\"/命名\">看清单与族批次</a>）</p>"
               % (结果["总数"],
                  " · ".join(f"{面名} {处数}" for 面名, 处数 in 结果["分档"].items()),
                  结果["总数"] - 未登记处数, 未登记处数, len(结果["未定义"]))))


def 内核咬合图页(连接) -> bytes:
    节点表 = list(连接.execute("select 名,层,职责 from 节点 order by 层,名"))
    边表 = list(连接.execute("select 起,止,条数 from 连接 order by 条数 desc"))
    入度, 出度 = {}, {}
    for 起点, 终点, 条数 in 边表:
        出度[起点] = 出度.get(起点, 0) + 条数
        入度[终点] = 入度.get(终点, 0) + 条数
    按层 = {}
    for 节点名, 层名, 职责 in 节点表:
        按层.setdefault(层名, []).append((节点名, 职责))
    图层 = ""
    for 层名 in sorted(按层):
        层块 = f"<层><h3>{html.escape(层名)}（{len(按层[层名])}）</h3>"
        for 节点名, 职责 in 按层[层名]:
            层块 += (f"<点><a href=\"/节点?名={html.escape(节点名)}\">{html.escape(节点名)}</a>"
                    f"<边>出 {出度.get(节点名, 0)} · 入 {入度.get(节点名, 0)}</边></点>")
        图层 += 层块 + "</层>"
    边行 = [(起点, 终点, 条数) for 起点, 终点, 条数 in 边表[:60]]
    正文 = (库现状(连接)
            + f"<h2>内核咬合图（节点 {len(节点表)} · 连接 {len(边表)}）</h2>"
            f"<div>{图层}</div>"
            f"<h2>连接（按 import 实际条数降序，前 60）</h2>"
            + 表格(("起", "止", "条数"), 边行))
    return 页面壳("内核咬合图", 正文)


def 节点页(连接, 节点名: str) -> bytes:
    数据行 = 连接.execute("select 名,层,职责 from 节点 where 名=?", (节点名,)).fetchone()
    if not 数据行:
        return 页面壳("找不到节点", f"<p class=\"红\">库里没有节点：{html.escape(节点名)}</p>")
    出边 = list(连接.execute("select 止,条数 from 连接 where 起=? order by 条数 desc", (节点名,)))
    入边 = list(连接.execute("select 起,条数 from 连接 where 止=? order by 条数 desc", (节点名,)))
    文件表 = [件名 for (件名,) in 连接.execute(
        "select distinct 文件 from 代码名 where 文件 like ? limit 40", (节点名 + "/%",))]
    正文 = (f"<h2>{html.escape(节点名)}</h2>"
            f"<p>层：<b>{html.escape(str(数据行[1]))}</b>　职责：{html.escape(数据行[2] or '（未登记）')}</p>"
            f"<h2>它连出去（{len(出边)}）</h2>" + 表格(("止", "条数"), 出边)
            + f"<h2>连到它（{len(入边)}）</h2>" + 表格(("起", "条数"), 入边)
            + f"<h2>它的文件（{len(文件表)}）</h2>" + 表格(("文件",), [(件名,) for 件名 in 文件表]))
    return 页面壳(节点名, 正文)


# 出处行的缓存：一个件读一次（判语义要看那个名住在什么上下文里）。
_行缓存: dict = {}


def 取行(根目录, 文件: str, 行号: int) -> str:
    """从盘上读那一行（带缓存）。读不到 ⇒ 空串。"""
    if 文件 not in _行缓存:
        try:
            _行缓存[文件] = (根目录 / 文件).read_text(
                encoding="utf-8", errors="replace").splitlines()
        except OSError:
            _行缓存[文件] = []
    行表 = _行缓存[文件]
    return 行表[行号 - 1].strip()[:110] if 0 < 行号 <= len(行表) else ""


def 所在范围(限定名: str) -> str:
    """限定名去掉末尾那个名 ⇒ 「它住在哪个模块 / 类型里」（判语义靠这个上下文）。"""
    for 分隔 in ("::", "."):
        if 分隔 in 限定名:
            return 限定名.rsplit(分隔, 1)[0] or "（顶层）"
    return "（顶层）"


def 命名页(连接) -> bytes:
    结果 = 验证.查命名(连接)
    定义行 = list(连接.execute("select 语义,唯一名,现状 from 命名定义 order by 语义"))
    例外行 = list(连接.execute("select 名 from 命名例外 order by 名"))
    例外 = {一行[0] for 一行 in 例外行}
    族规则 = [(族名, 判据式, 定义) for _次序, 族名, 判据式, 定义 in
            连接.execute("select 次序,族名,判据式,定义 from 命名族 order by 次序")]
    词性规则 = [(词性, 说明, 判据式) for _次序, 词性, 说明, 判据式 in
            连接.execute("select 次序,词性,说明,判据式 from 命名词性 order by 次序")]
    未定义表 = 结果["未定义"]
    名到记录 = 结果["归"]
    线索行 = []
    for 面名, 名称, 件数, 处数, 样例 in 未定义表[:400]:
        # 形参面与局部面**索引看不见** ⇒ 名到记录里没有它们，种类只能标成「索引看不见这一面」。
        位表 = 名到记录.get(名称, {}).get("位") or []
        种类 = 位表[0][0] if 位表 else "（索引看不见这一面）"
        文件, _, 行号 = 样例.rpartition(":")
        线索行.append((名称, 件数, 处数, 面名, 种类, 样例, 取行(仓根, 文件, int(行号 or 0))))
    泛名行 = 验证.泛名候选(名到记录, 例外)
    候选 = 验证.同义候选(名到记录, 例外)
    族结果 = 验证.归族(名到记录, 族规则, 例外)
    族结果["族数"] = len(族结果["各族"])
    正文 = (f"<h2>命名：三面 {结果['总数']} 处（{html.escape(str(结果['分档']))}）</h2>"
            f"<p>规则（**穷举口径**，华哥 2026-09-28）：出现即须登记 —— 在库 `命名定义` 里 · "
            f"或属库 `命名例外`（语言强加）。<b class=\"红\">★ 2026-09-29：形状模式不再算定义</b>"
            f"（华哥：「之前的老规则，全部移除掉」）—— 它原是「形状对就算有定义」，把 1012 个名静默放行了。<br>"
            f"<span class=\"灰\">三面 = 定义面（代码地图索引）+ 形参面 + 局部绑定面 —— 后两面索引看不见，"
            f"由 `开发工具/信息核心/命名穷举.py` 现扫（与判据 ㊷ 同一份）。"
            f"**名可复用**：同一个名在别处再出现不是新增债，债按**名**记、不按处数记。</span><br>"
            f"<b class=\"红\">未登记 {len(未定义表)} 个名</b>（其中跨件 {len(结果['跨件未定义'])} 个）。<br>"
            f"归类看**语义**（华哥：「按照语义去命名……是否有前缀，这个关系不大」）—— "
            f"所以下面给的是「种类 · 住在哪 · 出处一行」，而不是按字面前缀分族。</p>"
            + f"<h2>真泛名候选：无主且泛指（该加限定词，共 {len(泛名行)} 个）</h2>"
            f"<p class=\"灰\">判「泛」的关键不是名短不短，而是**有没有主人**："
            f"<code>号类::类型</code> 短，但主人把语义钉死了 ⇒ 精准；"
            f"<code>渲染</code> 短且无主（顶层函数）⇒ 泛指，得写成「渲染<什么>」。"
            f"只在测试/案例件里出现的也不算 —— 那是测试名（本来就是一整句）。<br>"
            f"<b class=\"红\">★ 2026-09-28 补</b>：被「命名模式」覆盖而漏在名册外的泛指名（<code>解析</code> · "
            f"<code>用法</code> · <code>用法说明</code> · <code>用法行</code> · <code>_本</code> · "
            f"<code>标识串</code> · <code>装支持库</code>）已补进名册 —— 模式过 ≠ 名清晰。</p>"
            + 表格(("种类", "名", "件数", "细化数", "细化它的（例）"), 泛名行, 红列={1})
            + f"<h2>命名族（类型）—— 相近的名归成族，一族共用一句定义（共 {族结果['族数']} 族 · 其中专名 {len(族结果['未归'])} 个）</h2>"
            f"<p class=\"灰\">族 = **类型**：同一个族的名共用一个定义，**跨包可复用**（同一个语义在不同包里用同名）。"
            f"归属取**第一个**命中的族（次序从专到泛，规则表在库 `命名族` 表）。"
            f"末三档不走正则：<b>语言强加例外</b>（按成员判）· <b>测试用例名</b>（只在测试/案例件里出现）· "
            f"<b>专名</b>（只此一处、归不进任何族 —— 没有族，它本身就是它的类型）。</p>"
            f"<p class=\"灰\"><b>定名两条根</b>（华哥 2026-09-28）—— ① <b>名要到「明确场景」</b>："
            f"只说动作不说对象就是泛指（<code>解析</code> 解析什么？<code>打印</code> 是结果输出还是印刷？）"
            f"⇒ 必带宾语或限定词。<b class=\"红\">模式定义 ≠ 名清晰</b>：<code>^(转|解|拆|剥|译).+</code> "
            f"让 <code>解析</code> 从没进过「未定义」，它仍是泛指 ⇒ 真泛名按<b>有没有主人</b>判，不看模式过没过。<br>"
            f"② <b>按「返回什么 / 承载什么」定名</b>，不按字面猜 —— 读代码看它 <code>return</code> 什么、装的是什么；"
            f"同一语义在不同包里<b>复用同名</b>（<code>解析运行数据根</code> 在工具侧与内核侧各一份实现，共用一个名）。"
            f"③ 命名规范不清晰处，华哥<b>授权重构</b>（全量或部分）。</p>"
            + "<h2>词性 —— 分类根上就是小学语文那套（动词 / 名词 / 判断 / 量）</h2>"
            + "<p class=\"灰\">判一个名对不对，先问它<b>在句子里当什么</b>："
            "动词名（执行动作）<b class=\"红\">必带宾语</b>（<code>解析协议值</code> 成句，光杆 <code>解析</code> 是语法残缺）；"
            "名词名（承载物）<b class=\"红\">必到具体物</b>（<code>协议值</code> 不是 <code>值</code>）。"
            "族 → 词性取<b>第一个</b>命中（规则表在库 <code>命名词性</code> 表）。</p>"
            + 表格(("词性", "判据", "族数", "名数"), 验证.词性汇总(族结果["各族"], 词性规则))
            + 表格(("族（类型）", "这族的名是什么意思", "名数", "例"), 族结果["各族"])
            + f"<h2>同义候选：一个意思两个名（要「统一」的就是这些，共 {len(候选)} 组）</h2>"
            + 表格(("种类", "名 A", "名 B（含 A）"), 候选, 红列={1, 2})
            + "<h2>未登记的名 —— 按语义线索看（面 · 种类 · 出处一行）</h2>"
            + 表格(("名", "件数", "处数", "面", "种类", "出处", "那一行代码"), 线索行, 红列={0})
            + f"<h2>命名定义（语义 → 唯一名，{len(定义行)} 行）</h2>"
            + 表格(("语义", "唯一名", "现状"), 定义行)
            + f"<h2>命名例外（语言 / 协议 / 工具强加，不在命名管辖内，{len(例外行)} 个）</h2>"
            + 表格(("名",), 例外行))
    return 页面壳("命名", 正文)


def 规则页(连接) -> bytes:
    数据行 = list(连接.execute("select 类,名,内容,依据 from 规则 order by 类,编号"))
    按类 = {}
    for 类别, 规则名, 内容, 依据 in 数据行:
        按类.setdefault(类别, []).append((规则名, 内容, 依据))
    正文 = f"<h2>规则（{len(数据行)} 条，{len(按类)} 类）</h2>"
    for 类别 in sorted(按类):
        正文 += (f"<h2>{html.escape(类别)}（{len(按类[类别])}）</h2>"
                 + 表格(("名", "内容", "依据"), 按类[类别]))
    return 页面壳("规则", 正文)


def 文档页(连接) -> bytes:
    数据行 = list(连接.execute("select 路径,权威档,表达什么 from 文档 order by 权威档,路径"))
    红列集 = {1} if any(一行[1] == "（未定义）" for 一行 in 数据行) else set()
    return 页面壳("文档账本", f"<h2>文档账本（{len(数据行)} 份 md）</h2>"
              + 表格(("路径", "权威档", "表达什么"), 数据行, 红列=红列集))


def 未完成页(连接) -> bytes:
    数据行 = list(连接.execute("select 号,缺什么,落点 from 未完成 order by 号"))
    return 页面壳("未完成", f"<h2>未完成事项（{len(数据行)} 条）</h2>"
              + 表格(("号", "缺什么", "落点"), 数据行))


def 接口页(连接) -> bytes:
    能力表 = list(连接.execute("select 编号,名称,参数个数,返回类型,可抛错误码 from 能力"))
    参数表 = list(连接.execute("select 编号,序号,名,类型,方向 from 能力参数"))
    类型表 = list(连接.execute("select 标签,名称,说明 from 类型 order by 标签"))
    错误表 = list(连接.execute("select 码,段位,名称,可重试,可自愈,需人工 from 错误码 order by 码"))
    越界表 = 验证.查契约(连接)
    正文 = f"<h2>契约参数越界：{len(越界表)} 处</h2>" + 表格(("能力", "位", "名", "问题"), 越界表, 红列={3})
    正文 += "<h2>能力</h2>" + 表格(("编号", "名称", "参数个数", "返回类型", "可抛错误码"), 能力表)
    正文 += "<h2>能力参数</h2>" + 表格(("编号", "序号", "名", "类型", "方向"), 参数表)
    正文 += "<h2>类型</h2>" + 表格(("标签", "名称", "说明"), 类型表)
    正文 += f"<h2>错误码（{len(错误表)}）</h2>" + 表格(("码", "段位", "名称", "可重试", "可自愈", "需人工"), 错误表)
    return 页面壳("接口", 正文)


def 条款页(连接, 件: str) -> bytes:
    if 件:
        数据行 = list(连接.execute("select 序号,标题,正文 from 条款 where 文档路径=? order by 序号", (件,)))
        if not 数据行:
            return 页面壳("找不到", f"<p class=\"红\">库里没有这份文档：{html.escape(件)}</p>")
        正文 = f"<h2>{html.escape(件)}（{len(数据行)} 节）</h2>"
        for _序号, 标题, 节正文 in 数据行:
            正文 += (f"<h3>{html.escape(标题 or '（无标题）')}</h3>"
                     f"<pre style=\"white-space:pre-wrap;font:12px/1.5 monospace\">{html.escape(节正文)}</pre>")
        return 页面壳(件, 正文)
    数据行 = list(连接.execute(
        "select 文档路径,权威档,count(*),sum(length(正文)) from 条款 group by 文档路径,权威档 "
        "order by 权威档,文档路径"))
    表格行 = [(f'<a href="/条款?件={html.escape(格首)}>{html.escape(格首)}</a>', 格次, 格三, 格四)
              for 格首, 格次, 格三, 格四 in 数据行]
    正文 = (f"<h2>条款（{len(数据行)} 份文档 · {sum(一行[2] for 一行 in 数据行)} 节）</h2>"
            "<p class=\"灰\">全部 md 的正文都在这里 —— md 本身只是本表的一个视图。</p>"
            + 表格(("文档路径", "权威档", "节数", "字节"), 表格行, 原样={0}))
    return 页面壳("条款", 正文)


def 查询页(连接, sql: str) -> bytes:
    输入框 = ("<form method=\"get\" action=\"/查询\">"
              f"<input name=\"sql\" value=\"{html.escape(sql)}\" placeholder=\"select ...\">"
              "<button>跑</button></form>")
    表名 = [一项[0] for 一项 in 连接.execute(
        "select name from sqlite_master where type='table' order by name")]
    正文 = f"<h2>查询（只读 select）</h2>{输入框}<p class=\"灰\">表：{html.escape(' · '.join(表名))}</p>"
    if sql.strip():
        if not sql.strip().lower().startswith(("select", "with", "pragma")):
            return 页面壳("查询", 正文 + "<p class=\"红\">只许 select / with / pragma。</p>")
        try:
            游标 = 连接.execute(sql)
            列名 = tuple(一列[0] for 一列 in 游标.description)
            数据行 = 游标.fetchall()[:500]
            正文 += f"<p>{len(数据行)} 行（最多 500）</p>" + 表格(列名, 数据行)
        except sqlite3.Error as 错误:
            正文 += f"<p class=\"红\">SQL 错：{html.escape(str(错误))}</p>"
    return 页面壳("查询", 正文)


# ── 路由 ──────────────────────────────────────────────────────────
路由表 = {"/": 内核咬合图页, "/命名": 命名页, "/规则": 规则页, "/文档": 文档页,
        "/条款": lambda 连接: 条款页(连接, ""), "/未完成": 未完成页, "/接口": 接口页}


class 页面处理器(BaseHTTPRequestHandler):
    def do_GET(self):
        # 路径要先 `unquote` —— 路由表的键是中文，不解码就永远匹配不上（只命中首页/404）。
        路径 = urlparse(unquote(self.path))
        连接 = 验证.连信息核心库()[0]
        if 连接 is None:
            应答体 = 页面壳("库不在", "<p class=\"红\">库不在。先跑：<code>python3 开发工具/信息核心/建库.py</code></p>")
        elif 路径.path == "/条款":
            应答体 = 条款页(连接, (parse_qs(路径.query).get("件") or [""])[0])
        elif 路径.path == "/节点":
            应答体 = 节点页(连接, (parse_qs(路径.query).get("名") or [""])[0])
        elif 路径.path == "/查询":
            应答体 = 查询页(连接, (parse_qs(路径.query).get("sql") or [""])[0])
        elif 路径.path in 路由表:
            应答体 = 路由表[路径.path](连接)
        else:
            应答体 = 页面壳("404", f"<p class=\"红\">没有这个页面：{html.escape(路径.path)}</p>")
        if 连接 is not None:
            连接.close()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(应答体)))
        self.end_headers()
        self.wfile.write(应答体)

    def log_message(self, *a):
        pass


def 起页面(端口: int = 表定义.默认端口) -> None:
    """起页面端口（**永不返回**）。端口由 `信息核心.py 查看 --端口 N` 传进来。"""
    服务 = ThreadingHTTPServer(("127.0.0.1", 端口), 页面处理器)
    print(f"信息核心页面：http://127.0.0.1:{端口}/　（Ctrl-C 退）")
    服务.serve_forever()
