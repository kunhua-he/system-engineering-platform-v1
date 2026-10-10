#!/bin/sh
# 进入本仓的构建环境。两种用法都行：
#
#   . 构建环境/进入.sh     # 在当前 shell 里生效（在仓库根执行）
#
# **只设环境，绝不 exec。** 早先版本在末尾用 $0 判断「是否被 source」再 exec 一个新 shell ——
# zsh 会把 $0 设成被 source 的脚本名（bash 不会），于是 source 完直接被 exec 掉，
# 后面的命令全部不执行。这个坑实测撞到过，故整段删除。
#
# 把两个环境都钉在仓库内：
#   Rust   —— 工具链版本由 rust-toolchain.toml 钉死；cargo 的家与构建缓存都在 构建环境/ 下
#   Python —— 仓库内 venv（不带 pip，site-packages 空 ⇒ 只用标准库）
# 一切产物落在 构建环境/ 下，不往 ~/.cargo、~/.rustup、~/.local、/tmp 乱飞。
#
# 注 1：变量名用 ASCII —— sh/bash 不认中文变量名（工具链强制，同 Cargo 包名）。
# 注 2：本入口**只设环境，不做闸门** —— 要自检请显式跑 构建环境/自检.sh。
#       原因：闸门放在入口会在别人半成品时把所有人都卡住。
# 注 3：**不许用 $0 推仓根** —— 被 source 时 $0 是 shell 名不是脚本路径（踩过）。

# 仓根解析：优先「当前目录就是仓根」，否则用脚本路径（直接执行时 $0 可用）。
ROOT=""
if [ -f "rust-toolchain.toml" ] && [ -d "构建环境" ]; then
  ROOT="$(pwd)"
elif [ -n "$0" ] && [ -f "$0" ]; then
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
if [ -z "$ROOT" ] || [ ! -f "$ROOT/rust-toolchain.toml" ]; then
  echo "进入.sh：定位不到仓根。" >&2
  echo "  请在仓库根执行：. 构建环境/进入.sh" >&2
  return 1 2>/dev/null || exit 1
fi

export CARGO_HOME="$ROOT/构建环境/cargo"
export CARGO_TARGET_DIR="$ROOT/构建环境/构建缓存"
export RUSTUP_TOOLCHAIN="$(sed -n 's/^channel *= *"\(.*\)"/\1/p' "$ROOT/rust-toolchain.toml")"
export CARGO_NET_OFFLINE=true
# ★ 解释器唯一化（3.14 · 唯一一份 · 无回落）：venv **只住主仓** —— 腿（linked 工作树）里
#   没有 `构建环境/python`（`并行工作树.sh` 不再为腿建），一律用主仓那份；找不到就是环境不成立。
#   主仓由 **git** 解析（linked 工作树的 common dir 就是主仓 `.git`），不手工拼 gitdir。
MAIN_ROOT="$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$ROOT/.git")")"
export VIRTUAL_ENV="$MAIN_ROOT/构建环境/python"
export PATH="$VIRTUAL_ENV/bin:$PATH"
unset PYTHONHOME

echo "仓根        : $ROOT"
echo "Rust        : $RUSTUP_TOOLCHAIN（由 rust-toolchain.toml 钉死）"
echo "cargo 家    : $CARGO_HOME"
echo "构建缓存    : $CARGO_TARGET_DIR"
if [ -x "$VIRTUAL_ENV/bin/python" ]; then
  echo "Python      : $("$VIRTUAL_ENV/bin/python" -c 'import sys;print(sys.version.split()[0])')（$VIRTUAL_ENV）"
else
  echo "Python      : venv 不存在（唯一那份住主仓：$VIRTUAL_ENV）"
fi
echo "离线构建    : $CARGO_NET_OFFLINE"
echo
echo "（入口只设环境，不做闸门。要自检请显式跑： 构建环境/自检.sh）"
