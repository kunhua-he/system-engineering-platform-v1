#!/bin/sh
# 并行工作树 —— 一腿一工作树，消灭三条争用（见 项目文档/设计文档/并行开发与工作区.md）
#
#   sh 开发工具/并行工作树.sh 新建 <腿名>
#   sh 开发工具/并行工作树.sh 列出
#   sh 开发工具/并行工作树.sh 移除 <腿名>
#   sh 开发工具/并行工作树.sh 自检
#
# 为什么需要它（实测）：
#   ① 文件争用：多腿共享一个可变工作区 ⇒ 同一文件被两条腿写（本会话实测 4 例）
#   ② 构建锁争用：cargo 对**目标目录**加锁 ⇒ 同一 target-dir 下多次构建**串行**
#      ——「十几路在抢」的真因是这个锁，不是核不够
#   ③ 提交点争用：工作区是一个共享可变状态 ⇒ 任一条腿在写就不能提交
#
# 一腿一工作树之后：文件争用归零 · 构建锁争用归零 · **共享工作区永远绿**（半成品红只在该腿自己的树里）
#
# ★ 本文件里的**标识符一律 ASCII**（变量名 · 函数名 · heredoc 定界符）。
#   sh/bash 不认非 ASCII 标识符 —— 实测三种变体：① 函数名 `用法() {` 报 `not a valid identifier`
#   ② 变量赋值 `腿=x` 报 `command not found` ③ **变量展开后紧跟中文字符**会被当成变量名的一部分
#   （`"$leg（分支"` 展开成乱码），必须写 `"${leg}（分支"`。
#   中文只出现在**注释与输出串**里。这三条我都在这个脚本里先后撞到过。
#
# ★★ 工作树落在**仓外**（与仓库同级：`../系统工程平台V1.工作树/`），这是刻意的，不是随手。
#   放仓内的代价实测过：`git worktree add .工作树/x` 之后，**全仓扫描会把那份检出当成真命中**
#   ——验证器常量表检查的 13 条命中里 8 条来自 `.工作树/trial1/**` 那份收口前的旧拷贝，
#   里面还有我从没写过的旧值（`单项超时毫秒: u64 = 30_000`）。**陈旧副本长得跟真的一样**
#   ⇒ 假红假绿都判不准。给每个扫描面加跳过项是打补丁（今天两个扫描面、明天第三个忘了又中）；
#   落仓外则是**结构性**修法：仓库里不再有「自己的副本」，任何遍历都看不见它。
#   代价：与仓库同级多一个目录（不在版本库内，故无需 .gitignore，也无需登记进 README 目录树）。

set -e

# ── 仓根解析：优先「当前目录就是仓根」，否则用脚本路径（直接执行时 $0 可用）──
ROOT=""
if [ -f "rust-toolchain.toml" ] && [ -d "构建环境" ]; then
  ROOT="$(pwd)"
elif [ -n "$0" ] && [ -f "$0" ]; then
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
if [ -z "$ROOT" ] || [ ! -f "$ROOT/rust-toolchain.toml" ]; then
  echo "并行工作树：定位不到仓根。" >&2
  echo "  请在仓库根执行，或传绝对路径。" >&2
  exit 1
fi
cd "$ROOT"

# 仓外：与仓库同级。改这一行 = 改「工作树落在哪」，全脚本只有这一处定义。
TREES="../系统工程平台V1.工作树"

usage() {
  cat <<'USAGE'
并行工作树 —— 一腿一工作树

  sh 开发工具/并行工作树.sh 新建 <腿名>    建一条腿的工作树（独立检出 + 独立构建缓存）
  sh 开发工具/并行工作树.sh 列出           列出所有工作树与各自的构建缓存占用
  sh 开发工具/并行工作树.sh 移除 <腿名>    移除一条腿的工作树（先确认它已收工）
  sh 开发工具/并行工作树.sh 自检           检查本机制是否真的隔离（不靠看，靠量）

腿名用 ASCII（分支名要能进 git ref）：字母 · 数字 · 短横线。
USAGE
}

