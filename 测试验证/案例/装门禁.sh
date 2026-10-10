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
    print("✗ 超顶：完整墙钟 %d ms > %d ms —— 硬顶无例外（裁决 §一）" % (墙钟毫秒, 阈值毫秒), file=sys.stderr)
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
HOOK_MERGE="$HOOKS_DIR/pre-merge-commit"

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

# ── 幂等与不踩别人（两个落点都查：pre-commit 与 pre-merge-commit）──
for TARGET in "$HOOK" "$HOOK_MERGE"; do
  if [ -f "$TARGET" ] && ! grep -qF "$MARK" "$TARGET"; then
    echo "装门禁：$TARGET 已经存在且不是本门禁装的 —— 拒绝覆盖。" >&2
    echo "        要装就先自身处置那个钩子（本脚本不替你做这个决定）。" >&2
    exit 1
  fi
done

TMP="$HOOK.new"
cat > "$TMP" <<'HOOK_BODY'
#!/bin/sh
# 装门禁标记: v1-case-runner
#
# 端到端主门禁（形状见 测试验证/案例/形状.md）。
# **只判「拒或不拒」，绝不 git commit。**
#
# ★ 本件同时装成 `pre-commit` 与 `pre-merge-commit`（两个落点同一份体）—— **实测**：`git merge`
#   造合并提交时**只跑 `pre-merge-commit`、不跑 `pre-commit`**（fast-forward 与 `update-ref`
#   更是零钩子）⇒ 只装 `pre-commit` 时，合入主干**根本不过闸**。两个落点都装，合并提交才过闸。
#
# 六步：
#   ① 跑**闸 0**（声明侧 + 实现侧）—— 实测 2.4 s 级，进得去 5 秒硬顶 ⇒ 与案例同进每提交路径。
#      先跑它：它比案例快得多，坏了当场拒，不必等编译。
#   ①b 跑**判据自测**（`--自测`）—— 每条判据的身份证（反向样本证明它真会红）。它红即拒。
#      ★ 2026-10-09（口径：自测只跑一次，不在释放与合并各跑一遍）：实测闸 0 6.9 s + 自测 35.5 s
#      + 案例 0.5 s ≈ 43 s，自测占八成；而释放（检查提交门禁）与合并（集成树提交门禁）**各跑一遍**
#      = 同一提交被验两遍。自测证的是「判据自身仍会红」，与业务代码无关 ⇒ 只有判据面变了才需重证。故：
#        · 合并提交（MERGE_HEAD 在）⇒ 跑 —— 合并是唯一全闸点
#        · 本次提交进了判据面（`构建装配/一键验证/` 或 `测试验证/案例/`）⇒ 跑
#        · 显式 `V1_FULL_GATE=1` ⇒ 跑
#        · 其余（腿提交、未动判据面）⇒ **跳过并明写回执**（不静默）
#   ② 读 `git rev-parse HEAD`，与回执最新一行的 `提交哈希` 比 —— 不一致就当场说清
#      「最新那份回执不是这个提交的」，让「回执是旧的」与「代码坏了」分得开。
#   ③ 跑**全部**案例（跑案例的程序自身把回执追加进 运行回执.jsonl）。
#   ④ 复核新回执的哈希 == HEAD，再按退出码决定拒或不拒。
#   ⑤ **不暂存回执** —— 回执不进版本库（见 `.gitignore` 里那段）。
#
# **2026-09-27：原第 ④ 步「认领机制的提交闸」已撤**（`决策记录/2026-09-27_开工账本与四道闸.md`）：
# 所有权与指纹的闸搬到了 `v1_edit` 的**写盘前**（四道闸），比在提交时拦更早也更准 ——
# 提交闸读的是那本已被并掉的 `认领机制/账本.json`。
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

# ── 解释器唯一化：仓内 venv（3.14）──
# 裸 `python3` 会解析到系统 3.9.6，与判据面的 3.12+/3.13+ 写法冲突 ⇒ 钩子当场 SyntaxError、
# 提交被拒；而手工用 3.14 跑全绿 = 假绿。腿（worktree）里没有 构建环境/，venv 只在主仓
# ⇒ 先问 git 主目录，再退本树，最后才退解释器名。
MAIN_ROOT=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
[ -x "$PY" ] || PY=$(command -v python3.14 || command -v python3)

