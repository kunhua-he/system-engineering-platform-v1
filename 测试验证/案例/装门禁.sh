#!/bin/sh
# 装门禁 —— 把端到端主门禁装进 `.git/hooks/pre-commit`。
#
# 为什么版本化的件是**这个安装脚本**而不是钩子本身：`.git/hooks/` 不进版本库，
# 别人 clone 下来拿不到钩子。所以能版本化的只有「怎么装」这件事。
#
# 怎么跑（在仓库根）：
#
#     sh 测试验证/案例/装门禁.sh
#
# 幂等：重复跑不叠加 —— 认标记 `装门禁标记: v1-case-runner`，是自家钩子就整体重写，
# 不是自家钩子就**拒绝覆盖**（别人的钩子不许被我们踩掉）。
#
# 钩子只判「拒或不拒」，**自身绝不 git commit**（pre-commit 里再提交会递归）。
#
# ── 多了一步：认领机制的**提交闸**（2026-09-27 加，见 开发工具/认领机制/说明.md §六） ──
#
# 它比对「将要提交的路径」与「账本里本腿的认领集」，把不在集里的报出来 ——
# 这是 `说明.md` §五 说的「真正的强制点在提交」那处落点。
#
# ★ **默认只报不拦（警告模式）**：现在没人在用认领机制（账本实测为空），
#   硬拦会挡住**所有**提交，把闸变成路障。硬拦是**显式开关**：
#   环境变量 `CLAIM_GATE=硬拦`（别名 block/1/true）。
#   警告/硬拦的**模式定义只有一处** —— 在 `认领机制.py::gate_mode`；
#   本钩子只写 `exit $CODE`，**不自行判模式**（两处各判一次 = 两处定义同一件事）。
#
# ★ 认领机制不在（别人 clone 下来 / 还没落这套）⇒ **跳过，不拒**：
#   闸本来就是协作式的（`说明.md` §五），缺件时拒提交等于把闸变成路障。
#
# ★ 变量名一律 ASCII —— **实测**：macOS 的 `/bin/sh` 是 bash 3.2，**不认中文变量名**
#   （`仓根=$(...)` 会被当成一条命令，报 `No such file or directory`）。
#   这是工具链强制，与 `构建环境/进入.sh` 的注 1 同一条理由。
#   （第二坑：`$VAR` 后面**紧跟中文**会被当成变量名的一部分而输出乱码 ⇒ 一律写 `${VAR}`。）

set -u

# ── 五秒硬顶：壳自量自门禁（阈值唯一落点在 `构建装配/门禁/常量.py`，口径见 `构建装配/门禁/壳.py`）──
#
# 本件是**纯 shell**，没有 Python 业务包可挂壳 ⇒ 用两条 `python3 -c` 自量（本脚本本来就要 python3）。
# 起表点必须在**第一件耗时的事之前**；用 `trap … EXIT` 覆盖**每一条** `exit` 路径
# （本脚本有多处 `exit 1`：定位不到仓根 / 拒绝覆盖别人的钩子 / 共享钩子没显式同意 …）。
#
# ★ 门禁是**诊断**，不许改命令本体算出来的码：python 侧只用退出码 3 报「超顶」，
#   别的非 0（例如 import 不到共享件）一律**保留原码** —— 否则门禁自身坏了会把一次
#   成功的安装变成失败（那是假红，比没有门禁更坏）。
# ★ 函数名与变量名一律 **ASCII**：bash 3.2 连函数名都不认非 ASCII
#   （实测：`门禁报告() { … }` ⇒ `` `门禁报告': not a valid identifier ``，整个脚本退出码 2）。
START=$(python3 -c 'import time;print(time.monotonic())')

