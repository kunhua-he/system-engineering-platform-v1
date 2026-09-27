// 底部页签 —— 那 8 个格子的名字与切换。
//
// 名字**逐字照抄参考图**（`提示 · 输出 · 调用表 · 监视表 · 变量表 · 搜寻1 · 搜寻2 · 剪辑历史`）——
// 它们是易语言主窗体底部的固定页签，属「资源里的形状」那一类，照抄不算抄业务。
// **内容全部是我们的**：每一格装的是本平台四个冻结端点的真读数（见 index.html 里那 8 个 `底格`）。
//
// 这一条同 `菜单表.js` 的做派：抄形状、不抄业务。改一格内容只需改 index.html 与对应的 .js，
// 本件一行不动。

import { 建元素 } from "./呈现.js";
import { 画图标 } from "./图标.js";

/** 页签名 → 它对应的 `底格` 的 id。行序＝参考图里那一排从左到右的次序。 */
export const 页签表 = [
  ["提示", "底格_提示"],
  ["输出", "底格_输出"],
  ["调用表", "底格_调用表"],
  ["监视表", "底格_监视表"],
  ["变量表", "底格_变量表"],
  ["搜寻1", "底格_搜寻1"],
  ["搜寻2", "底格_搜寻2"],
  ["剪辑历史", "底格_剪辑历史"],
];

/**
 * 页签名 → 它前面那个小图：图形名与页签名**同名**，所以不另立一张映射表
 * （少一张表就少一处会分叉的地方）。图形本身在 `图标.js`，是**替代图形，非抄件**。
 */
export function 装底页签() {
  const 带 = document.getElementById("底页签带");
  const 体 = document.getElementById("页签体");
  const 钮表 = new Map();

  function 切页签(名) {
    for (const [格名, 钮] of 钮表) {
      const 选 = 格名 === 名;
      钮.classList.toggle("选", 选);
      钮.setAttribute("aria-selected", 选 ? "true" : "false");
    }
    for (const [, id] of 页签表) {
      const 格 = document.getElementById(id);
      if (格) 格.classList.toggle("选", id === 页签表.find(([格名]) => 格名 === 名)[1]);
    }
    体.scrollTop = 0;
  }

  for (const [名, id] of 页签表) {
    const 钮 = 建元素("button", "页签");
    钮.type = "button";
    // 参考图那排页签每格前面都有一个小图，所以这里也摆一个（图形名与页签名同名）。
    钮.append(画图标(名));
    钮.append(建元素("span", null, 名));
    钮.setAttribute("aria-selected", "false");
    钮.addEventListener("click", () => 切页签(名));
    带.append(钮);
    钮表.set(名, 钮);
  }

  切页签("提示");
  return { 切页签 };
}
