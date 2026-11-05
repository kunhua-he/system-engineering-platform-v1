#!/bin/sh
# 切换 —— 把流量指过去（停掉活着的实例 → 在流量端口上起目标 → 原子改「当前」）。形状与判据：形状.md §二。
#
# 用法：构建装配/上线切换/切换.sh <制品标识>
#       构建装配/上线切换/切换.sh --模式=停        # 模式=停：停掉实例、让流量口空着（不是第四条命令）
# 说明：本件是**执行**脚本（不是 source 脚本）；变量名一律 ASCII（sh 不认非 ASCII 变量名）。
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# ★ 解释器唯一化：venv 只住主仓（腿里不建）；主仓由 git 解析。
ROOT="$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$ROOT/.git")")"
# ★ 流量口若被「网关守护」占着，先让它让路。
#
# 守护壳的活是「端口没人听就拉起来」，而切换要做的正是「停旧的、在同一个端口起新的」——
# 两者抢同一口，实测切换直接失败 `端口绑不上：Address already in use`，看起来像制品坏了。
# 顺序必须是：停守护壳 → 切换 → 起回守护壳。这里只做前两步，收尾在第 24 行之后。
RUNDIR="${V1_RUN_ROOT:-/Users/hekunhua/Library/Application Support/系统工程平台V1/运行}"
GUARD="$RUNDIR/网关守护.sh"
GUARD_RUNNING=0
if pgrep -f "网关守护.sh" >/dev/null 2>&1; then
  GUARD_RUNNING=1
  # 光杀壳不够：网关是壳的子进程，壳死了它照样占着端口。
  # 顺序必须是「先杀监听端口的网关进程，再杀壳」——反过来会让正在保活的壳立刻重拉一个。
  pkill -f "网关守护.sh" 2>/dev/null || true
  pids=$(/usr/sbin/lsof -t -iTCP:43110 -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    sleep 2
    pids=$(/usr/sbin/lsof -t -iTCP:43110 -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      kill -9 $pids 2>/dev/null || true
    fi
    sleep 1
  fi
fi

"$ROOT/构建环境/python/bin/python" "$ROOT/构建装配/上线切换/上线切换.py" 切换 "$@"
SWITCH_EXIT=$?

# 收尾：按原样把守护壳起回去（只在它本来就在跑时）。
if [ "$GUARD_RUNNING" = "1" ] && [ -f "$GUARD" ]; then
  nohup sh "$GUARD" >/dev/null 2>&1 &
fi
exit "$SWITCH_EXIT"