gate_report() {
  ORIG_CODE=$?
  python3 - "$START" "$ORIG_CODE" "$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)" <<'PY'
import sys, time
sys.path.insert(0, sys.argv[3])
from 构建装配.门禁 import 硬顶毫秒, 注入人为慢
余量毫秒 = 200   # 壳量不到「解释器启动 + 打印 + 进程退出」那一段，200 是它的上界（见 构建装配/门禁/壳.py）
注入毫秒 = 注入人为慢()   # 反向样本：复用共享那一份（`V1_CMD_SLOW_MS=<毫秒>`），本件不另写一套
墙钟毫秒 = int((time.monotonic() - float(sys.argv[1])) * 1000)
阈值毫秒 = 硬顶毫秒 - 余量毫秒
print("─" * 78, file=sys.stderr)
print("命令墙钟（壳自量）%d ms · 阈值 %d ms（硬顶 %d − 尾巴余量 %d）· 人为慢注入 %d ms"
      % (墙钟毫秒, 阈值毫秒, 硬顶毫秒, 余量毫秒, 注入毫秒), file=sys.stderr)
if 墙钟毫秒 > 阈值毫秒:
    print("✗ 超顶：完整墙钟 %d ms > %d ms —— 五秒硬顶无例外（裁决 §一）" % (墙钟毫秒, 阈值毫秒), file=sys.stderr)
    sys.exit(3)
print("✓ 在硬顶内", file=sys.stderr)
PY
  GATE_CODE=$?
  if [ "${GATE_CODE}" -eq 3 ]; then exit 1; fi
  exit "${ORIG_CODE}"
}
trap gate_report EXIT

MARK='装门禁标记: v1-case-runner'

# ── 定位仓根：优先「当前目录就是仓根」，否则用脚本路径 ──
ROOT=''
if [ -f rust-toolchain.toml ] && [ -d 构建环境 ]; then
  ROOT=$(pwd)
elif [ -n "${0:-}" ] && [ -f "$0" ]; then
  ROOT=$(cd "$(dirname "$0")/../.." && pwd)
fi
if [ -z "$ROOT" ] || [ ! -f "$ROOT/rust-toolchain.toml" ]; then
  echo "装门禁：定位不到仓根。请在仓库根执行：sh 测试验证/案例/装门禁.sh" >&2
  exit 1
fi

