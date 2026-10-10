#!/bin/sh
# 回退 —— 指回上一份（不给参数就用「上一份」＝回退账首；`--步=N` 取账里第 N 条；
#        给参数可回退到**任意一份已产出的制品**）。形状与判据：形状.md §二。
#
# 用法：构建装配/上线切换/回退.sh [<制品标识>] [--步=N]
# 说明：本件是**执行**脚本（不是 source 脚本）；变量名一律 ASCII（sh 不认非 ASCII 变量名）。
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# ★ 解释器唯一化：venv 只住主仓（腿里不建）；主仓由 git 解析。
ROOT="$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$ROOT/.git")")"
exec "$ROOT/构建环境/python/bin/python" "$ROOT/构建装配/上线切换/上线切换.py" 回退 "$@"
