#!/bin/sh
# 并行工作树 —— 一腿一工作树，消灭三条争用（见 项目文档/设计文档/并行开发与工作区.md）
#
#   sh 开发工具/并行工作树.sh 新建 <腿名>
#   sh 开发工具/并行工作树.sh 列出
#   sh 开发工具/并行工作树.sh 移除 <腿名>
#   sh 开发工具/并行工作树.sh 自检
#
# 为什么需要它（实测）：
#   ① **共享可变工作区**（代价最大）：所有腿写同一个工作区 ⇒ 任一条腿的半成品让**全员**红，
#      且任一条腿在写就**不能提交**。实测：主树一度因两处错误 ⇒ 全仓 12 个 crate 一起红；
#      10 路成果一度全压在工作区没进版本库。**它同时废掉「全仓绿」与「随时可提交」两句话。**
#   ② 文件争用：多腿写同一个文件 ⇒ **静默覆盖**（不报错，事后才发现丢了别人的改动）。实测 4 例。
#   ③ 构建锁争用：cargo 对目标目录加锁是真的（日志有 `Blocking waiting for file lock`），
#      但**代价只有 0.04 秒**（冷构建 0.32 秒，同 target-dir 并发 0.36 秒）⇒ 可忽略。
#      ★ 本条原写「『十几路在抢』的真因是这个锁」——**那是没量就下的结论，已被实测推翻**
#        （见 `项目文档/设计文档/并行开发与工作区.md` §一：机制存在 ≠ 机制是瓶颈）。
#        保留机制一的隔离，是因为它顺手把这条也归零，且防将来 crate 变大后回潮，不是因为它现在贵。
#
# 一腿一工作树之后：共享可变状态归零 · 文件争用归零 · 构建锁争用归零
# ⇒ **共享工作区永远绿**（半成品红只在该腿自身的树里）
#
# ★ 用法陷阱（实测）：每条腿必须 source **自身那棵树里**的 `构建环境/进入.sh`。
#   若在工作树里 source 了主树的，两条腿又会共用主树的 target 目录（`ROOT` 决定落点）。
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
#   ⇒ 假红假绿都判不准。给每个扫描面加跳过项是临时凑合（今天两个扫描面、明天第三个忘了又中）；
#   落仓外则是**结构性**修法：仓库里不再有「自身的副本」，任何遍历都看不见它。
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
# ★ 解释器唯一化（3.14 · 唯一一份 · 无回落）：venv 只住主仓（腿里不建）；主仓由 git 解析。
ROOT="$(dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$ROOT/.git")")"
cd "$ROOT"

# ── 壳自门禁（五秒硬顶）────────────────────────────────────────────────────
# 依据：`项目文档/决策记录/2026-09-27_所有运行五秒硬顶.md` §一/§六 —— 一条命令完整跑完
#（进程启动到退出）的墙钟 ≤ 5000 ms，取 p100，超过即 bug、无例外。
# 阈值**不在这里写第二份**：从唯一落点 `构建装配/门禁/` 取（与判据 ⑱ 同源）。
# 反向样本（跑绿即删）：`V1_CMD_SLOW_MS=5200 sh 开发工具/并行工作树.sh 自检` ⇒ 必红。
# ★ 变量名 / 函数名一律 ASCII —— bash 3.2 不认非 ASCII 标识符（见本文件顶部三条实测）。
# ★ 解释器唯一化（3.14 · 唯一一份 · 无回落）：裸 `python3` 会落到系统 3.9.6（口径：所有 py
#   命令都用 3.14，禁第二个版本）。venv 只住仓根 ⇒ 直接取，不在即拒。
PY="$ROOT/构建环境/python/bin/python"
if [ ! -x "$PY" ]; then
  echo "并行工作树：仓内解释器不在：$PY（唯一允许的 3.14 venv）⇒ 拒" >&2
  exit 1
fi
# ★ 解释器唯一化：`V1_PY` 是**唯一来源**，随本脚本起的子进程一路继承。
export V1_PY="$PY"
START=$("$PY" -c 'import time;print(time.monotonic())')
gate_report() {
  ORIG_CODE=$?
  GATE_CODE=0
  # ★ 必须写成 `... || GATE_CODE=$?`：本脚本有 `set -e`（`装门禁.sh` 没有），
  #   直接 `"$PY" ...; GATE_CODE=$?` 在超顶时会被 `set -e` 当场带走 ——
  #   下面那行映射变成死代码，退出码停在 3（实测）。这样写才是「接住码再映射」。
  "$PY" - "$START" "$ORIG_CODE" "$ROOT" <<'PY' || GATE_CODE=$?
import sys, time
sys.path.insert(0, sys.argv[3])
from 构建装配.门禁 import 硬顶毫秒, 注入人为慢
余量毫秒 = 200
注入毫秒 = 注入人为慢()
墙钟毫秒 = int((time.monotonic() - float(sys.argv[1])) * 1000)
阈值毫秒 = 硬顶毫秒 - 余量毫秒
print("─" * 78)
print("命令墙钟（壳自量）%d ms · 阈值 %d ms（硬顶 %d − 尾巴余量 %d）· 人为慢注入 %d ms"
      % (墙钟毫秒, 阈值毫秒, 硬顶毫秒, 余量毫秒, 注入毫秒))
if 墙钟毫秒 > 阈值毫秒:
    print("✗ 超顶。本件是开发工具，慢的一档是 `git worktree` 与 `du`（规模决定）——"
          "先量是哪一档慢（`列出` 的 `du -sh` 会随各腿构建缓存长大），再决定缓存或分片，别砍判据。",
          file=sys.stderr)
    sys.exit(3)
print("✓ 在硬顶内")
PY
  if [ "${GATE_CODE}" -eq 3 ]; then exit 1; fi
  exit "${ORIG_CODE}"
}
trap gate_report EXIT