# 每条腿一个构建缓存目录：.cargo/config.toml 里 target-dir 是相对路径，
# 所以在工作树里自然解析到「该工作树自己的 构建环境/构建缓存」——不需要额外配置。
mk_cache() {
  leg="$1"
  tree="$TREES/$leg"
  if [ ! -d "$tree" ]; then echo "工作树不存在：$tree" >&2; exit 1; fi
  mkdir -p "$tree/构建环境/构建缓存"
  # Python venv：gitignore 的产物，工作树里不会带过来。缺了就建一个（不带 pip ⇒ site-packages 空）。
  if [ ! -x "$tree/构建环境/python/bin/python" ]; then
    python3 -m venv --without-pip "$tree/构建环境/python" 2>/dev/null \
      || echo "（提示：venv 没建成，Python 侧的腿请用主树的 构建环境/python）" >&2
  fi
}

case "${1:-}" in
  新建)
    leg="${2:-}"
    if [ -z "$leg" ]; then echo "缺腿名。用法见：sh 开发工具/并行工作树.sh" >&2; exit 1; fi
    case "$leg" in
      *[!A-Za-z0-9-]*) echo "腿名只能用 ASCII 字母 / 数字 / 短横线（分支名要能进 git ref）：$leg" >&2; exit 1 ;;
    esac
    if [ -e "$TREES/$leg" ]; then echo "已存在：$TREES/$leg" >&2; exit 1; fi
    mkdir -p "$TREES"
    git worktree add -b "腿/$leg" "$TREES/$leg"
    mk_cache "$leg"
    echo
    echo "工作树已就绪：$TREES/${leg}（分支 腿/${leg}）"
    echo "（落在仓外 —— 全仓扫描看不见它，见本文件顶部说明）"
    echo "进它、并在里面工作："
    echo "    cd $TREES/$leg && . ./构建环境/进入.sh"
    echo "构建缓存（各腿独立，互不等锁）：$(du -sh "$TREES/$leg/构建环境/构建缓存" 2>/dev/null | cut -f1)"
    ;;
  列出)
    git worktree list
    echo
    echo "各腿构建缓存占用："
    if [ ! -d "$TREES" ]; then echo "  （还没有工作树）"; exit 0; fi
    for d in "$TREES"/*/; do
      [ -d "$d" ] || continue
      printf "  %-28s %s\n" "$(basename "$d")" "$(du -sh "${d}构建环境/构建缓存" 2>/dev/null | cut -f1)"
    done
    echo
    echo "主工作区构建缓存：$(du -sh 构建环境/构建缓存 2>/dev/null | cut -f1)"
    ;;
  移除)
    leg="${2:-}"
    if [ -z "$leg" ]; then echo "缺腿名。" >&2; exit 1; fi
    git worktree remove --force "$TREES/$leg"
    echo "已移除 $TREES/${leg}（分支 腿/$leg 保留，便于查它的提交）"
    ;;
  自检)
    # 判据：**不靠看，靠量**——两条腿的构建缓存目录必须是两个不同的物理目录。
    echo "① 工作树清单"
    git worktree list
    echo
    echo "② target-dir 是不是「每条腿各自一份」"
    echo "   .cargo/config.toml 里 target-dir = $(sed -n 's/^target-dir *= *//p' .cargo/config.toml)"
    echo "   它是**相对路径** ⇒ 在每个工作树里自然解析到该工作树自己的目录（不需额外配置）"
    echo
    echo "③ 实测：两条腿的构建缓存是否真是两个不同的目录（inode 不同即隔离）"
    n=0
    for d in "$TREES"/*/; do
      [ -d "$d" ] || continue
      printf "   %-28s inode=%s\n" "$(basename "$d")" "$(stat -f %i "${d}构建环境/构建缓存" 2>/dev/null || echo 不存在)"
      n=$((n+1))
    done
    printf "   %-28s inode=%s\n" "（主工作区）" "$(stat -f %i 构建环境/构建缓存 2>/dev/null || echo 不存在)"
    if [ "$n" -eq 0 ]; then echo "   （还没有工作树可量；先用「新建」建一条）"; fi
    echo
    echo "④ 磁盘余量（每腿约 403 MB 实测）"
    df -h . | tail -1
    ;;
  ""|-h|--help|帮助)
    usage
    ;;
  *)
    echo "未知动作：$1" >&2
    usage
    exit 1
    ;;
esac
