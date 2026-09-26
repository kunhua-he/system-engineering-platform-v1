#!/bin/sh
# 环境自检 —— 四问，任一不过即不许开工（见 项目文档/设计文档/内核落点.md 第二节 · 代码形态分工.md 第四节）。
#
#   ① Rust 工具链：当前 rustc 版本 == rust-toolchain.toml 里钉的版本
#   ② Rust 依赖  ：Cargo.lock 里除本仓成员外无任何第三方包
#   ③ Rust 静态检查：cargo check --workspace --locked 通过（离线），并报墙钟毫秒
#   ④ Python 环境：仓库内 venv 存在，且其中无第三方包（只用标准库）
#
# 注：变量名用 ASCII —— sh/bash 不认中文变量名（工具链强制）。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PINNED="$(sed -n 's/^channel *= *"\(.*\)"/\1/p' rust-toolchain.toml)"
ACTUAL="$(rustc --version | awk '{print $2}')"
if [ "$PINNED" = "$ACTUAL" ]; then echo "① Rust 工具链  $ACTUAL == 钉的 $PINNED  ✓"
else echo "① Rust 工具链  实际 $ACTUAL != 钉的 $PINNED  ✗"; exit 1; fi

MEMBERS=0
for d in 契约声明 运行内核/*/; do
  [ -f "$d/Cargo.toml" ] && MEMBERS=$((MEMBERS+1))
done
LOCKED=0
[ -f Cargo.lock ] && LOCKED="$(grep -c '^\[\[package\]\]' Cargo.lock || true)"
if [ "$LOCKED" -le "$MEMBERS" ]; then echo "② Rust 依赖    lock 里 $LOCKED 个包 · 本仓成员 $MEMBERS 个 ⇒ 无第三方  ✓"
else echo "② Rust 依赖    lock 里 $LOCKED 个包 > 本仓成员 $MEMBERS 个 ⇒ 有第三方  ✗"; exit 1; fi

START=$(python3 -c 'import time;print(int(time.time()*1000))')
cargo check --workspace --locked >/dev/null 2>&1 || { echo "③ Rust 静态检查  失败  ✗"; exit 1; }
END=$(python3 -c 'import time;print(int(time.time()*1000))')
MS=$((END - START))
echo "③ Rust 静态检查  通过  ✓  （墙钟 ${MS} ms）"
[ "$MS" -gt 3000 ] && echo "   ⚠ 超过 3 秒：慢就是 bug，先查并发与串行点（README 第二节）"

PY="$ROOT/构建环境/python/bin/python"
if [ ! -x "$PY" ]; then echo "④ Python 环境  venv 不存在  ✗"; exit 1; fi
THIRD="$("$PY" -c '
import sys, pathlib
n = 0
for p in sys.path:
    if p.endswith("site-packages"):
        r = pathlib.Path(p)
        if r.is_dir():
            n += len([x for x in r.iterdir() if x.name != "__pycache__"])
print(n)
')"
PYVER="$("$PY" -c 'import sys;print(sys.version.split()[0])')"
if [ "$THIRD" -eq 0 ]; then echo "④ Python 环境  $PYVER · site-packages 空 ⇒ 只用标准库  ✓"
else echo "④ Python 环境  site-packages 有 $THIRD 项 ⇒ 违规  ✗"; exit 1; fi
exit 0
