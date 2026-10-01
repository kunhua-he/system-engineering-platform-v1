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
# 判法是**位置判据**，不是**词命中**（照 ⑪-3 / ⑪-4 先例）：
#   早先的模式是一袋词（`解析|生成|校验|验证|…`），于是**真实路径**也被禁 ——
#   `测试验证/案例/` 里含「验证」，前端不敢写真路径、只好写「案例区」（名词被判成违规）。
#   现在只认**调用形 / 定义形**：`JSON.parse(` · `DOMParser` · `.test(` ·
#   `校验(` 这种「后面紧跟 `(`」的形状才算「在解析 / 在判断」。
#   路径字符串（`"/测试验证/案例"`）里「验证」后面是 `/` 不是 `(` ⇒ 不命中。
#
# 扫描面**只做静态检查**（本脚本不启动浏览器、不读运行时页面控制台）—— 见「八 检查面声明」。
#
# 用法：sh 前端呈现/网页应用/自检.sh
# 退出码：0 = 全部通过；1 = 有违规。
#
# 注：变量名一律 ASCII —— sh 不认中文标识符（工具链强制，见 `代码形态分工.md` 一之二）。

set -u
cd "$(cd "$(dirname "$0")" && pwd)" || exit 1
START_EPOCH="$(date +%s)"

# 扫描面：本目录下的 .html / .js / .css。自检.sh 自身不在扫描面内（它当然含这些词）。
SCAN=""
for f in *.html *.js *.css; do
  [ -f "$f" ] && SCAN="${SCAN} ${f}"
done
SCAN="${SCAN# }"

# 违规形（位置判据）：只有「调用 / 定义形」才算 —— 关键词后面紧跟 `(`。
#   ① 真解析 / 真执行：`JSON.parse(` · `DOMParser` · `eval(` · `new Function(` · `new RegExp(`
#   ② 正则真判断：`.test(` / `.exec(`
#   ③ 中文动词的调用 / 定义形：`校验(` · `校验器(` · `验证结果(`（后面必须跟 `(`）
#   ④ 英文动词的调用 / 定义形：`validate(` · `parse(` · `convert(` …
# 不含 `正则` / `regex` 的裸词：它们作名词（如 `// 这里不用正则`）不构成「在判断」，
# 作调用形时已被 `new RegExp(` / `.test(` 覆盖。
PATTERN='JSON[[:space:]]*\.[[:space:]]*parse[[:space:]]*\(|DOMParser|parseFromString[[:space:]]*\(|eval[[:space:]]*\(|new[[:space:]]+Function[[:space:]]*\(|new[[:space:]]+RegExp[[:space:]]*\(|\.[[:space:]]*(test|exec)[[:space:]]*\(|(解析|校验|验证|生成|判断|检查|转换)[A-Za-z0-9_$]*[[:space:]]*\(|(validate|valid|parse|generat|convert)[A-Za-z0-9_$]*[[:space:]]*\('

hits() { grep -E -o "${PATTERN}" $1 2>/dev/null | wc -l | tr -d ' '; }

FAIL=0
echo "════ 前端自检 · 网页应用 ════"
echo "扫描面：${SCAN}"
echo

echo "一 违规形命中（应为 0）"
grep -E -n "${PATTERN}" ${SCAN} 2>/dev/null || true
N="$(hits "${SCAN}")"
echo "  命中读数：${N}"
if [ "${N}" -eq 0 ]; then echo "  ✓ 0 处解析 / 生成 / 校验"; else echo "  ✗ 前端出现了解析 / 生成 / 校验"; FAIL=1; fi
echo

TMP="$(mktemp -d)"
echo "二 反向样本（必须报红 —— 否则上面的 0 是空转的）"
printf '%s\n' 'export function 校验(文) { return JSON.parse(文); }' > "${TMP}/反向.js"
RH="$(hits "${TMP}/反向.js")"
echo "  反向样本命中读数：${RH}"
if [ "${RH}" -ge 1 ]; then echo "  ✓ 抓到了（判据不空转）"; else echo "  ✗ 抓不到 ⇒ 判据空转，上面的 0 不算数"; FAIL=1; fi
echo

echo "三 正向样本（干净输入必须通过 —— 否则判据误报）"
# 正向样本刻意含**真实路径**（`测试验证/案例/`）与一个普通赋值 —— 它们都该通过。
# 这一条同时钉住 #161：路径里的「验证」是名词，不许被判成「在验证」。
printf '%s\n' 'export const 案例根 = "/测试验证/案例";' 'export const 校验器名 = "纯名词，不是调用";' > "${TMP}/正向.js"
PH="$(hits "${TMP}/正向.js")"
echo "  正向样本命中读数：${PH}"
if [ "${PH}" -eq 0 ]; then echo "  ✓ 通过（真实路径不被误报）"; else echo "  ✗ 误报（路径名词被判成动作）"; FAIL=1; fi
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

