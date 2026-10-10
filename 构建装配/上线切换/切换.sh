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
exec "$ROOT/构建环境/python/bin/python" "$ROOT/构建装配/上线切换/上线切换.py" 切换 "$@"
