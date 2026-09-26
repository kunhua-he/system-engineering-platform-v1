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
# 钩子只判「拒或不拒」，**自己绝不 git commit**（提交纪律：提交是人/协调方的事）。
#
# ★ 变量名一律 ASCII —— **实测**：macOS 的 `/bin/sh` 是 bash 3.2，**不认中文变量名**
#   （`仓根=$(...)` 会被当成一条命令，报 `No such file or directory`）。
#   这是工具链强制，与 `构建环境/进入.sh` 的注 1 同一条理由。

set -u

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

HOOK="$ROOT/.git/hooks/pre-commit"
if [ ! -d "$ROOT/.git/hooks" ]; then
  echo "装门禁：找不到 $ROOT/.git/hooks —— 本仓不是一个 git 工作区？" >&2
  exit 1
fi

# ── 幂等与不踩别人 ──
if [ -f "$HOOK" ] && ! grep -qF "$MARK" "$HOOK"; then
  echo "装门禁：$HOOK 已经存在且不是本门禁装的 —— 拒绝覆盖。" >&2
  echo "        要装就先自己处置那个钩子（本脚本不替你做这个决定）。" >&2
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
# 四步：
#   ① 读 `git rev-parse HEAD`，与回执最新一行的 `提交哈希` 比 —— 不一致就当场说清
#      「最新那份回执不是这个提交的」，让「回执是旧的」与「代码坏了」分得开。
#   ② 跑**全部**案例（跑案例的程序自己把回执追加进 运行回执.jsonl）。
#   ③ 复核新回执的哈希 == HEAD，再按退出码决定拒或不拒。
#   ④ 把新回执 `git add` 进本次提交 —— 证据跟着提交走，提交后工作区不残留一行。
#
# **回执的 `提交哈希` 是「跑那一刻的 HEAD」**（`测试验证/案例/形状.md` §四：回执绑提交哈希，
# 否则「回执是旧的」与「代码坏了」不可区分 —— `判据的可信性.md` §三 的假绿来源之一）。
# 钩子跑在**提交之前** ⇒ 那一刻的 HEAD = **本次提交的父提交**（回执不可能写自己的提交哈希 ——
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

# ④ 把新回执暂存进本次提交 —— 证据跟着提交走（提交后 `git status` 不残留这一行）。
#    暂存**整个**追加式回执件：它是追加日志，整体入版本（不是只挑一行）。
git add "$RECEIPT" || { echo "门禁：回执暂存失败 ⇒ 拒提交" >&2; exit 1; }

echo "门禁：案例全过，回执绑在 $HEAD_SHA 上（父提交），已暂存进本次提交"
exit 0
HOOK_BODY

mv "$TMP" "$HOOK"
chmod +x "$HOOK"

echo "装门禁：已装到 $HOOK"
echo "        行为：先比 HEAD 与回执里的提交哈希，再跑全部案例，任一失败即拒提交；"
echo "              跑案例的程序把读数追加进 测试验证/案例/运行回执.jsonl，"
echo "              通过后由钩子把该回执暂存进本次提交（提交后工作区不残留一行）。"
echo "              回执里的提交哈希是**跑那一刻的 HEAD**（= 本次提交的父提交）。"
echo "        卸载：删掉那个文件即可（本脚本没有留任何别的东西）。"
