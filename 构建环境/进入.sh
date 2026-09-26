#!/bin/sh
# 进入本仓的构建环境：source 本文件。
#
#   . 构建环境/进入.sh
#
# 做三件事：把 cargo 的家与构建缓存都钉在仓库内、按 rust-toolchain.toml 选工具链、跑一次自检。
# 一切产物落在 构建环境/ 下，不往 ~/.cargo、~/.rustup、/tmp 乱飞。
#
# 注：变量名用 ASCII —— sh/bash 不认中文变量名（工具链强制，同 Cargo 包名）。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CARGO_HOME="$ROOT/构建环境/cargo"
export CARGO_TARGET_DIR="$ROOT/构建环境/构建缓存"
export RUSTUP_TOOLCHAIN="$(sed -n 's/^channel *= *"\(.*\)"/\1/p' "$ROOT/rust-toolchain.toml")"
export CARGO_NET_OFFLINE=true
echo "仓根        : $ROOT"
echo "工具链      : $RUSTUP_TOOLCHAIN（由 rust-toolchain.toml 钉死）"
echo "cargo 家    : $CARGO_HOME"
echo "构建缓存    : $CARGO_TARGET_DIR"
echo "离线构建    : $CARGO_NET_OFFLINE"
echo
echo "自检三问："
"$ROOT/构建环境/自检.sh"
