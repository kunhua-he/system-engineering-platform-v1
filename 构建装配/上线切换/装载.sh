#!/bin/sh
# 装载 —— 起一份新制品（临时端口 + 健康检查，**流量不动**）。形状与判据：形状.md §二。
#
# 用法：构建装配/上线切换/装载.sh <制品标识>
# 说明：本件是**执行**脚本（不是 source 脚本）；变量名一律 ASCII（sh 不认非 ASCII 变量名）。
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# ★ 解释器唯一化：venv 只住主仓（腿里不建）；主仓由 git 解析。
ROOT="$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$ROOT/.git")")"
# ★ 缺材料阻断发布：四类正式材料（源码 / 契约 / 制品 / 工具链）不齐就不许装载。
"$ROOT/构建环境/python/bin/python" "$ROOT/构建装配/上线切换/发布证据.py" --阻断
exec "$ROOT/构建环境/python/bin/python" "$ROOT/构建装配/上线切换/上线切换.py" 装载 "$@"
