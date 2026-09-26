#!/bin/sh
# 环境自检 —— 三问，任一不过即不许开工（见 项目文档/设计文档/内核落点.md 第二节）。
#
#   ① 当前 rustc 版本 == rust-toolchain.toml 里钉的版本
#   ② Cargo.lock 里除本仓成员外无任何第三方包
#   ③ cargo check --workspace --locked 通过（离线），并报墙钟毫秒
#
# 注：变量名用 ASCII —— sh/bash 不认中文变量名（工具链强制）。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PINNED="$(sed -n 's/^channel *= *"\(.*\)"/\1/p' rust-toolchain.toml)"
ACTUAL="$(rustc --version | awk '{print $2}')"
if [ "$PINNED" = "$ACTUAL" ]; then echo "① 工具链  $ACTUAL == 钉的 $PINNED  ✓"
else echo "① 工具链  实际 $ACTUAL != 钉的 $PINNED  ✗"; exit 1; fi

MEMBERS=0
for d in 契约声明 运行内核/*/; do
  [ -f "$d/Cargo.toml" ] && MEMBERS=$((MEMBERS+1))
done
LOCKED=0
[ -f Cargo.lock ] && LOCKED="$(grep -c '^\[\[package\]\]' Cargo.lock || true)"
if [ "$LOCKED" -le "$MEMBERS" ]; then echo "② 依赖    lock 里 $LOCKED 个包 · 本仓成员 $MEMBERS 个 ⇒ 无第三方  ✓"
else echo "② 依赖    lock 里 $LOCKED 个包 > 本仓成员 $MEMBERS 个 ⇒ 有第三方  ✗"; exit 1; fi

START=$(python3 -c 'import time;print(int(time.time()*1000))')
cargo check --workspace --locked >/dev/null 2>&1 || { echo "③ 静态检查  失败  ✗"; exit 1; }
END=$(python3 -c 'import time;print(int(time.time()*1000))')
MS=$((END - START))
echo "③ 静态检查  通过  ✓  （墙钟 ${MS} ms）"
[ "$MS" -gt 3000 ] && echo "   ⚠ 超过 3 秒：慢就是 bug，先查并发与串行点（README 第二节）"
exit 0
