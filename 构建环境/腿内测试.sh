#!/bin/sh
# 腿内测试 —— 「腿里跑全量测试」的唯一入口：先把**案例前置**备好，再跑 cargo test。
#
# ★ 为什么存在（债务 534 · 2026-10-13 实测）：腿工作树天然没有预建
#   `构建环境/构建缓存/debug/v1-case-runner`（构建缓存被 .gitignore 忽略），而
#   `对外接口面/调用接口面/src/验证样本/接口面工具族测试.rs` 有几条用例要它、
#   `案例清单_有条数且坏回执为零` 还要读 `测试验证/测试案例/运行回执.jsonl`（同样被忽略）
#   ⇒ **空树首跑必红 3 条**（实测 97 passed / 3 failed），而主干上同一批全过。
#   那不是回归，是**缺前置** —— 但红的样子跟真回归一模一样，容易诱人回滚正确改动。
#   `构建环境/自检.sh` 已声明「本件不替它兜底（那样会把测试面变成假绿）」，
#   本件因此**不是兜底**：它把前置**真备好**（真编出跑者、真让回执落一行）再跑测试
#   —— 那几条用例照旧真判，断言一条不放松。
#
# 用法（在仓根或本腿根跑）：
#     sh 构建环境/腿内测试.sh --查      # 只查前置就绪度（不编不跑，秒级）
#     sh 构建环境/腿内测试.sh            # 备前置 + 跑根工作区全量测试
#     sh 构建环境/腿内测试.sh --扩展      # 再跑扩展工作区（独立 workspace）
#
# 变量名一律 ASCII（macOS 的 /bin/sh 是 bash 3.2，不认中文变量名）。
# ★ **不设 `set -u`**（2026-10-13 实测）：`构建环境/进入.sh` 内部会碰未绑定的变量
#   （`RUSTUP_TOOLCHAIN` 一类）⇒ 本件一旦开了 `set -u`，`. 进入.sh` 当场退 127，
#   而本件把它的输出吞掉后只会报「进不了构建环境」—— 一个看不清真因的假拒。
#
# ★ 壳自量（判据 ㉔）：`.sh` 的壳形是**命令位**上的 `trap …` / `START_EPOCH=`。
#   本件是**命令路**（跑测试）⇒ 带壳自量，不登记白名单 —— 534 这条债要盯的正是「测试面多慢
#   没人拦」。秒级足够（本件量级是几十秒到几分钟，不是 5 秒硬顶那条线）；
#   `trap … EXIT` 保证**每一条退出路**（含用法错、前置未就绪）都报墙钟，不只在成功路。
START_EPOCH=$(date +%s)
# ★ `rc=$?` 必须**先取**：`$?` 与 `$(date …)` 在同一行时，命令替换会在展开阶段**先跑**
#   ⇒ 直接写 `$?` 拿到的是 `date` 自己的 0（实测：真退出码 1 被报成 0）。
trap 'rc=$?; echo "腿内测试：墙钟 $(( $(date +%s) - START_EPOCH )) s · 退出码 $rc"' EXIT

case "${1:-}" in
  --查) MODE=check ;;
  --扩展) MODE=ext ;;
  "") MODE=run ;;
  *) echo "用法：sh 构建环境/腿内测试.sh [--查 | --扩展]" >&2; exit 2 ;;
esac

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "不在 git 仓里 ⇒ 拒" >&2; exit 1; }
cd "$ROOT" || exit 1

if [ ! -f 构建环境/进入.sh ]; then
  echo "找不到 构建环境/进入.sh ⇒ 拒（本件只跑仓内构建环境，不猜路径）" >&2
  exit 1
fi
. ./构建环境/进入.sh >/dev/null 2>&1 || {
  echo "进不了构建环境 ⇒ 拒（逐字复跑看真因：sh -c '. ./构建环境/进入.sh'）" >&2; exit 1; }

RUNNER="${CARGO_TARGET_DIR:-构建环境/构建缓存}/debug/v1-case-runner"
RECEIPT=测试验证/测试案例/运行回执.jsonl

READY_RUNNER=no
[ -x "$RUNNER" ] && READY_RUNNER=yes
READY_RECEIPT=no
[ -s "$RECEIPT" ] && READY_RECEIPT=yes

if [ "$MODE" = check ]; then
  echo "腿内测试前置就绪度（本树 ${ROOT}）"
  echo "  案例跑者 $RUNNER ： $READY_RUNNER"
  echo "  运行回执 $RECEIPT ： $READY_RECEIPT"
  if [ "$READY_RUNNER" = yes ] && [ "$READY_RECEIPT" = yes ]; then
    echo "⇒ 前置已就绪：可直接跑 cargo test（本件不带 --查 即备前置并跑）"
    exit 0
  fi
  echo "⇒ 前置未就绪：那几条用例会红 —— **不是回归，是缺前置**（债务 534）"
  echo "   正解：sh 构建环境/腿内测试.sh（真编出跑者、真让回执落一行，再跑测试）"
  exit 1
fi

# ── 备前置：真编跑者 + 真跑一次案例（让回执落一行）──
echo "腿内测试：备前置 —— cargo build -p v1-case-runner"
cargo build --locked -p v1-case-runner || {
  echo "编不出案例跑者 ⇒ 停（前置没备上，别把红读成回归）" >&2; exit 1; }

echo "腿内测试：备前置 —— 跑一次案例让回执落一行"
cargo run --quiet --locked -p v1-case-runner || {
  echo "案例跑者退出码非 0 ⇒ 停（逐条读数见 $RECEIPT）" >&2; exit 1; }

echo "腿内测试：前置已就绪 ⇒ 跑全量测试"
cargo test --workspace --locked
CODE=$?
if [ "$CODE" -ne 0 ]; then
  echo "腿内测试：根工作区测试退出码 $CODE" >&2
  exit "$CODE"
fi

if [ "$MODE" = ext ]; then
  echo "腿内测试：扩展工作区（独立 workspace）"
  ( cd 扩展根目录/原子支持库/编译器支持库 && cargo test --locked ) || exit 1
fi

echo "腿内测试：全过"
exit 0