# ── 钩子落点：交给 git 自身算，**不写死** `$ROOT/.git/hooks` ──
#
# ★ 实测（撞到，不是推测）：在**工作树**里跑本脚本，写死的 `$ROOT/.git/hooks`
#   会直接报「本仓不是一个 git 工作区？」（**假红**）——因为工作树里的 `.git` 是个**文件**
#   （内容 `gitdir: …/工作树名`），不是目录。机制一（一腿一工作树）就建在这种树上。
# ★ `--git-path hooks` 可能给**相对**路径（主仓里给 `.git/hooks`）⇒ 按 ROOT 解析。
HOOKS_REL=''
HOOKS_REL=$(git -C "$ROOT" rev-parse --git-path hooks 2>/dev/null) || HOOKS_REL=''
case "$HOOKS_REL" in
  /*) HOOKS_DIR="$HOOKS_REL" ;;
  '') HOOKS_DIR='' ;;
  *)  HOOKS_DIR="$ROOT/$HOOKS_REL" ;;
esac
if [ -z "$HOOKS_DIR" ] || [ ! -d "$HOOKS_DIR" ]; then
  echo "装门禁：定位不到钩子目录（git rev-parse --git-path hooks 给的是 '${HOOKS_REL:-（空）}'）" >&2
  exit 1
fi
HOOK="$HOOKS_DIR/pre-commit"

# ★ 钩子目录**不在本仓内** ⇒ 这是「一腿一工作树」的情形：git 把钩子放在**公共** git 目录里，
#   那一份是**所有工作树共享**的。在这里装 = 给**全仓每一棵树**（含主树）装门禁 ——
#   这不该由一条腿悄悄做 ⇒ 必须显式说要装（`GATE_INSTALL_SHARED=yes`）。
case "$HOOKS_DIR" in
  "$ROOT"/*) : ;;
  *)
    if [ "${GATE_INSTALL_SHARED:-}" != 'yes' ]; then
      echo "装门禁：钩子目录不在本仓内 —— $HOOKS_DIR" >&2
      echo "        那份钩子是**所有工作树共享**的：在这里装 = 给全仓每一棵树（含主树）都装。" >&2
      echo "        要装请显式：GATE_INSTALL_SHARED=yes sh 测试验证/案例/装门禁.sh" >&2
      exit 1
    fi
    echo "装门禁：注意 —— 钩子是**共享**的（${HOOKS_DIR}），本次安装对**所有工作树**生效。" >&2
    ;;
esac

# ── 幂等与不踩别人 ──
if [ -f "$HOOK" ] && ! grep -qF "$MARK" "$HOOK"; then
  echo "装门禁：$HOOK 已经存在且不是本门禁装的 —— 拒绝覆盖。" >&2
  echo "        要装就先自身处置那个钩子（本脚本不替你做这个决定）。" >&2
  exit 1
fi

TMP="$HOOK.new"
cat > "$TMP" <<'HOOK_BODY'
#!/bin/sh
# 装门禁标记: v1-case-runner
#
# 端到端主门禁（形状见 测试验证/案例/形状.md）。
# **只判「拒或不拒」，绝不 git commit。**
#
# 五步：
#   ① 读 `git rev-parse HEAD`，与回执最新一行的 `提交哈希` 比 —— 不一致就当场说清
#      「最新那份回执不是这个提交的」，让「回执是旧的」与「代码坏了」分得开。
#   ② 跑**全部**案例（跑案例的程序自身把回执追加进 运行回执.jsonl）。
#   ③ 复核新回执的哈希 == HEAD，再按退出码决定拒或不拒。
#   ④ 认领机制的『提交闸』（`开发工具/认领机制/认领机制.py 提交闸`）——
#      **默认只报不拦**；要它拒就设 `CLAIM_GATE=硬拦`。
#   ⑤ **不暂存回执** —— 回执不进版本库（见 `.gitignore` 里那段）。
#
# **回执的 `提交哈希` 是「跑那一刻的 HEAD」**（`测试验证/案例/形状.md` §四：回执绑提交哈希，
# 否则「回执是旧的」与「代码坏了」不可区分 —— `判据的可信性.md` §三 的假绿来源之一）。
# 钩子跑在**提交之前** ⇒ 那一刻的 HEAD = **本次提交的父提交**（回执不可能写自身的提交哈希 ——
# 自指）。所以这份回执验的是**将要提交的那棵树**（工作区），而它写的哈希是**父**。
# **读法**：哈希 X ＋「跑于 pre-commit」⇒ 验的是 X 的**子**提交的内容。
#
# 变量名一律 ASCII：macOS 的 /bin/sh 是 bash 3.2，不认中文变量名。

ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$ROOT" || exit 1

HEAD_SHA=$(git rev-parse HEAD) || exit 1
RECEIPT='测试验证/案例/运行回执.jsonl'

OLD=''
if [ -f "$RECEIPT" ]; then
  OLD=$(tail -n 1 "$RECEIPT" | sed -n 's/.*"提交哈希":"\([0-9a-f]\{40\}\)".*/\1/p')
fi
if [ "$OLD" != "$HEAD_SHA" ]; then
  echo "门禁：回执最新一行说的是 ${OLD:-（没有回执）}，不是本提交 $HEAD_SHA ⇒ 本次必须重跑（旧回执不算数）"
fi

if [ ! -f 构建环境/进入.sh ]; then
  echo "门禁：找不到 构建环境/进入.sh ⇒ 拒提交" >&2
  exit 1
fi
. ./构建环境/进入.sh >/dev/null 2>&1 || { echo "门禁：进不了构建环境 ⇒ 拒提交" >&2; exit 1; }

cargo run --quiet --locked -p v1-case-runner
CODE=$?
if [ "$CODE" -ne 0 ]; then
  case "$CODE" in
    1) echo "门禁：有案例失败 ⇒ 拒提交（逐条读数见 测试验证/案例/运行回执.jsonl）" >&2 ;;
    2) echo "门禁：工具错误（案例文件坏了 / 语料读不到 / 接缝不对）⇒ 拒提交，且**没写回执**" >&2 ;;
    *) echo "门禁：跑案例的程序退出码 $CODE ⇒ 拒提交" >&2 ;;
  esac
  exit 1
