#!/bin/bash
# 批量接入 —— 老项目（系统工程平台/）逐层翻译成 V1 契约声明的批量入口。
#
# 小队6产出。读 `老项目依赖图.json` 的「接入顺序」（小队3产出），按依赖层级
# 从低到高逐批逐层调用 `老项目模块翻译.py`（小队5产出）；某层失败即停
# （不再接后续层，避免级联错误）。
#
# 用法：
#   bash 构建装配/翻译器/批量接入.sh                 # 正式批量接入
#   bash 构建装配/翻译器/批量接入.sh --干跑           # 只演练顺序与前置，不调翻译器
#   bash 构建装配/翻译器/批量接入.sh --跳过验证        # 不跑契约一致性 / 闸0
#   bash 构建装配/翻译器/批量接入.sh --依赖图 <路径> --翻译器 <路径> --日志 <路径>
#
# 退出码：0 成功 · 2 前置缺失 · 3 翻译失败 · 4 契约验证失败 · 5 门禁失败
#
# 幂等：可重复执行；翻译器按模块覆盖输出，日志每次重建。
#
# ★ 本件标识符一律 ASCII —— sh/bash 不认非 ASCII 标识符（工具链强制，见
#   `项目文档/设计文档/代码形态分工.md` 第三节 三条例外）。中文只进注释与输出串。

set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

GRAPH="$REPO_ROOT/构建装配/翻译器/老项目依赖图.json"
TRANSLATOR="$REPO_ROOT/构建装配/翻译器/老项目模块翻译.py"
LOGFILE="$REPO_ROOT/构建装配/翻译器/批量接入日志.txt"
CONTRACT_CHECK="$REPO_ROOT/测试验证/契约一致性/扫实现.py"
GATE="$REPO_ROOT/构建装配/一键验证/闸0.py"

DRY_RUN=0
RUN_VERIFY=1

while [ $# -gt 0 ]; do
  case "$1" in
    --干跑)     DRY_RUN=1 ;;
    --跳过验证) RUN_VERIFY=0 ;;
    --依赖图)   if [ $# -lt 2 ]; then printf '参数 %s 缺值\n' "$1" >&2; exit 2; fi; GRAPH=$2; shift ;;
    --翻译器)   if [ $# -lt 2 ]; then printf '参数 %s 缺值\n' "$1" >&2; exit 2; fi; TRANSLATOR=$2; shift ;;
    --日志)     if [ $# -lt 2 ]; then printf '参数 %s 缺值\n' "$1" >&2; exit 2; fi; LOGFILE=$2; shift ;;
    -h|--帮助)  sed -n '2,19p' "$0"; exit 0 ;;
    *)          printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$(dirname "$LOGFILE")"
: > "$LOGFILE"

