#!/bin/sh
# 构建全链：一套走到底，中间不许漏步。
#
# 为什么要有这个入口：这几步原先靠手敲命令串，实测漏过两次 ——
# 一次漏了「能力声明对齐」，json 与源码漂移了两处默认值；一次漏了「扩展指纹」，
# 门禁 ㉟ 直接失配。次序也不能换：对齐必须早于指纹（指纹按 json 内容算），
# 指纹必须早于落库（库里存的是指纹），构建制品读的是落库后的结果。
#
# 用法：
#   bash 构建装配/全链.sh            只构建，出制品标识
#   bash 构建装配/全链.sh --装载     构建完直接装载到临时端口验收
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 1
# 进入.sh 里有未定义变量的引用，`set -u` 下 source 会直接把脚本打停 —— 先在宽松模式里跑完它。
set +u
. "$ROOT/构建环境/进入.sh" >/dev/null 2>&1
set -u

LOG=/tmp/构建全链.log
: > "$LOG"

step() {
  printf '%-24s' "$1"
  shift
  if "$@" >> "$LOG" 2>&1; then
    echo "ok"
  else
    echo "失败（看 $LOG）"
    tail -20 "$LOG"
    exit 1
  fi
}

step "① 能力声明对齐"   python3 构建装配/形态装配/能力声明对齐.py
step "② 生成声明"       python3 构建装配/形态装配/生成声明.py
step "③ 扩展指纹"       python3 构建装配/形态装配/扩展指纹.py
step "④ 信息核心落库"   python3 开发工具/信息核心/信息核心.py 落库
step "⑤ 预构建"         python3 构建装配/上线切换/构建制品.py --预构建
step "⑥ 构建制品"       python3 构建装配/上线切换/构建制品.py

ARTIFACT=$(grep -o '[0-9a-f]\{12\}-[0-9a-f]\{16\}' "$LOG" | tail -1)
if [ -z "$ARTIFACT" ]; then
  echo "没解析到制品标识，看 $LOG"
  exit 1
fi
echo "制品 = $ARTIFACT"

if [ "${1:-}" = "--装载" ]; then
  # 装载口偶发第一次起不来（约十次一遇，日志只到装载清单），重试三次。
  i=0
  while [ $i -lt 3 ]; do
    i=$((i + 1))
    R=$(bash 构建装配/上线切换/装载.sh "$ARTIFACT" 2>&1 | grep -E "实例 pid|没起来" | head -1)
    echo "装$i: $R"
    case "$R" in
      *pid*) break ;;
    esac
  done
fi
