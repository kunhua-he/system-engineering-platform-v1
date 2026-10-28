#!/bin/sh
# 开发网关守护 —— 固定开发端口 43110（= 契约声明/常量表.json 的 接口端口）上的常驻壳。
# launchd 版 plist 在 ~/Library/LaunchAgents/com.huashi.v1-gateway-dev.plist：登录时系统自动加载；
# 在 Hermes 网关进程树里 launchctl 被拦截，故这里用本壳保活（端口有人监听就不重复起）。
# 扩展装载由网关自身完成：启动装配末尾跑「启动即装载」（幂等），本壳不再发 curl 补装载 ——
# **壳只管崩溃重拉**，不写第二套装载腿、也不轮询就绪。
# ★ 变量名必须 ASCII：macOS 自带 bash 3.2 不认中文标识符 ⇒ `${中文名:-默认}` 在**运行期**报
#   `bad substitution`（每行一条、整壳起不来、网关无人保活）。函数名同样用 ASCII。
#   **可覆盖环境变量也算在内** —— `V1_RUN_ROOT` / `V1_REPO_ROOT` / `V1_GATEWAY_LOG` /
#   `V1_GATEWAY_PORT` / `V1_GUARD_SELFTEST` 这五个的名字同样是变量名，写成中文一样炸。
# ★ `sh -n` 只查语法，**查不出**这种运行期 `bad substitution`（实测：坏名前 `sh -n` 退 0、真跑退 1）
#   ⇒ 改完必须**真跑**自检支：`python3 构建装配/上线切换/网关守护自检.py`
#   （判据 71 在一键验证里也真跑它 —— 改了壳不跑就红）。
#
# ★ 本件是**唯一源**：部署副本在 `<运行数据根>/运行/网关守护.sh`（起网关时按本件抄一份），
#   两处内容应逐字一致；改界（阈值）只改本件，再抄过去。
#
# ★ 日志轮转（size-based）：守护壳的输出是**只增**的（每次崩溃重拉还会再写一段），故每写一行前
#   先在 `rotate_log` 里量一次大小：≥ 5 MiB 就 `mv` 成 `.1`（**只保留一份**），随后从空件继续追加。
#   只留一份的道理与运行数据收敛同源：留多了只是把一个「只增不减」换成几个。这里刻意不引入
#   `curl` / 轮询 / 定时器 —— 壳的职责只有「崩了拉起来」与「日志别撑爆盘」两件。

# 部署位置可覆盖（反证要在临时目录里跑同一份壳，不碰真日志）：覆盖值是**完整路径**。
RUNDIR="${V1_RUN_ROOT:-/Users/hekunhua/Library/Application Support/系统工程平台V1/运行}"
REPO="${V1_REPO_ROOT:-/Users/hekunhua/Documents/Agent/PHP/系统工程平台V1}"
LOG="${V1_GATEWAY_LOG:-/tmp/网关-dev.log}"
PORT="${V1_GATEWAY_PORT:-43110}"
# 收 TERM / INT 就干净退出（常驻壳的正常退出路；不是「一条命令完整运行」那种入口）。
trap 'exit 0' TERM INT
# 轮转阈值：5 MiB（字节）。到界就转，不等它撑爆。
LOG_MAX_BYTES=5242880

rotate_log() {
  # $1 = 日志件路径。≥ LOG_MAX_BYTES ⇒ 覆盖那份 `.1`（`mv -f`：旧的一份不留）。
  [ -f "$1" ] || return 0
  size=$(wc -c < "$1" 2>/dev/null | tr -d ' ')
  [ -n "$size" ] || return 0
  if [ "$size" -ge "$LOG_MAX_BYTES" ]; then
    mv -f "$1" "$1.1"
  fi
}

guard() {
  cd "$REPO" || exit 1
  while :; do
    if /usr/sbin/lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      sleep 30
      continue
    fi
    rotate_log "$LOG"
    echo "=== $(date '+%F %T') start gateway on $PORT" >> "$LOG"
    "$RUNDIR/启动网关" \
      --声明根 扩展装载/扩展根声明.json \
      --后缀表 扩展装载/后缀表.json \
      --静态根 前端呈现/网页应用 \
      --工具根 . \
      --跨进程配置 "$RUNDIR/跨进程配置.json" \
      --端口 "$PORT" >> "$LOG" 2>&1
    echo "=== $(date '+%F %T') gateway exited ($?), relaunch in 2s" >> "$LOG"
    sleep 2
  done
}

# 自检开关：`V1_GUARD_SELFTEST=1` ⇒ 只加载定义、不进保活循环（反证要单独测 `rotate_log` 那一支，
# 不能真起网关，更不能把真正的 `/tmp` 日志动掉）。
if [ "${V1_GUARD_SELFTEST:-}" != "1" ]; then
  guard
fi
