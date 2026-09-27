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

export function 装对话框(取元素) {
  const 选 = 取元素("对话框选");
  const 台 = 取元素("对话框台");
  const 读 = 取元素("对话框读数");

  for (const 话 of 对话框) {
    const 项 = document.createElement("option");
    项.value = 话.编号;
    项.textContent = 话.编号 + " · " + 话.标题 + "（" + 话.控件数 + " 控件）";
    选.append(项);
  }

  const 摆 = (编号) => {
    const 话 = 对话框.find((候) => 候.编号 === 编号);
    const 框 = document.createElement("div");
    框.className = "易对话框";
    框.style.width = 话.cx + "px";
    框.style.height = 话.cy + "px";
    // 字号照资源的「字号」字段给；**字体族不在这里给** —— 进前端的这 18 个全是「宋体」，
    // 族链（宋体 → SimSun → Songti SC）只在 `样式.css` 里写一份，两处写就是两个来源。
    // 实测过：这里写 `fontFamily = "宋体"` 会在 macOS 上落到默认族（量到 PingFang SC），
    // 因为本机没有叫「宋体」的字面；走 CSS 那条链才会落到 Songti SC。资源的字体名照旧显示在读数里。
    框.style.fontSize = 话.字号 + "pt";
    for (const 控项 of 话.控件) {
      const 控 = document.createElement("div");
      控.className = "易控件 " + (类样式[控项.类] || "他") + (控项.禁用 ? " 灰" : "");
      控.style.left = 控项.左 + "px";
      控.style.top = 控项.上 + "px";
      控.style.width = 控项.cx + "px";
      控.style.height = 控项.cy + "px";
      控.textContent = 控项.标题;
      控.title = "类 " + 控项.类 + " · id " + 控项.id + " · 样式 " + 控项.样式
        + (控项.禁用 ? " · WS_DISABLED" : "");
      框.append(控);
    }
    台.replaceChildren(框);
    读.textContent = "对话框 " + 话.编号 + " · " + 话.标题 + " · 字体 " + 话.字体 + " " + 话.字号
      + "pt · 尺寸 " + 话.cx + "×" + 话.cy + " 对话框单位 · 控件 " + 话.控件数
      + " · 可达命令 " + 话.依据 + " · 只摆样子，未接动作";
  };

  选.addEventListener("change", () => 摆(选.value));
  摆(对话框[0].编号);
}