# ── 分段耗时：全闸原先只有总数、没有分段读数（每次问「为什么这么慢」都要手工量一遍）──
# 壳自量。`tick` 用 $PY（同解释器口径）；段边界 = 闸0 / 判据自测 / 全案例。
tick() { "$PY" -c 'import time;print(int(time.monotonic()*1000))'; }
T0=$(tick)
[ -x "$PY" ] || PY=$(command -v python3.14 || command -v python3)

# ① 闸 0（声明侧 + 实现侧）—— 实测 2.4 s 级，进得去 5 秒硬顶 ⇒ 与案例同进每提交路径。
#    先跑它：它比案例快得多，坏了当场拒，不必等编译。
#    注：本步跑**仓内 venv 的解释器**（构建环境/python，3.14），不依赖 构建环境/进入.sh。
#    ★ 子进程加 5 秒 timeout（2026-10-05 修 · 审计 B-7）：原先只事后量、无 timeout ⇒ 卡死即挂死。
#    ★ 瞬时超顶自动复跑一次（2026-10-05 修 · 审计 B-10）：并发腿抢 CPU 会把闸 0 顶过 5 秒
#      （实测 5578/5793/6688 ms），那是读数被污染、不是代码坏了 ⇒ 复跑一次，仍超才红。
run_gate0() {
  "$PY" - "$ROOT" <<'PY'
import subprocess
import sys
import sys

sys.path.insert(0, sys.argv[1])
from 构建装配.门禁 import 跑并复跑超顶, 硬顶毫秒

硬顶秒 = 硬顶毫秒 / 1000   # 从**唯一主人**派生（2026-10-08 临时放宽到 10 s）；本件不写第二个数


def 执行一次():
    try:
        回执 = subprocess.run([sys.executable, "构建装配/一键验证/闸0.py"],
                             timeout=硬顶秒, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return 3, "门禁：闸 0 超时（> %g s）—— 硬顶无例外" % 硬顶秒
    return 回执.returncode, (回执.stdout or "") + (回执.stderr or "")


退出码, 输出文本, 复跑过 = 跑并复跑超顶(执行一次)
if 复跑过:
    sys.stderr.write("门禁：闸 0 瞬时超顶（并发腿抢 CPU 的可能）—— 已自动复跑一次%s\n"
                     % ("，通过" if 退出码 == 0 else ""))
if 退出码 != 0:
    sys.stderr.write(输出文本 + "\n")
sys.exit(退出码)
PY
}
GATE0_OUT=$(run_gate0 2>&1)
CODE=$?
if [ "$CODE" -ne 0 ]; then
  printf '%s\n' "${GATE0_OUT}" >&2
  echo "门禁：闸 0 不过（退出码 ${CODE}）⇒ 拒提交" >&2
  exit 1
fi
T1=$(tick)

# ①b 判据自测
#     ★ 2026-10-09 起**按档跑**（口径：自测只跑一次，不在释放与合并各跑一遍）：
#       跑 = 合并提交（MERGE_HEAD 在）· 本次提交进了判据面 · 显式 V1_FULL_GATE=1；其余跳过并明写回执。
#       理由：实测自测 35.5 s（占全闸 43 s 的八成），而它证的是「判据自身仍会红」、与业务代码无关
#       ⇒ 业务腿提交上重证一遍没有新信息，纯浪费；合并才是唯一全闸点。
#     它红有两种可能：① 某条判据的反向样本没了 / 不再报红 / 理由退化成空话
#       ⇒ 那条判据的「会红」没有证据；② ⑱「命令墙钟」正向样本被本机负载顶红。
#     成功时只吞掉它的长读数（77 条各数行）；红了把原文透传出来。
#    ★ 瞬时超顶自动复跑一次（2026-10-08 与 ①闸0 同一份口径 `构建装配/门禁/复跑.py`）：
#      机器一忙，⑱「命令墙钟」在 `--自测` 的嵌套里会假红（读数带「已越过 N ms」）⇒ 复跑一次，仍红才拒。
run_selftest() {
  "$PY" - "$ROOT" <<'PY'
import subprocess
import sys

sys.path.insert(0, sys.argv[1])
from 构建装配.门禁 import 跑并复跑超顶


def 执行一次():
    回执 = subprocess.run([sys.executable, "构建装配/一键验证/一键验证.py", "--自测"],
                        capture_output=True, text=True)
    return 回执.returncode, (回执.stdout or "") + (回执.stderr or "")


退出码, 输出文本, 复跑过 = 跑并复跑超顶(执行一次)
if 复跑过:
    sys.stderr.write("门禁：判据自测瞬时超顶假红（⑱ 命令墙钟在嵌套里被负载顶红）—— 已自动复跑一次%s\n"
                     % ("，通过" if 退出码 == 0 else ""))
if 退出码 != 0:
    sys.stderr.write(输出文本)
sys.exit(退出码)
PY
}
# ── 按档决定跑不跑自测（变量名一律 ASCII：bash 3.2 不认中文变量名，见件头）──
RUN_SELFTEST=0
SELFTEST_WHY=''
if [ "${V1_FULL_GATE:-}" = '1' ]; then
  RUN_SELFTEST=1; SELFTEST_WHY='显式 V1_FULL_GATE=1'
elif [ -n "$(git rev-parse -q --verify MERGE_HEAD)" ]; then
  RUN_SELFTEST=1; SELFTEST_WHY='合并提交（唯一全闸点）'
elif ! git diff --cached --quiet -- 构建装配/一键验证 测试验证/案例; then
  RUN_SELFTEST=1; SELFTEST_WHY='本次提交进了判据面'
fi
if [ "$RUN_SELFTEST" -eq 0 ]; then
  echo "门禁：跳过判据自测（快档 —— 本次未动判据面、也非合并提交）" >&2
  echo "      自测只在 合并提交 / 判据面进暂存 / V1_FULL_GATE=1 时跑；要强制跑：V1_FULL_GATE=1 git commit …" >&2
else
  SELFTEST_OUT=$(run_selftest 2>&1)
  CODE=$?
  if [ "$CODE" -ne 0 ]; then
    printf '%s\n' "${SELFTEST_OUT}" >&2
    echo "门禁：判据自测不过（退出码 ${CODE}）⇒ 先看上面 ✗ 的真读数，两种可能：① 某条判据的反向样本缺失 / 不再报红 / 理由退化成空话；② ⑱「命令墙钟不超五秒」的正向样本被本机负载顶红（并发 CPU；读数带「已越过」= 负载红，不是判据坏了；本步已自动复跑一次仍红）⇒ 拒提交" >&2
    exit 1
  fi
  echo "门禁：判据自测已跑（因：${SELFTEST_WHY}）" >&2
fi
T2=$(tick)

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

# ④ **不暂存回执** —— 它不进版本库（`.gitignore` 里那段有裁决与实测）。
#    ★ 保证不变：钩子每次提交都跑案例、失败即拒 ⇒「提交存在 ⇒ 案例当时过了」仍成立；
#      回执只是**读数**，留在本机给人看。
#    ★ 实测后果（2026-09-27，这条就是改的理由）：回执是**只增日志**，而一开工一工作树时
#      每条支线提交都会往同一个件追加一行 ⇒ N 条支线合并就是 N 次冲突，冲突内容毫无信息量。

T3=$(tick)
echo "门禁分段：闸0 $((T1 - T0)) ms · 自测 $((T2 - T1)) ms · 案例 $((T3 - T2)) ms · 合计 $((T3 - T0)) ms"
echo "门禁：案例全过，回执绑在 $HEAD_SHA 上（父提交）· 回执只落本机，不进版本库"
exit 0
HOOK_BODY

for TARGET in "$HOOK" "$HOOK_MERGE"; do
  cp "$TMP" "$TARGET"
  chmod +x "$TARGET"
done
rm -f "$TMP"

echo "装门禁：已装到 $HOOK 与 $HOOK_MERGE"
echo "        行为：先跑闸 0（声明侧 + 实现侧），再**按档**跑判据自测（合并提交 / 本次进判据面 / V1_FULL_GATE=1 才跑，其余跳过并明写回执），再比 HEAD 与回执里的提交哈希，再跑全部案例，任一失败即拒提交；"
echo "              跑案例的程序把读数追加进 测试验证/案例/运行回执.jsonl，"
echo "              该回执**不进版本库**（只落本机 —— 它是只增日志，进版本库会让每条支线"
echo "              都改同一个件，合并必冲突；见 .gitignore 里那段）。"
echo "              回执里的提交哈希是**跑那一刻的 HEAD**（= 本次提交的父提交）。"
echo "        两个落点：pre-commit（普通提交）· pre-merge-commit（合并提交）—— 同一份体。"
echo "        卸载：把这两个文件删掉即可（本脚本没有留任何别的东西）。"