echo "七 源码 0 处向控制台输出（静态调用形）"
# 判据：前端是纯 UI，不往浏览器控制台打日志。这是**静态**读数（扫源码里的 `console.*` 调用形），
# 与「运行时页面控制台 0 条」（需浏览器 + CDP）是两件不同的事 —— 见「八 检查面声明」。
# 位置判据（同一/四）：只有 `console.xxx(` 这种**调用形**才算；注释里的「控制台」是名词，不算。
CONSOLE_PATTERN='console[[:space:]]*\.[[:space:]]*[A-Za-z_$][A-Za-z0-9_$]*[[:space:]]*\('
CN="$(grep -E -o "${CONSOLE_PATTERN}" ${SCAN} 2>/dev/null | wc -l | tr -d ' ')"
echo "  console.* 调用形命中读数：${CN}"
if [ "${CN}" -eq 0 ]; then echo "  ✓ 0 处向控制台输出"; else echo "  ✗ 源码里有 console.* 调用"; FAIL=1; fi
# 反向样本（必须报红）+ 正向样本（注释/名词必须通过）—— 判据必须成对（同 二/三）。
TMP2="$(mktemp -d)"
printf '%s\n' 'console.log("x");' > "${TMP2}/反向控制台.js"
CH="$(grep -E -o "${CONSOLE_PATTERN}" "${TMP2}/反向控制台.js" 2>/dev/null | wc -l | tr -d ' ')"
echo "  反向样本命中读数：${CH}"
if [ "${CH}" -ge 1 ]; then echo "  ✓ 抓到了（判据不空转）"; else echo "  ✗ 抓不到 ⇒ 判据空转"; FAIL=1; fi
printf '%s\n' '// 控制台输出只由浏览器驱动读，本页不写' 'const 控制台 = "纯名词";' > "${TMP2}/正向控制台.js"
CP="$(grep -E -o "${CONSOLE_PATTERN}" "${TMP2}/正向控制台.js" 2>/dev/null | wc -l | tr -d ' ')"
echo "  正向样本命中读数：${CP}"
if [ "${CP}" -eq 0 ]; then echo "  ✓ 通过（注释/名词不被误报）"; else echo "  ✗ 误报"; FAIL=1; fi
rm -rf "${TMP2}"
echo

echo "八 检查面声明（本脚本查什么 / 不查什么）"
# 本脚本**不查运行时页面控制台输出** —— 它是纯静态 shell，不启动浏览器、不连 CDP。
# 「运行时页面控制台 0 条」是另一条路（CDP）测的读数，**不在本判据集内**。
# 本脚本查的是**源码静态**的 `console.*` 调用形（「七」那一节）；两者不许混称。
echo "  · 查：静态源码里的解析/生成/校验调用形 · 无构建步骤 · 端口不写死 · 单件 ≤400 行 · 源码 0 处 console.* 调用形 · 本命令墙钟"
echo "  · 不查：运行时页面控制台输出（需浏览器 + CDP，不在本静态脚本内；别把它说成本脚本查的）"
echo

echo "九 命令墙钟 ≤ 5 秒（决策记录 五秒硬顶 §一：本命令在 §一 范围里被点名）"
# ★ 命令级墙钟**自量自门禁**：一条命令的完整墙钟只有它自身的壳能量，中央判据读别条命令的
#   回执行不通（回执不在 ⇒ 未判 ⇒ 退出码 1 ⇒ 门禁永久红；且回执里常是内部耗时，冒充墙钟就是
#   假读数）。落点见 `2026-09-27_所有运行五秒硬顶.md` §六.1。
# 计时只用 `date +%s`（POSIX，本脚本不引入 python3 之类的额外依赖 ⇒ 单独跑也成立）。
# **分辨率 ±1 秒**：故阈值取 **3 秒**（比硬顶留足 2 秒余量）—— 这条闸**只抓量级退化**
#   （例：有人往本脚本里塞一步真解析/真编译，从 0.2 秒变成十几秒），不假装能判 3–5 秒之间。
#   计时粒度是如实登记的**口径下限**，不许在别处声称「本脚本能判 1 毫秒级」。
END_EPOCH="$(date +%s)"
ELAPSED=$((END_EPOCH - START_EPOCH))
echo "  完整墙钟读数：${ELAPSED} 秒（粒度 1 秒 · 阈值 3 秒）"
if [ "${ELAPSED}" -le 3 ]; then echo "  ✓ 在硬顶内"; else echo "  ✗ 越过硬顶（> 5 秒）"; FAIL=1; fi
# 反向样本（**阈值失效式**，同 `一键验证` 判据 ⑱ 的先例）：把起始时刻往前挪 4 秒 ⇒ 读数必 > 3
# ⇒ 本闸当场红。不用「真睡 4 秒」：那会把**本命令自身**顶到硬顶边上（本命令也是一条命令）。
if [ $((END_EPOCH - (START_EPOCH - 4))) -gt 3 ]; then
  echo "  ✓ 反向样本：起始时刻前挪 4 秒 ⇒ 读数 4 秒 ⇒ 当场红（本闸不空转）"
else
  echo "  ✗ 反向样本抓不住 ⇒ 本闸空转，上面的 ✓ 不算数"; FAIL=1
fi
echo

if [ "${FAIL}" -eq 0 ]; then
  echo "════ 全部通过 ════"
else
  echo "════ 有违规，见上面的 ✗ ════"
fi
exit "${FAIL}"
