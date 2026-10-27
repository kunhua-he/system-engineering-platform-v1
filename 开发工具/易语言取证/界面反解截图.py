#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""界面反解截图 —— 把**我方前端**渲染成 PNG，喂给 `配色对拍.py`。

**为什么需要它**：`配色对拍.py` 只吃两张 PNG，而「我方那一张」此前是用一个**没进仓的临时脚本**
渲染的 ⇒ 整条视觉验收链**不可复跑**（`前端呈现/说明.md` §八 记着这条待办）。
本脚本把那一步落进仓：起一个本地静态服务（ES 模块必须走 http，`file://` 会被浏览器挡），
用 playwright 的无头 chromium 按**参考图的尺寸**截图。

**与 `说明.md` §八 的叫法冲突（如实记）**：§八 把 `界面反解截图.py` 说成「解**参考图**」，
而本脚本做的是「渲染**我方**前端」。名字沿用 §八 已登记的那个（免得凭空多一个名字），
但**两件事不同** ⇒ 若将来真要「解参考图」，那是另一件，另起名字。

跑法（要 playwright 与它的 chromium；**缺什么就报什么，不许编读数**）：
    python3 开发工具/易语言取证/界面反解截图.py <输出.png> [宽 高]
    # 默认尺寸 = 参考图尺寸 1426x755；输出约定落临时区，**不进制品**
    # 出图后接着对拍：
    python3 开发工具/易语言取证/配色对拍.py 项目文档/界面参考/易语言IDE_截图.png <输出.png>

**依赖（例外，如实登记）**：本件要 `playwright`（+ chromium）。仓内 venv（`构建环境/python`）是
`--without-pip`，且 `构建环境/自检.sh` ④ 要求 site-packages 空（只用标准库）⇒ **本件只在系统
`python3` 下跑**。为何是例外：它是**取证 / 视觉**工具链的依赖，不进闸 0、不参与「Python 只用标准库」
那条口径；装进 venv 反而会把那条口径破在 venv 里（自检 ④ 当场红）。`--help` 不 import playwright。

退出码：0 = 出图；1 = 起不来或渲染失败（原因一律打到 stderr，**不假装成功**）。
"""
import functools
import 开发工具.易语言取证.开发工具.server
import socketserver
import sys
import threading
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包（构建装配.门禁）之前（见 构建装配/门禁/命令壳.py）

仓根 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(仓根))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

前端目录 = 仓根 / "前端呈现" / "网页应用"
参考图 = 仓根 / "项目文档" / "参考" / "易语言IDE_截图.png"
参考尺寸 = (1426, 755)
# ★ 上面三个是**唯一实现**（2026-09-30 收口）：`前端呈现/视觉对拍.py` 引本处，不再复写。


def 入口函数(命令行参数):
    if 命令行参数 and 命令行参数[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if not 命令行参数:
        print(__doc__)
        return 1
    出图 = Path(命令行参数[0])
    if len(命令行参数) >= 3:
        try:
            宽度, 高度 = int(命令行参数[1]), int(命令行参数[2])
        except ValueError:
            print(f"宽高要是整数：{命令行参数[1]!r} {命令行参数[2]!r}", file=sys.stderr)
            return 1
    else:
        宽度, 高度 = 参考尺寸
    if not 前端目录.is_dir():
        print(f"起不来：前端目录不存在 {前端目录}", file=sys.stderr)
        return 1
    try:
        from 开发工具.易语言取证.playwright.sync_api import sync_playwright
    except ImportError as 错误:
        print(f"起不来：没有 playwright 模块（{错误}）", file=sys.stderr)
        print("  装法：pip install playwright 然后 playwright install chromium", file=sys.stderr)
        return 1

    # 本地静态服务：ES 模块要 http；端口取 0 = 让内核给一个空闲口（不写死端口，免得撞）。
    # 静音访问日志：静态服务是本脚本的内部件，它的 404 噪声（页面会拉 `/接口`）不该混进读数。
    # 用**赋值**而不是子类 —— 本文件是 py-script，判据「只许一个顶层 def/class」多一个就欠债。
    开发工具.server.SimpleHTTPRequestHandler.log_message = lambda *实参, **键参数: None
    处理 = functools.partial(开发工具.server.SimpleHTTPRequestHandler, directory=str(前端目录))
    try:
        服务 = socketserver.TCPServer(("127.0.0.1", 0), 处理)
    except OSError as 错误:
        print(f"起不来：静态服务开不了（{错误}）", file=sys.stderr)
        return 1
    监听端口 = 服务.server_address[1]
    服务.allow_reuse_address = True
    threading.Thread(target=服务.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as 浏览器驱动:
            try:
                浏览器 = 浏览器驱动.chromium.launch()
            except Exception as 错误:  # playwright 的错误类型随版本变，按「起不来」一类处理
                print(f"起不来：chromium 启动失败（{错误}）", file=sys.stderr)
                print("  装法：playwright install chromium", file=sys.stderr)
                return 1
            try:
                页面 = 浏览器.new_page(viewport={"width": 宽度, "height": 高度})
                # `load` 而不是 `networkidle`：本页会周期性拉 `/接口`，networkidle 可能永远不达。
                页面.goto(f"http://127.0.0.1:{监听端口}/", wait_until="load", timeout=5000)
                页面.wait_for_timeout(800)  # 让首帧布局与字体落定
                页面.screenshot(path=str(出图))
            finally:
                浏览器.close()
    finally:
        服务.shutdown()
        服务.server_close()

    if not 出图.is_file():
        print(f"渲染失败：没写出来 {出图}", file=sys.stderr)
        return 1
    print(f"出图 {出图} · {宽度}x{高度} · {出图.stat().st_size} 字节 · 静态服务端口 {监听端口}")
    print(f"对拍：python3 开发工具/易语言取证/配色对拍.py {参考图.relative_to(仓根)} {出图}")
    return 0


# `尾巴余量毫秒=200`：壳在 import 业务包之前起表 ⇒ 量不到「解释器启动 + 结果打印 + 进程退出」
# 那一段；200 是它的上界，与 `构建装配/一键验证/一键验证/自检样本/自检_延迟与两遍.py` 那条尾巴自证同源
# （同一个解释器、同一段物理尾巴）。阈值 = 共享 `硬顶毫秒` − 这个余量。
if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="渲染慢就降尺寸（只喂 <宽> <高> 两个更小的数）：重活是 playwright 起"
                         "chromium 与页面加载，`入口函数` 里的 `wait_for_timeout(800)` 也可按需收小。"))
