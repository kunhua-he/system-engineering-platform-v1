// 使用面回归 · 网页应用 —— 未知结果不得标成功 + 链末一步只调一次（纯函数 / fetch 替身夹具）。
//
// 判据：`接口面形状.md` §三（成功没成功只看服务端 `成功` 字段，不靠猜）；
//       编译链「每步只调一次、链末应答**复用**不重复执行」。
// 为什么要有它：网页失败保真（未知结果不标成功）与链末去重此前**零自动化测试**；
//       静态 `自检.sh` 只查解析/生成/校验调用形，不是运行时覆盖。
//
// 做法：装 fetch 替身 + 最小 DOM 替身，真 import 生产模块（`呈现.js` / `编译.js`）。
//   node 测试验证/准入判据/使用面回归_网页.mjs
// 退出码：0 = 各条断言成立；1 = 有断言不成立。

import * as 文件系统 from "node:fs";
import * as 路径 from "node:path";
import * as 系统临时 from "node:os";
import * as 网址 from "node:url";

// 生产 .js 是 ES 模块，但仓里没有 package.json（硬规矩：不许引构建步骤）⇒ node 认不出 .js 的模块型。
// 故把三件源件**逐字**复制到临时目录、只把相对 import 的后缀从 .js 换成 .mjs，再 import 临时副本。
// 被断言的仍是生产源码本身（复制不改一个字节，只改模块说明符）。
const 网页根 = new URL("../../前端呈现/网页应用/", import.meta.url);
const 临时根 = 文件系统.mkdtempSync(路径.join(系统临时.tmpdir(), "网页回归-"));
const 模块表 = ["呈现", "取接口", "编译"];
for (const 模块名 of 模块表) {
  const 源文本 = 文件系统
    .readFileSync(new URL(模块名 + ".js", 网页根), "utf8")
    .replace(/from "\.\/([^"]+)\.js"/g, 'from "./$1.mjs"');
  文件系统.writeFileSync(路径.join(临时根, 模块名 + ".mjs"), 源文本);
}
const 呈现模块 = await import(网址.pathToFileURL(路径.join(临时根, "呈现.mjs")).href);
const 编译模块 = await import(网址.pathToFileURL(路径.join(临时根, "编译.mjs")).href);
const 取应答摘要 = 呈现模块.取应答摘要;
const 跑编译 = 编译模块.跑编译;
const 跑诊断 = 编译模块.跑诊断;

// ── 最小 DOM 替身：只实现生产代码用到的那几个形状 ──
function 造假元素() {
  const 节点 = {
    className: "",
    textContent: "",
    子项表: [],
    firstChild: null,
    classList: { add() {} },
    append() {
      for (const 子项 of arguments) {
        this.子项表.push(子项);
        if (!this.firstChild) this.firstChild = 子项;
      }
    },
    removeChild(子项) {
      this.子项表 = this.子项表.filter((待处理值) => 待处理值 !== 子项);
      this.firstChild = this.子项表[0] || null;
    },
  };
  return 节点;
}
globalThis.document = { createElement: () => 造假元素() };

const 元素表 = {};
const 取元素 = (节点名) => (元素表[节点名] ||= 造假元素());
const 编辑 = { value: "整数 x 定义。" };

// ── fetch 替身：只认链上那三条 GET/POST，POST 计数 ──
let 请求次数 = 0;
let 当前应答体 = { 值: [{ 类型标签: 4, 值: "ok" }] }; // 未知形状：没有逻辑型 `成功`
function 造假应答(状态码, 应答体, 应答文本) {
  return {
    status: 状态码,
    clone() { return this; },
    async json() { return 应答体; },
    async text() { return 应答文本; },
  };
}
globalThis.fetch = async (目标, 选项 = {}) => {
  if ((选项.method || "GET") === "POST") {
    请求次数 += 1;
    return 造假应答(200, 当前应答体, JSON.stringify(当前应答体));
  }
  if (目标 === "/接口") {
    return 造假应答(200, { 能力: [{ 编号: 1, 名称: "样例能力", 参数个数: 1 }] }, "{}");
  }
  if (目标.startsWith("/接口/能力/")) {
    return 造假应答(200, { 契约: { 参数表: [{ 类型标签: 4 }] } }, "{}");
  }
  return 造假应答(404, null, "not found");
};

const 失败表 = [];
function 记一条(条名, 条件, 实际) {
  console.log(`  [${条件 ? "符合" : "不符"}] ${条名}`);
  console.log(`        实际：${实际}`);
  if (!条件) 失败表.push(条名);
}

console.log("使用面回归 · 网页应用（纯函数 + fetch 替身夹具）");

// 一 纯函数：成功判定只认服务端 `成功` 字段。
记一条("成功字段为真才标成功", 取应答摘要({ 成功: true }).判定档 === "好", "好");
记一条("成功字段为假标失败", 取应答摘要({ 成功: false }).判定档 === "坏", "坏");
记一条("未知结果不得标成功", 取应答摘要({ 值: [] }).判定档 === "灰", JSON.stringify(取应答摘要({ 值: [] })));
记一条("非对象一律未知", 取应答摘要("不是对象").判定档 === "灰", "灰");

// 二 链末去重：链上 1 步 ⇒ 只调 1 次；未知结果不标明确成功。
请求次数 = 0;
await 跑编译(取元素, 编辑);
记一条("链上 1 步只调一次（链末去重）", 请求次数 === 1, `请求次数=${请求次数}`);
记一条(
  "未知结果不标明确成功",
  String(元素表["输出状态"].textContent).includes("含未知结果"),
  元素表["输出状态"].textContent,
);

// 三 显式诊断：不给已有应答 ⇒ 真调一次；给已有应答 ⇒ 不再重复执行。
请求次数 = 0;
await 跑诊断(取元素, 编辑);
记一条("显式诊断调链末一次", 请求次数 === 1, `请求次数=${请求次数}`);
请求次数 = 0;
await 跑诊断(取元素, 编辑, { 状态: 200, 报文体: { 成功: true, 值: [] }, 应答文本: "{}" });
记一条("传入已有应答不再重复执行（链末去重）", 请求次数 === 0, `请求次数=${请求次数}`);

console.log("");
if (失败表.length) {
  console.log(`网页回归：不符 ${失败表.length} 条 —— ${失败表.join(" · ")}`);
  process.exit(1);
}
console.log("网页回归：全部符合（退出码 0）");