# 仓内相对路径（不在仓内则原样）—— 让日志不绑某棵工作树。
rel() {
  case "$1" in
    "$REPO_ROOT"/*) printf '%s' "${1#"$REPO_ROOT"/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

log() { printf '%s\n' "$*" | tee -a "$LOGFILE"; }

START_AT=$(date '+%Y-%m-%d %H:%M:%S')
START_EPOCH=$(date +%s)

log "=== 批量接入开始 ==="
log "开始时间：$START_AT"
log "依赖图：$(rel "$GRAPH")"
log "翻译器：$(rel "$TRANSLATOR")"
if [ "$DRY_RUN" = "1" ]; then log "模式：干跑演练（不调翻译器）"; else log "模式：正式接入"; fi
log ""

# ---------- 前置检查：环境与输入 ----------
log "=== 前置检查 ==="
if command -v python3 >/dev/null 2>&1; then
  log "  ✓ python3：$(python3 -V 2>&1)"
else
  log "  ✗ python3 缺失 —— 翻译器与依赖图解析都要它"
  exit 2
fi

if [ -f "$GRAPH" ]; then
  log "  ✓ 依赖图：$(rel "$GRAPH")"
else
  log "  ✗ 依赖图缺失：$(rel "$GRAPH")"
  log "    （小队3产出 —— 没有它定不了接入顺序）"
  exit 2
fi

OLD_ROOT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("老项目根",""))' "$GRAPH") || {
  log "  ✗ 依赖图解析失败：$(rel "$GRAPH")"
  exit 2
}

if [ -n "$OLD_ROOT" ] && [ -d "$OLD_ROOT" ]; then
  log "  ✓ 老项目根：$OLD_ROOT"
else
  log "  ✗ 老项目根不可达：${OLD_ROOT:-（依赖图未写 老项目根）}"
  exit 2
fi
log ""

# ---------- 接入顺序（计划） ----------
PLAN=$(python3 - "$GRAPH" <<'PY'
import json, sys
graph = json.load(open(sys.argv[1], encoding="utf-8"))
layers = {m["层"]: m for m in graph.get("模块列表", [])}
for batch in graph.get("接入顺序", []):
    for layer in batch.get("层", []):
        m = layers.get(layer, {})
        deps = ",".join(m.get("声明依赖", [])) or "—"
        print("\t".join([str(batch.get("批次", "?")), layer,
                         str(m.get("层级", "?")), str(m.get("文件数", "?")), deps]))
PY
)

log "=== 接入顺序（计划） ==="
while IFS=$'\t' read -r batch layer level files deps; do
  if [ -n "$layer" ]; then
    log "  第${batch}批 · ${layer}（第${level}层 · 依赖图记 ${files} 个 .py · 依赖：${deps}）"
  fi
done <<< "$PLAN"
log ""

log "=== 顺序自检（每层依赖须落在更早批次） ==="
SELFCHECK=$(python3 - "$GRAPH" <<'PY'
import json, sys
graph = json.load(open(sys.argv[1], encoding="utf-8"))
layers = {m["层"]: m for m in graph.get("模块列表", [])}
order = graph.get("接入顺序", [])
batch_of = {}
for batch in order:
    for name in batch.get("层", []):
        batch_of[name] = batch.get("批次", 0)
for batch in order:
    for name in batch.get("层", []):
        deps = layers.get(name, {}).get("声明依赖", [])
        bad = [d for d in deps if d not in batch_of or batch_of[d] >= batch_of[name]]
        if bad:
            print("✗ %s（第%s批）：依赖 %s 未落在更早批次" % (name, batch_of[name], "、".join(bad)))
        else:
            print("✓ %s（第%s批）：依赖 %s 均在更早批次" % (name, batch_of[name], "、".join(deps) if deps else "无"))
missing = [n for n in layers if n not in batch_of]
ghost = [n for n in batch_of if n not in layers]
if missing:
    print("✗ 接入顺序漏了模块列表里的层：%s" % "、".join(missing))
if ghost:
    print("✗ 接入顺序里有模块列表没有的层：%s" % "、".join(ghost))
cyc = graph.get("循环依赖") or []
print("✗ 存在循环依赖：" + "、".join(cyc) if cyc else "✓ 无循环依赖")
PY
)
while IFS= read -r line; do
  log "  $line"
done <<< "$SELFCHECK"
PROBLEM_N=$(printf '%s\n' "$SELFCHECK" | grep -c '^✗' || true)
if [ "$PROBLEM_N" != "0" ]; then
  log ""
  log "=== 批量接入中止（依赖图顺序有误：${PROBLEM_N} 处） ==="
  exit 2
fi
log ""

# ---------- 前置检查：翻译器 ----------
TRANSLATOR_OK=0
if [ -f "$TRANSLATOR" ]; then TRANSLATOR_OK=1; fi

if [ "$TRANSLATOR_OK" = "1" ]; then
  log "  ✓ 翻译器：$(rel "$TRANSLATOR")"
elif [ "$DRY_RUN" = "1" ]; then
  log "  ⚠ 翻译器缺失：$(rel "$TRANSLATOR")（干跑不调它，继续）"
else
  log "  ✗ 翻译器缺失：$(rel "$TRANSLATOR")"
  log "    （小队5产出 —— 没有它翻不了任何一层）"
  log "    ⇒ 本次转为「逐层预检」：走完接入顺序但不翻译，末尾以退出码 2 中止"
fi
log ""

# ---------- 逐层接入 ----------
log "=== 逐层接入 ==="
TOTAL=0
DONE=0
LAST_BATCH=""
while IFS=$'\t' read -r batch layer level files deps; do
  if [ -z "$layer" ]; then continue; fi
  TOTAL=$((TOTAL + 1))
  if [ "$batch" != "$LAST_BATCH" ]; then
    log ""
    log "--- 第${batch}批 ---"
    LAST_BATCH=$batch
  fi
  if [ "$DRY_RUN" = "1" ] || [ "$TRANSLATOR_OK" != "1" ]; then
    real_files=$(find "$OLD_ROOT/$layer" -name '*.py' -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DRY_RUN" = "1" ]; then TAG=干跑; else TAG=预检; fi
    log "  [${TAG}] ${layer}：老项目实有 ${real_files} 个 .py（依赖图记 ${files}）"
    DONE=$((DONE + 1))
    continue
  fi
  log "  翻译 ${layer} ..."
  if python3 "$TRANSLATOR" --模块 "$layer" >> "$LOGFILE" 2>&1; then
    log "  ✓ ${layer} 翻译成功"
    DONE=$((DONE + 1))
  else
    code=$?
    log "  ✗ ${layer} 翻译失败（退出码 ${code}）—— 按「失败即停」中止，不再接后续层"
    log ""
    log "=== 批量接入中止（翻译失败） ==="
    exit 3
  fi
done <<< "$PLAN"

# ---------- 汇总 ----------
BATCH_N=$(printf '%s\n' "$PLAN" | cut -f1 | grep -v '^$' | sort -u | wc -l | tr -d ' ')
log ""
log "=== 汇总 ==="
if [ "$DRY_RUN" = "1" ]; then
  log "  批次 ${BATCH_N} 个 · 层 ${TOTAL} 个 · 演练完成 ${DONE}"
elif [ "$TRANSLATOR_OK" != "1" ]; then
  log "  批次 ${BATCH_N} 个 · 层 ${TOTAL} 个 · 预检 ${DONE}（未翻译 —— 翻译器缺失）"
else
  log "  批次 ${BATCH_N} 个 · 层 ${TOTAL} 个 · 完成 ${DONE} · 失败 $((TOTAL - DONE))"
fi
log "  耗时 $(( $(date +%s) - START_EPOCH )) 秒"

if [ "$DRY_RUN" != "1" ] && [ "$TRANSLATOR_OK" != "1" ]; then
  log ""
  log "=== 批量接入中止（前置缺失：翻译器） ==="
  exit 2
fi

# ---------- 验证 ----------
if [ "$DRY_RUN" = "1" ]; then
  log ""
  log "（干跑演练 —— 跳过契约验证与门禁）"
elif [ "$RUN_VERIFY" = "1" ]; then
  log ""
  log "=== 验证契约 ==="
  if [ -f "$CONTRACT_CHECK" ]; then
    if python3 "$CONTRACT_CHECK" >> "$LOGFILE" 2>&1; then
      log "  ✓ 契约验证通过"
    else
      log "  ✗ 契约验证失败 —— 详见本日志上方输出"
      exit 4
    fi
  else
    log "  ✗ 契约校验件缺失：$(rel "$CONTRACT_CHECK")"
    log ""
    log "=== 批量接入中止（前置缺失：契约校验件） ==="
    exit 2
  fi
  log "=== 门禁验证 ==="
  if [ -f "$GATE" ]; then
    if python3 "$GATE" >> "$LOGFILE" 2>&1; then
      log "  ✓ 门禁通过"
    else
      log "  ✗ 门禁失败 —— 详见本日志上方输出"
      exit 5
    fi
  else
    log "  ✗ 门禁件缺失：$(rel "$GATE")"
    log ""
    log "=== 批量接入中止（前置缺失：门禁件） ==="
    exit 2
  fi
else
  log ""
  log "（--跳过验证 —— 跳过契约验证与门禁）"
fi

log ""
log "=== 批量接入完成 ==="