fi

# 复核：新写出的回执必须绑在 HEAD 上（否则是回执写坏了 = 判据坏了 ⇒ 拒提交）
NEW=$(tail -n 1 "$RECEIPT" | sed -n 's/.*"提交哈希":"\([0-9a-f]\{40\}\)".*/\1/p')
if [ "$NEW" != "$HEAD_SHA" ]; then
  echo "门禁：新回执的提交哈希是 ${NEW:-（读不出）}，不是 $HEAD_SHA ⇒ 回执写坏了 ⇒ 拒提交" >&2
  exit 1
fi

# ④ 认领机制的提交闸 —— **默认只报不拦**。
#
#    退出码**只由脚本按模式决定**（见上面那段注）：警告模式一律 0，故这里
#    在默认状态下**永远不会拒**。要拒就把 CLAIM_GATE 设成硬拦。
GATE_PY="$ROOT/开发工具/认领机制/认领机制.py"
if [ -f "$GATE_PY" ]; then
  GATE_CODE=0
  python3 "$GATE_PY" 提交闸 || GATE_CODE=$?
  if [ "$GATE_CODE" -ne 0 ]; then
    # ★ 变量必须写成 ${GATE_CODE} —— **实测**：`$GATE_CODE` 后面紧跟中文（`）`）会被
    #   bash 3.2 当成变量名的一部分，输出乱码（`退出码 ��⇒`）。本仓第三次踩同一个坑
    #   （前两次见 开发工具/并行工作树.sh 与 构建环境/进入.sh 的注）。
    echo "门禁：认领机制的提交闸拒了本次提交（退出码 ${GATE_CODE}）⇒ 拒提交" >&2
    echo "      逐条读取：python3 开发工具/认领机制/认领机制.py 提交闸" >&2
    exit 1
  fi
else
  echo "门禁：没有 $GATE_PY ⇒ 跳过提交闸（不拒 —— 闸是协作式的，缺件时拒提交等于把闸变成路障）"
fi

# ⑤ **不暂存回执** —— 它不进版本库（`.gitignore` 里那段有裁决与实测）。
#    ★ 保证不变：钩子每次提交都跑案例、失败即拒 ⇒「提交存在 ⇒ 案例当时过了」仍成立；
#      回执只是**读数**，留在本机给人看。
#    ★ 实测后果（2026-09-27，这条就是改的理由）：回执是**只增日志**，而一开工一工作树时
#      每条支线提交都会往同一个件追加一行 ⇒ N 条支线合并就是 N 次冲突，冲突内容毫无信息量。

echo "门禁：案例全过，回执绑在 $HEAD_SHA 上（父提交）· 回执只落本机，不进版本库"
exit 0
HOOK_BODY

mv "$TMP" "$HOOK"
chmod +x "$HOOK"

echo "装门禁：已装到 $HOOK"
echo "        行为：先比 HEAD 与回执里的提交哈希，再跑全部案例，任一失败即拒提交；"
echo "              跑案例的程序把读数追加进 测试验证/案例/运行回执.jsonl，"
echo "              该回执**不进版本库**（只落本机 —— 它是只增日志，进版本库会让每条支线"
echo "              都改同一个件，合并必冲突；见 .gitignore 里那段）。"
echo "              回执里的提交哈希是**跑那一刻的 HEAD**（= 本次提交的父提交）。"
echo "        另加一步「认领机制的提交闸」：比对将要提交的路径与账本里本腿的认领集。"
echo "              ★ **默认只报不拦（警告）** —— 现在没人在用认领机制，硬拦会挡掉所有提交。"
echo "              要它真拒：CLAIM_GATE=硬拦（别名 block/1/true），见 开发工具/认领机制/说明.md §六。"
echo "              （钩子只写 exit \$CODE，模式只由 认领机制.py::gate_mode 判 —— 不两处定义。）"
echo "        卸载：删掉那个文件即可（本脚本没有留任何别的东西）。"
