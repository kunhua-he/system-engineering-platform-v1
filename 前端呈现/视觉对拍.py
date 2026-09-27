#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉对拍 —— 起网关 → 渲染我方前端 → 与参考图对拍（去掉错误文本污染）。

**为什么要它**：`开发工具/取证/界面反解截图.py` 默认只起一个静态服务；网关不在时页面拉
`/接口` 全 404，标题条「连接状态」、左栏「支持库树」、底部「状态条」三处渲染的是**错误文本**，
不是本页真实状态。实测（同一视口 1426x755，逐像素差）：网关起着 vs 网关没起 **16711 px**，
分布在 y=10..22（标题条）· y=129..527（左栏树）· y=748..753（状态条）—— **三处都在「壳区」里**
⇒「只截壳区（去掉底格）」截不掉污染（污染不在底格、在壳里）。所以 #227 取**让渲染时网关起着**。

**本件是驱动，不是第二套读数**：像素口径仍由 `开发工具/取证/配色对拍.py` 出（本件出图后调它）；
不给网关时**转调**既有渲染件，不另起一套静态服务。

跑法（从仓根）：
    python3 前端呈现/视觉对拍.py /tmp/我方.png --网关 <启动网关可执行件> --声明根 <扩展根声明.json>
    # 不给 --网关 / --声明根 ⇒ 转调老路（带污染，只作对照）
    # 出图后自动调配色对拍；加 --只出图 就只出图。

退出码：0 = 出图并打完读数；1 = 起不来 / 渲染失败 / 对拍失败（原因打到 stderr，不假装成功）。
"""
import subprocess
import sys
import time
from pathlib import Path

起始时刻 = time.monotonic()  # 壳起表点：必须在 import 业务包（构建装配.门禁）之前

仓根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(仓根))  # 仓根：取共享门禁
from 构建装配.门禁 import 自门禁  # noqa: E402

前端目录 = 仓根 / "前端呈现" / "网页应用"
参考图 = 仓根 / "项目文档" / "参考" / "易语言IDE_截图.png"
对拍件 = 仓根 / "开发工具" / "取证" / "配色对拍.py"
旧渲染件 = 仓根 / "开发工具" / "取证" / "界面反解截图.py"
参考尺寸 = (1426, 755)


def 入口函数(参数):
    if not 参数:
        print(__doc__)
        return 1
    出图 = Path(参数[0])
    宽度, 高度 = 参考尺寸
    网关 = 声明根 = None
    只出图 = False
    序号 = 1
    while 序号 < len(参数):
        本参 = 参数[序号]
        if 本参 == "--网关":
            网关 = 参数[序号 + 1]; 序号 += 2
        elif 本参 == "--声明根":
            声明根 = 参数[序号 + 1]; 序号 += 2
        elif 本参 == "--只出图":
            只出图 = True; 序号 += 1
        else:
            宽度, 高度 = int(参数[序号]), int(参数[序号 + 1]); 序号 += 2

    if not (网关 and 声明根):
        print("没给 --网关 / --声明根 ⇒ 转调界面反解截图.py 的老路（只起静态服务 · 带错误文本污染）")
        错误码 = subprocess.call([sys.executable, str(旧渲染件), str(出图), str(宽度), str(高度)])
    else:
        错误码 = 0
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as 错误:
            print(f"起不来：没有 playwright（{错误}）", file=sys.stderr)
            return 1
        # 起**演示口径**的网关：端口取 0 让它自身报，静态根指我方前端目录（同源）。
        进程 = subprocess.Popen(
            [str(网关), "--声明根", str(声明根), "--端口", "0", "--静态根", str(前端目录)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        端口 = None
        for 源码行 in 进程.stdout:
            print("  [网关] " + 源码行.rstrip())
            if "监听 127.0.0.1:" in 源码行:
                端口 = int(源码行.rsplit(":", 1)[1])
                break
        if not 端口:
            进程.kill()
            print("起不来：网关没报监听端口（看上面它的输出）", file=sys.stderr)
            return 1
        网址 = f"http://127.0.0.1:{端口}/"
        try:
            with sync_playwright() as 驱动器:
                浏览器 = 剧.chromium.launch()
                try:
                    页面 = 浏览器.new_page(viewport={"width": 宽度, "height": 高度})
                    页面.goto(网址, wait_until="load", timeout=5000)
                    页面.wait_for_timeout(800)  # 让首帧布局与字体落定
                    页面.screenshot(path=str(出图))
                finally:
                    浏览器.close()
        finally:
            进程.kill()
            进程.wait()

    if 错误码:
        return 错误码
    if not 出图.is_file():
        print(f"渲染失败：没写出来 {出图}", file=sys.stderr)
        return 1
    print(f"出图 {出图} · {宽度}x{高度} · {出图.stat().st_size} 字节")
    if 只出图:
        return 0
    return subprocess.call([sys.executable, str(对拍件), str(参考图.relative_to(仓根)), str(出图)])


if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 入口函数(sys.argv[1:]), 尾巴余量毫秒=200,
                    修法="渲染慢就降尺寸（喂两个更小的整数）：重活是 playwright 起 chromium 与页面加载，"
                         "`入口函数` 里的 `wait_for_timeout(800)` 也可按需收小。"))
