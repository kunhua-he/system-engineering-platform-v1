# -*- coding: utf-8 -*-
"""前端零逻辑语义判 · 内联脚本扫描面的身份证。"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from . import 常量

from .合成仓 import 造干净仓
from .常量 import 前端逻辑模式, 检查名
from .判据_拓扑 import 前端命中
from .测试件 import 生产区文本
from .验证 import 验证


def 自检_前端语义判据() -> list:
    """⑪ 判据 6（前端零逻辑）**从词命中改成语义判**后的身份证（2026-09-27 收窄）。

    为什么单列：原模式 `JSON\\.parse|JSON\\.stringify|校验|解析|生成|validate|parse\\(` 是一袋词，
    它把 `前端呈现/网页应用/取接口.js` 里**传输必需的 `JSON.stringify(文本)`** 判成了违规
    收窄最怕**收过头**：把真解析一起放过 ⇒ 判据变成空转。
    故成对钉三层：
      · **反向样本**：注入一处**真 `JSON.parse`** ⇒ ⑪ 必须报红、且指到注入件；
      · **正向样本**：注入 `JSON.stringify` / 一段**解释自身不是违规的注释** / 纯拼接搬运 ⇒ 不许报红；
      · **承重证明（关/开对照）**：把判据临时关掉（模式换成永不匹配）再注入**同一处真解析**
        ⇒ 必须不报 —— 证明那处红**确实由本判据承重**，不是别的判据顺带报的。
    依据：项目文档/设计文档/判据的可信性.md §三.5（判据的解析器/模式也是假绿来源）。
    """
    import tempfile

    出 = []
    注入件 = "前端呈现/网页应用/注入样例.js"

    def 断言(名, 好, 说明):
        出.append((名, 好, 说明))

    # ── 第一层：纯文本（快，直接钉模式本身；样本取自现场实测的形状）──
    真解析 = 'export function 取值(文) { return JSON.parse(文); }\n'
    序列化 = 'export function 编码(文) { return JSON.stringify(文); }\n'
    辩解注释 = (
        "// `JSON.stringify` 只做编码：把文本编成 JSON 字面量，不改内容、不看内容。\n"
        "// 这里不解析、不校验 —— 任何判断都在后端。\n"
        "export function 编码(文) { return JSON.stringify(文); }\n"
    )
    搬运 = 'export function 拼(号, 文) { return "{" + 号 + ":" + 文 + "}"; }\n'
    词袋 = re.compile(r"JSON\.parse|JSON\.stringify|校验|解析|生成|validate|parse\(")

    def 命中(文, 模式=None):
        return [匹配.group(0) for 匹配 in (模式 or 常量.前端逻辑模式).finditer(生产区文本(文))]

    断言(
        "反向样本：真 `JSON.parse` ⇒ 新模式报（解析 = 对内容作出判断）",
        bool(命中(真解析)),
        f"命中 {命中(真解析)}（要求非空）",
    )
    断言(
        "正向样本：`JSON.stringify` ⇒ 新模式不报（序列化是传输必需的编码）",
        not 命中(序列化),
        f"命中 {命中(序列化)}（要求空）——它不看内容、不改内容",
    )
    断言(
        "正向样本：一段「解释自身不是违规」的注释 ⇒ 新模式不报",
        not 命中(辩解注释),
        f"命中 {命中(辩解注释)}（要求空）——#176 的病灶就在这里",
    )
    断言(
        "对照：同一份文本，**原词袋模式**报（证明收窄真治了那个病）",
        bool(命中(辩解注释, 词袋)) and not 命中(辩解注释),
        f"原模式命中 {命中(辩解注释, 词袋)} · 新模式命中 {命中(辩解注释)}",
    )
    断言(
        "正向样本：纯拼接搬运（编码传输串）⇒ 不报",
        not 命中(搬运),
        f"命中 {命中(搬运)}（要求空）——纯搬运/编码允许",
    )
    断言(
        "反向样本：正则**字面量在值位置**（赋给标识符 / 作实参 / `return` / 对象属性值 / 数组元素 / 三元分支 / 箭头体）⇒ 报",
        all(
            命中(样本)
            for 样本 in (
                "const 形 = /^[0-9]+$/;\n",
                "export function 判(s) { return /^[0-9]+$/.test(s); }\n",
                "export function 判(s, 另) { return 查(s, /^[0-9]+$/); }\n",
                "const 表 = { 模式: /^[0-9]+$/ };\n",
                "const 表 = [/^[0-9]+$/, /^[a-z]+$/];\n",
                "export function 取(x) { return x ? /^[0-9]+$/ : /^[a-z]+$/; }\n",
                "const 判 = (s) => /^[0-9]+$/;\n",
            )
        ),
        "七种值位置各报一处（要求都非空）",
    )
    断言(
        "正向样本：**除法**与含 `//` 的字符串/注释 ⇒ 不报（值位置的口径不许误伤它们）",
        not any(
            命中(样本)
            for 样本 in (
                "export function 比(a, b) { return a / b; }\n",
                "export function 比(a, b) { const 商 = a / b; return 商; }\n",
                "export function 比(a, b, c) { return a ? b / c : c / b; }\n",
                "export function 取(表, i, j) { return 表[i / j]; }\n",
                "// 注释里写 /^[0-9]+$/ 不算逻辑\n",
                'const 网址 = "https://example.com/a/b";\n',
            )
        ),
        "除法与注释/字符串不许被当成正则字面量",
    )
    断言(
        "反向样本：`DOMParser` / `eval(` / 正则 `.test(` 这类真判断 ⇒ 报",
        all(
            命中(样本)
            for 样本 in (
                "const 解 = new DOMParser();\n",
                "export function 跑(s) { return eval(s); }\n",
                "export function 判(s) { return /^[0-9]+$/.test(s); }\n",
            )
        ),
        "三种判断形各报一处（要求都非空）",
    )
    # ── #38 残留关闭：正则字面量的**非调用**用法（八种值位置前缀认不出的那些）──
    # 旧口径只认 `=` `return` `,` `(` `:` `[` `?` `=>` 后面的 `/…/`；`||` `!` `&&` `}` `;`
    # 后面的一律不认（#38 记的就是这条）。现在改走 `命名扫描._前是表达式头`（位置无关）。
    # **正向样本同时钉住**：旧口径已认得出的那几种不许因此报成两处。
    非调用样本 = {
        "`||` 之后": "export function 判(s) { return 甲 || /^[0-9]+$/.test(s); }\n",
        "`!` 之后": "export function 判(s) { return !/^[0-9]+$/.test(s); }\n",
        "`&&` 之后": "const 好 = 甲 && /^[a-z]+$/;\n",
        "`;` 之后": "function 甲(){};/^x$/.test(文);\n",
    }
    断言(
        "反向样本（#38）：正则字面量的**非调用**用法（`||` `!` `&&` `;` 之后）⇒ 认得出",
        all(前端命中(生产区文本(样本)) for 样本 in 非调用样本.values()),
        f"四形命中：{ {名: 前端命中(生产区文本(文)) for 名, 文 in 非调用样本.items()} }",
    )
    断言(
        "正向样本（#38）：值位置的 `/…/` 只报**一处**（两支去重，不许报两次）",
        len(前端命中(生产区文本("const 形 = /^[0-9]+$/;\n"))) == 1,
        f"命中 {前端命中(生产区文本('const 形 = /^[0-9]+$/;\n'))}（要求恰好 1 处）",
    )
    断言(
        "正向样本（#38）：除法与含 `//` 的字符串/注释⇒ 位置无关的扫描也不误伤",
        not any(
            前端命中(生产区文本(样本))
            for 样本 in (
                "export function 比(a, b) { return a / b; }\n",
                "export function 比(a, b) { const 商 = a / b; return 商; }\n",
                "// 注释里写 /^[0-9]+$/ 不算逻辑\n",
                'const 网址 = "https://example.com/a/b";\n',
            )
        ),
        "除法与注释/字符串里的 `/` 不许被当成正则字面量",
    )

    # ── 第二层：端到端（注入到干净合成仓 ⇒ 跑真判据；含关/开对照）──
    def 跑(注入文, 关判据=False):
        with tempfile.TemporaryDirectory(prefix="一键验证前端语义-") as 临时:
            临根 = Path(临时) / "仓"
            造干净仓(临根)
            if 注入文 is not None:
                (临根 / 注入件).write_text(注入文, encoding="utf-8")
            原模式 = 常量.前端逻辑模式
            try:
                if 关判据:
                    常量.前端逻辑模式 = re.compile(r"(?!)")  # 永不匹配 = 判据关掉
                return 验证(临根, 两遍=False)
            finally:
                常量.前端逻辑模式 = 原模式

    def 判据6条(结果):
        return [
            条
            for 条 in 结果["失败"] + 结果["未判"]
            if isinstance(条, dict) and 条["检查"] == 检查名[10] and "前端呈现" in 条["位置"]
        ]

    def 读数(结果):
        return [f"{条['位置']} ｜ {条['缺什么'][:70]}" for 条 in 判据6条(结果)]

    def 指到注入件(结果):
        return any(
            注入件 in 条["位置"] or 注入件 in 条["缺什么"] for 条 in 判据6条(结果)
        )

    开 = 跑(真解析)
    关 = 跑(真解析, 关判据=True)
    序列化果 = 跑(序列化)
    注释果 = 跑(辩解注释)
    基线 = 跑(None)

    断言(
        "反向样本（端到端）：干净仓 + 一处真 `JSON.parse` ⇒ ⑪ 判据 6 报红且指到注入件",
        len(判据6条(开)) == 1 and 指到注入件(开),
        f"⑪ 报 {len(判据6条(开))} 条：{读数(开)}",
    )
    断言(
        "承重证明（关/开对照）：判据关掉 + **同一处**真解析 ⇒ 不报",
        len(判据6条(关)) == 0,
        f"关掉后 ⑪ 报 {len(判据6条(关))} 条（要求 0）：{读数(关)}",
    )
    断言(
        "正向样本（端到端）：干净仓 + `JSON.stringify` ⇒ ⑪ 判据 6 不报",
        len(判据6条(序列化果)) == 0,
        f"⑪ 报 {len(判据6条(序列化果))} 条（要求 0）：{读数(序列化果)}",
    )
    断言(
        "正向样本（端到端）：干净仓 + 辩解注释 ⇒ ⑪ 判据 6 不报",
        len(判据6条(注释果)) == 0,
        f"⑪ 报 {len(判据6条(注释果))} 条（要求 0）：{读数(注释果)}",
    )
    断言(
        "基线：干净合成仓不注入 ⇒ ⑪ 判据 6 也不报（正向样本上不误报）",
        len(判据6条(基线)) == 0,
        f"⑪ 报 {len(判据6条(基线))} 条（要求 0）：{读数(基线)}",
    )
    return 出


def 自检_前端内联脚本() -> list:
    """⑪-6 的 `.html` 内联 `<script>` 扫描面的身份证。

    反向样本：只含**内联** `<script>…JSON.parse(…)</script>` 的 `.html` ⇒ ⑪-6 必须报
    （证明内联脚本真进了扫描面）。
    正向样本：只含**外链** `<script src=…>`（外链由它自身的 `.js` 件覆盖），
    且**标记属性里**写了 `JSON.parse` 的字样 ⇒ ⑪-6 不报（证明只扫脚本体，不扫标记）。
    承重证明（关/开对照）：关掉 `前端逻辑模式` + 同一注入 ⇒ 不报。
    """
    import tempfile

    出 = []
    注入件 = "前端呈现/网页应用/注入样例.html"
    反向文 = '<html><body><script>const x = JSON.parse("{}");</script></body></html>\n'
    正向文 = (
        '<html><body data-注="JSON.parse( 只是标记属性里的字样，不是脚本">\n'
        '<script type="module" src="应用.js"></script></body></html>\n'
    )

    def 跑(html文, 关判据=False):
        with tempfile.TemporaryDirectory(prefix="一键验证前端内联-") as 临时:
            临根 = Path(临时) / "仓"
            造干净仓(临根)
            if html文 is not None:
                (临根 / 注入件).write_text(html文, encoding="utf-8")
            原模式 = 常量.前端逻辑模式
            try:
                if 关判据:
                    常量.前端逻辑模式 = re.compile(r"(?!)")  # 永不匹配 = 判据关掉
                return 验证(临根, 两遍=False)
            finally:
                常量.前端逻辑模式 = 原模式

    def 判据6条(结果):
        return [
            条
            for 条 in 结果["失败"] + 结果["未判"]
            if isinstance(条, dict) and 条["检查"] == 检查名[10] and "前端呈现" in 条["位置"]
        ]

    开 = 跑(反向文)
    关 = 跑(反向文, 关判据=True)
    正 = 跑(正向文)
    出.append(
        (
            "反向样本：`.html` 内联 `<script>` 里的真 `JSON.parse` ⇒ ⑪-6 报",
            len(判据6条(开)) >= 1,
            f"⑪ 报 {len(判据6条(开))} 条（要求 ≥1）",
        )
    )
    出.append(
        (
            "承重证明（关/开对照）：关掉 `前端逻辑模式` + 同一注入 ⇒ 不报",
            len(判据6条(关)) == 0,
            f"关掉后 ⑪ 报 {len(判据6条(关))} 条（要求 0）",
        )
    )
    出.append(
        (
            "正向样本：只含外链 `<script src=…>`（标记属性里有 `JSON.parse` 字样）⇒ 不报",
            len(判据6条(正)) == 0,
            f"⑪ 报 {len(判据6条(正))} 条（要求 0）——只扫脚本体，不扫标记",
        )
    )
    return 出
