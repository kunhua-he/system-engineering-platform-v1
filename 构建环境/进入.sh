#!/bin/sh
# 进入本仓的构建环境：source 本文件。
#
#   . 构建环境/进入.sh
#
# 把两个环境都钉在仓库内：
#   Rust   —— 工具链版本由 rust-toolchain.toml 钉死；cargo 的家与构建缓存都在 构建环境/ 下
#   Python —— 仓库内 venv（只用标准库），供开发工具与验证面使用
# 一切产物落在 构建环境/ 下，不往 ~/.cargo、~/.rustup、~/.local、/tmp 乱飞。
#
# 注：变量名用 ASCII —— sh/bash 不认中文变量名（工具链强制，同 Cargo 包名）。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CARGO_HOME="$ROOT/构建环境/cargo"
export CARGO_TARGET_DIR="$ROOT/构建环境/构建缓存"
export RUSTUP_TOOLCHAIN="$(sed -n 's/^channel *= *"\(.*\)"/\1/p' "$ROOT/rust-toolchain.toml")"
export CARGO_NET_OFFLINE=true
export VIRTUAL_ENV="$ROOT/构建环境/python"
export PATH="$VIRTUAL_ENV/bin:$PATH"
unset PYTHONHOME
echo "仓根        : $ROOT"
echo "Rust        : $RUSTUP_TOOLCHAIN（由 rust-toolchain.toml 钉死）"
echo "cargo 家    : $CARGO_HOME"
echo "构建缓存    : $CARGO_TARGET_DIR"
echo "Python      : $("$VIRTUAL_ENV/bin/python" -c 'import sys;print(sys.version.split()[0])')（$VIRTUAL_ENV）"
echo "离线构建    : $CARGO_NET_OFFLINE"
echo
echo "自检四问："
"$ROOT/构建环境/自检.sh"
