#!/bin/sh
# 环境自检 —— 四问，任一不过即不许开工（见 项目文档/设计文档/内核落点.md 第二节 · 代码形态分工.md 第四节）。
#
#   ① Rust 工具链：当前 rustc 版本 == rust-toolchain.toml 里钉的版本
#   ② Rust 依赖  ：Cargo.lock 里除本仓成员外无任何第三方包
#   ③ Rust 静态检查：**两个工作区**都 `cargo check --all-targets --locked` 通过（离线），并报墙钟毫秒
#      —— 根工作区（底座 + 跑案例）与扩展工作区（`扩展根目录/原子支持库/编译器支持库`，
#      被根 `Cargo.toml` exclude 的独立工作区）。`--all-targets` 才编 `#[cfg(test)]` 与 `tests/`：
#      少了它，测试面的编译错从不被编，也就没人抓。
#      ★ **收口必跑**：本件就是收口路径。cargo 是分钟级 ⇒ **不**进 5 秒硬顶的闸 0，
#        也**不**进每提交的 pre-commit；测试面的编译门禁接在**这一条**上。
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
for d in 契约声明 运行内核/*/ 跨语言适配/*/ 对外接口面/*/ 测试验证/案例/*/; do
  [ -f "$d/Cargo.toml" ] && MEMBERS=$((MEMBERS+1))
done
LOCKED=0
[ -f Cargo.lock ] && LOCKED="$(grep -c '^\[\[package\]\]' Cargo.lock || true)"
# ③ 第三方的**定义**：lock 里带 `source =` 的包（来自 registry 或 git）。仓内件（工作区成员 ·
#    被 exclude 但仍是路径依赖的扩展）**没有** source 字段 ⇒ 问「有没有 source」才是直接问法。
#    ★ 不许改成「数包数 ≤ 数成员」：那个口径实测**假红**（2026-09-27）——成员得自行数，
#    数漏一个就误判；而被 exclude 的扩展仍进 lock。当时 lock 15 包 = 工作区 14 成员 + 1 被 exclude 的扩展，
#    旧口径只数出 10 个成员 ⇒ 假报「有第三方」，把零依赖的仓判成违规。
THIRD_PKG="$(grep -c '^source = ' Cargo.lock || true)"
if [ "$THIRD_PKG" -eq 0 ]; then echo "② Rust 依赖    lock 里 $LOCKED 个包（本仓 $MEMBERS 个成员）· 无一来自 registry/git ⇒ 无第三方  ✓"
else echo "② Rust 依赖    lock 里 $THIRD_PKG 个包来自 registry/git ⇒ 有第三方  ✗"; exit 1; fi

START=$(python3 -c 'import time;print(int(time.time()*1000))')
cargo check --workspace --all-targets --locked >/dev/null 2>&1 \
  || { echo "③ Rust 静态检查（根工作区 · --all-targets）失败  ✗"; exit 1; }
END=$(python3 -c 'import time;print(int(time.time()*1000))')
MS=$((END - START))
echo "③ Rust 静态检查  根工作区 --all-targets  通过  ✓  （墙钟 ${MS} ms）"
[ "$MS" -gt 3000 ] && echo "   ⚠ 超过 3 秒：慢就是 bug，先查并发与串行点（README 第二节）"

# 扩展工作区（独立）：被根 `Cargo.toml` exclude ⇒ 上面那条 `--workspace` 看不见它一个字。
# 它的测试面此前无门禁，靠的就是这一条补上。用 `--manifest-path` 指到它自身的 Cargo.toml。
START=$(python3 -c 'import time;print(int(time.time()*1000))')
cargo check --manifest-path 扩展根目录/原子支持库/编译器支持库/Cargo.toml --all-targets --locked >/dev/null 2>&1 \
  || { echo "③ Rust 静态检查（扩展工作区 · --all-targets）失败  ✗"; exit 1; }
END=$(python3 -c 'import time;print(int(time.time()*1000))')
MS=$((END - START))
echo "③ Rust 静态检查  扩展工作区 --all-targets  通过  ✓  （墙钟 ${MS} ms）"
[ "$MS" -gt 3000 ] && echo "   ⚠ 超过 3 秒：慢就是 bug，先查并发与串行点（README 第二节）"

# ★ 本件只做**编译面**，不跑 `cargo test`：`cargo test --workspace --locked` 现在**不自洽** ——
#   ① 有几条用例转调 `构建环境/构建缓存/debug/v1-case-runner`，得先
#      `cargo build -p v1-case-runner` 把那个二进制编出来；
#   ② `案例清单_有条数且坏回执为零` 读**真仓根**的 `测试验证/案例/运行回执.jsonl`，
#      而该件被 gitignore ⇒ **空树首跑必红**。
#   最小口径：要跑测试就先 `cargo build -p v1-case-runner`、再跑一次案例生成回执，然后 `cargo test`。
#   本件不替它兜底（那样会把测试面变成假绿）。

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
