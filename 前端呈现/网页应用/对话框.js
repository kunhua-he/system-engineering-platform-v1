// 对话框 —— 判定「进前端」的那 18 个，照 `对话框表.js` 逐控件摆出来。
//
// 判据：`项目文档/设计文档/界面实测.md` §三（56/56 资源、606/606 控件全解）与 §十
// （「对话框布局能 1:1 复刻」）。进哪 18 个、不进哪 38 个及各自的依据，写在 `前端呈现/说明.md`。
//
// 坐标单位是**对话框单位**（DLU，资源里就是它）。本文件按 1 单位 = 1 像素摆，不做像素折换
// —— 折换系数要 Windows 下 `宋体 9pt` 的字体度量，本平台量不到（见 `说明.md` 的缺口一节）。
// 控件只摆样子、不接动作：它是「资源里长什么样」的读数，不是能用的对话框。

import { 对话框 } from "./对话框表.js";

// 预定义控件序数已由取证脚本解成类名，这里只给每个类一个外观类。
const 类样式 = { BUTTON: "钮", EDIT: "编", STATIC: "静", LISTBOX: "列", COMBOBOX: "组" };

export function 装对话框(取) {
  const 选 = 取("对话框选");
  const 台 = 取("对话框台");
  const 读 = 取("对话框读数");

  for (const d of 对话框) {
    const 项 = document.createElement("option");
    项.value = d.编号;
    项.textContent = d.编号 + " · " + d.标题 + "（" + d.控件数 + " 控件）";
    选.append(项);
  }

  const 摆 = (编号) => {
    const d = 对话框.find((x) => x.编号 === 编号);
    const 框 = document.createElement("div");
    框.className = "易对话框";
    框.style.width = d.cx + "px";
    框.style.height = d.cy + "px";
    // 字号照资源的「字号」字段给；**字体族不在这里给** —— 进前端的这 18 个全是「宋体」，
    // 族链（宋体 → SimSun → Songti SC）只在 `样式.css` 里写一份，两处写就是两个来源。
    // 实测过：这里写 `fontFamily = "宋体"` 会在 macOS 上落到默认族（量到 PingFang SC），
    // 因为本机没有叫「宋体」的字面；走 CSS 那条链才会落到 Songti SC。资源的字体名照旧显示在读数里。
    框.style.fontSize = d.字号 + "pt";
    for (const c of d.控件) {
      const 控 = document.createElement("div");
      控.className = "易控件 " + (类样式[c.类] || "他") + (c.禁用 ? " 灰" : "");
      控.style.left = c.x + "px";
      控.style.top = c.y + "px";
      控.style.width = c.cx + "px";
      控.style.height = c.cy + "px";
      控.textContent = c.标题;
      控.title = "类 " + c.类 + " · id " + c.id + " · 样式 " + c.样式
        + (c.禁用 ? " · WS_DISABLED" : "");
      框.append(控);
    }
    台.replaceChildren(框);
    读.textContent = "对话框 " + d.编号 + " · " + d.标题 + " · 字体 " + d.字体 + " " + d.字号
      + "pt · 尺寸 " + d.cx + "×" + d.cy + " 对话框单位 · 控件 " + d.控件数
      + " · 可达命令 " + d.依据 + " · 只摆样子，未接动作";
  };

  选.addEventListener("change", () => 摆(选.value));
  摆(对话框[0].编号);
}
