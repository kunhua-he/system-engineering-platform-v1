#!/bin/sh
# 自检 —— 断言前端源文件里「0 处解析 / 生成 / 校验」。
#
# 判据：`项目文档/设计文档/接口面形状.md` §五 三条不许之一 ——
#       「前端不许有解析/生成/校验逻辑，前端是纯 UI。任何判断都在后端。」
#
# 依 `项目文档/设计文档/判据的可信性.md` 第五节：判据必须成对 ——
#   反向样本必须报红（证明判据不空转）· 正向样本必须通过（证明判据不误报）。
#   缺任一方 ⇒ 这条判据的「通过」不计入通过数。本脚本两件都做。
#
# 用法：sh 前端呈现/网页应用/自检.sh
# 退出码：0 = 全部通过；1 = 有违规。
#
# 注：变量名一律 ASCII —— sh 不认中文标识符（工具链强制，见 `代码形态分工.md` 一之二）。

set -u
cd "$(cd "$(dirname "$0")" && pwd)" || exit 1

# 扫描面：本目录下的 .html / .js / .css。自检.sh 自己不在扫描面内（它当然含这些词）。
SCAN=""
for f in *.html *.js *.css; do
  [ -f "$f" ] && SCAN="${SCAN} ${f}"
done
SCAN="${SCAN# }"

# 违规词：出现任一个即说明前端在做解析 / 生成 / 校验。中英各半，覆盖常见别名。
PATTERN='解析|生成|校验|验证|判断|检查|转换|validate|valid|parse|generat|convert|regex|正则'

hits() { grep -E -o "${PATTERN}" $1 2>/dev/null | wc -l | tr -d ' '; }

FAIL=0
echo "════ 前端自检 · 网页应用 ════"
echo "扫描面：${SCAN}"
echo

echo "一 违规词命中（应为 0）"
grep -E -n "${PATTERN}" ${SCAN} 2>/dev/null || true
N="$(hits "${SCAN}")"
echo "  命中读数：${N}"
if [ "${N}" -eq 0 ]; then echo "  ✓ 0 处解析 / 生成 / 校验"; else echo "  ✗ 前端出现了解析 / 生成 / 校验"; FAIL=1; fi
echo

TMP="$(mktemp -d)"
echo "二 反向样本（必须报红 —— 否则上面的 0 是空转的）"
printf '%s\n' 'export const 校验器 = 1;' > "${TMP}/反向.js"
RH="$(hits "${TMP}/反向.js")"
echo "  反向样本命中读数：${RH}"
if [ "${RH}" -ge 1 ]; then echo "  ✓ 抓到了（判据不空转）"; else echo "  ✗ 抓不到 ⇒ 判据空转，上面的 0 不算数"; FAIL=1; fi
echo

echo "三 正向样本（干净输入必须通过 —— 否则判据误报）"
printf '%s\n' 'export const 根路径 = "/接口";' > "${TMP}/正向.js"
PH="$(hits "${TMP}/正向.js")"
echo "  正向样本命中读数：${PH}"
if [ "${PH}" -eq 0 ]; then echo "  ✓ 通过"; else echo "  ✗ 误报"; FAIL=1; fi
rm -rf "${TMP}"
echo

echo "四 无构建步骤（不许 package.json / node_modules / CDN 外链）"
for bad in package.json node_modules; do
  if [ -e "${bad}" ]; then echo "  ✗ 出现了 ${bad}"; FAIL=1; fi
done
CDN="$(grep -E -o 'https?://|cdn|unpkg|jsdelivr' ${SCAN} 2>/dev/null | wc -l | tr -d ' ')"
echo "  CDN / 外链命中读数：${CDN}"
if [ "${CDN}" -eq 0 ]; then echo "  ✓ 离线可跑"; else echo "  ✗ 有外链"; FAIL=1; fi
echo

echo "五 端口不写死（不许 127.0.0.1 / localhost / :端口）"
PORT="$(grep -E -o '127\.0\.0\.1|localhost|:[0-9]{4,5}' *.js *.html 2>/dev/null | wc -l | tr -d ' ')"
echo "  写死主机/端口命中读数：${PORT}"
if [ "${PORT}" -eq 0 ]; then echo "  ✓ 一律同源相对路径"; else echo "  ✗ 写死了主机或端口"; FAIL=1; fi
echo

echo "六 每个源文件 ≤ 400 行"
for f in ${SCAN}; do
  L="$(wc -l < "${f}" | tr -d ' ')"
  if [ "${L}" -le 400 ]; then echo "  ✓ ${f}  ${L} 行"; else echo "  ✗ ${f}  ${L} 行"; FAIL=1; fi
done
echo

if [ "${FAIL}" -eq 0 ]; then
  echo "════ 全部通过 ════"
else
  echo "════ 有违规，见上面的 ✗ ════"
fi
exit "${FAIL}"