# 仓外：与仓库同级。改这一行 = 改「工作树落在哪」，全脚本只有这一处定义。
TREES="../系统工程平台V1.工作树"

usage() {
  cat <<'USAGE'
并行工作树 —— 一腿一工作树

  sh 开发工具/并行工作树.sh 新建 <腿名>    建一条腿的工作树（独立检出 + 独立构建缓存）
  sh 开发工具/并行工作树.sh 列出           列出所有工作树与各自的构建缓存占用
  sh 开发工具/并行工作树.sh 移除 <腿名> [强制]
                                           移除一条腿的工作树（脏树拒；显式「强制」才丢未提交改动）
  sh 开发工具/并行工作树.sh 路径 <腿名>    打印该腿工作树的绝对路径（不建、不删）
  sh 开发工具/并行工作树.sh 自检           检查本机制是否真的隔离（不靠看，靠量）

腿名用 ASCII（分支名要能进 git ref）：字母 · 数字 · 短横线。
USAGE
}

# 每条腿一个构建缓存目录：.cargo/config.toml 里 target-dir 是相对路径，
# 所以在工作树里自然解析到「该工作树自身的 构建环境/构建缓存」——不需要额外配置。
mk_cache() {
  leg="$1"
  tree="$TREES/$leg"
  if [ ! -d "$tree" ]; then echo "工作树不存在：$tree" >&2; exit 1; fi
  mkdir -p "$tree/构建环境/构建缓存"
  # Python venv：**腿里不建** —— 全仓只有主仓那一份 3.14 venv（`$ROOT/构建环境/python`）：
  # 解释器唯一、无回落、无第二个版本（口径：所有 py 命令都用 3.14）。腿里那份历史误建已清。
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
    FORCE="${3:-}"
    if [ -z "$leg" ]; then echo "缺腿名。" >&2; exit 1; fi
    # ★ 脏就拒（2026-10-05 修 · 审计 B-6）：原先无条件 `--force` ⇒ 未提交的改动被静默删、无提示。
    #   `git status --porcelain` 尊重 .gitignore（构建缓存 / venv / .codegraph 不算脏）。
    # ★ 变量名一律 ASCII —— bash 3.2 不认非 ASCII 变量名（见本文件顶部三条实测）。
    DIRTY=$(git -C "$TREES/$leg" status --porcelain 2>/dev/null) || DIRTY=''
    if [ -n "$DIRTY" ]; then
      NDIRTY=$(printf '%s\n' "$DIRTY" | grep -c . || true)
      if [ "$FORCE" != "强制" ] && [ "$FORCE" != "--强制" ]; then
        echo "移除：$TREES/$leg 有 ${NDIRTY} 件未提交的改动 ⇒ **拒绝移除**（这些改动会丢）。" >&2
        echo "      先提交 / 用 功能=3 释放；确认要丢就显式：sh 开发工具/并行工作树.sh 移除 $leg 强制" >&2
        printf '%s\n' "$DIRTY" >&2
        exit 1
      fi
      echo "移除：$TREES/$leg 有 ${NDIRTY} 件未提交的改动 —— **显式强制**，连同未提交改动一起删。" >&2
    fi
    if [ "$FORCE" = "强制" ] || [ "$FORCE" = "--强制" ]; then
      git worktree remove --force "$TREES/$leg"
    else
      git worktree remove "$TREES/$leg"
    fi
    echo "已移除 $TREES/${leg}（分支 腿/$leg 保留，便于查它的提交）"
    ;;
  路径)
    leg="${2:-}"
    if [ -z "$leg" ]; then echo "缺腿名。" >&2; exit 1; fi
    # 打印该腿工作树的绝对路径（供 开工.py 在**建树之前**占住账本行 —— 目录名的唯一定义仍在本件）。
    mkdir -p "$TREES"
    echo "$(cd "$TREES" && pwd)/$leg"
    ;;
  自检)
    # 判据：**不靠看，靠量**——两条腿的构建缓存目录必须是两个不同的物理目录。
    echo "① 工作树清单"
    git worktree list
    echo
    echo "② target-dir 是不是「每条腿各自一份」"
    echo "   .cargo/config.toml 里 target-dir = $(sed -n 's/^target-dir *= *//p' .cargo/config.toml)"
    echo "   它是**相对路径** ⇒ 在每个工作树里自然解析到该工作树自身的目录（不需额外配置）"
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
