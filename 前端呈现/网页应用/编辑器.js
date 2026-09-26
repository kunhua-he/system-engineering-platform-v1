// 编辑器 —— 写 `.程序文本` 的那个文本区。
//
// 它做的事只有四件，**一件都不多**：
//   ① `Tab` 插 4 个半角空格（挡住浏览器默认的换焦点）；
//   ② 行号栏跟着行数走（只报位置，不认内容）；
//   ③ 报光标位置与字符数；
//   ④ 从语料载入示例（只读，同源取）。
//
// **没有语法高亮，也没有任何别的「智能」** —— 不做自动缩进、不做括号配对、不做补全。
// 编辑器只是文本区：程序文本的解释权全在后端（判据：`项目文档/设计文档/接口面形状.md` §五）。

import { 取静态件 } from "./取接口.js";
import { 写状态 } from "./呈现.js";

/** 本页内置的极小模板 —— 不是语料，只是让编辑区一开始不空着。 */
const 模板 = [
  ".版本 2",
  "",
  ".程序集 程序集1",
  "",
  ".子程序 甲, 整数",
  "    返回 1",
  "",
].join("\n");

/**
 * 载入示例的清单。
 *
 * **曾经**这里列了 6 条「语料」入口，路径指向
 * `扩展根目录/原子支持库/编译器支持库/语料/真文本/…`。那两条都站不住，已撤：
 *
 *  1. **取不到**：静态托管的根是 `前端呈现/网页应用`（`常量.rs::静态根`，判据
 *     「只托管前端自己的件 · 仓内别处一律 404」），所以 `/扩展根目录/…` 恒 404 ——
 *     那 6 条点了只会报错，是个死功能。
 *  2. **破硬边界**：底座里出现某个扩展的名字与它的私有目录（README §五 硬边界 1）。
 *     底座要用扩展的东西只能经端点实时取，不许伸手进扩展的目录。
 *
 * 恢复它的正路是「程序文本」那一层的落点定下来之后走 `POST /接口/程序文本`（§七 端点，
 * 现在回 `9006 程序文本路径未定`）—— 落点未裁，见 `项目文档/未完成事项.md`。
 */
export const 示例表 = [
  ["本页内置的极小模板（不是语料）", ""],
];

/** 取编辑区原文。 */
export function 取文本(编辑) {
  return 编辑.value;
}

/** 往编辑区放文本（**原样**，不规范化换行、不动缩进）。 */
export function 置文本(编辑, 文) {
  编辑.value = 文 === undefined || 文 === null ? "" : String(文);
  编辑.dispatchEvent(new Event("input"));
}

/**
 * 装好编辑器。返回 `{ 编辑, 刷 }`。
 * `取` 是 `(id) => 节点`，由 `应用.js` 给（本文件不认 id 字符串之外的页面结构）。
 */
export function 装编辑器(取) {
  const 编辑 = 取("编辑区");
  const 号 = 取("行号");
  const 行列 = 取("行列读数");
  const 字数 = 取("字数读数");

  function 刷光标() {
    const 前 = 编辑.value.slice(0, 编辑.selectionStart);
    const 行 = 前.split("\n").length;
    const 列 = 前.length - (前.lastIndexOf("\n") + 1) + 1;
    行列.textContent = 行 + " : " + 列;
  }

  function 刷() {
    const 文 = 编辑.value;
    const 行数 = 文.split("\n").length;
    if (号.dataset.行数 !== String(行数)) {
      号.dataset.行数 = String(行数);
      const 表 = [];
      for (let 序 = 1; 序 <= 行数; 序 += 1) 表.push(String(序));
      号.textContent = 表.join("\n");
    }
    字数.textContent = String(文.length);
    刷光标();
  }

  编辑.addEventListener("input", 刷);
  编辑.addEventListener("keyup", 刷光标);
  编辑.addEventListener("click", 刷光标);
  编辑.addEventListener("scroll", () => {
    号.scrollTop = 编辑.scrollTop;
  });

  编辑.addEventListener("keydown", (事) => {
    if (事.key !== "Tab" || 事.ctrlKey || 事.metaKey || 事.altKey) return;
    事.preventDefault();
    编辑.setRangeText("    ", 编辑.selectionStart, 编辑.selectionEnd, "end");
    刷();
  });

  // 示例下拉与载入按钮
  const 选 = 取("示例选");
  示例表.forEach(([标签], 位) => {
    const 项 = document.createElement("option");
    项.value = String(位);
    项.textContent = 标签;
    选.append(项);
  });

  // 工具条的「打开」也走这里，所以只写一份（载入示例）。
  async function 载入示例() {
    const 位 = Number(选.value || 0);
    const 路 = 示例表[位][1];
    const 状态 = 取("工具状态");
    if (!路) {
      置文本(编辑, 模板);
      写状态(状态, "已载入内置模板", true);
      return "已载入内置模板（不是语料）";
    }
    写状态(状态, "取语料中…");
    try {
      const 件 = await 取静态件(路);
      if (件.状态 !== 200) {
        const 文 = "取不到（HTTP " + 件.状态 + "）：同源静态托管没把仓内路径交出来";
        写状态(状态, 文, false);
        return 文;
      }
      置文本(编辑, 件.文);
      const 文 = "已载入 " + 路.split("/").pop() + "（" + 件.文.length + " 字符）";
      写状态(状态, 文, true);
      return 文;
    } catch (错) {
      const 文 = "发不出去：" + 错.message;
      写状态(状态, 文, false);
      return 文;
    }
  }

  // 工具条的「新建」「清空」都走这里。
  function 清空编辑() {
    置文本(编辑, "");
    写状态(取("工具状态"), "已清空（0 字符）", true);
    return "已清空（0 字符）";
  }

  取("载入按钮").addEventListener("click", 载入示例);
  取("清空按钮").addEventListener("click", 清空编辑);

  刷();
  return { 编辑, 刷, 载入示例, 清空: 清空编辑 };
}
