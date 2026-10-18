// 对话框 —— 判定「进前端」的那 18 个，照 `对话框表.js` 逐控件摆出来。
//
// 判据：`项目文档/设计文档/界面实测.md` §三（56/56 资源、606/606 控件全解）与 §十
// （「对话框布局能 1:1 复刻」）。进哪 18 个、不进哪 38 个及各自的依据，写在 `前端呈现/说明.md`。
//
// 坐标单位是**对话框单位**（DLU，资源里就是它）。本文件按 1 单位 = 1 像素摆，不做像素折换
// —— 折换系数要 Windows 下 `宋体 9pt` 的字体度量，本平台量不到（见 `说明.md` 的缺口一节）。
// 控件只摆样子、不接动作：它是「资源里长什么样」的读数，不是能用的对话框。

import { 对话框 } from "../对话框表.js";

// 预定义控件序数已由取证脚本解成类名，这里只给每个类一个外观类。
const 类样式 = { BUTTON: "钮", EDIT: "编", STATIC: "静", LISTBOX: "列", COMBOBOX: "组" };

export function 装对话框(取元素) {
  const 选中 = 取元素("对话框选");
  const 台容器 = 取元素("对话框台");
  const 读数元素 = 取元素("对话框读数");

  for (const 对话框项 of 对话框) {
    const 选项元素 = document.createElement("option");
    选项元素.value = 对话框项.编号;
    选项元素.textContent = 对话框项.编号 + " · " + 对话框项.标题 + "（" + 对话框项.控件数 + " 控件）";
    选中.append(选项元素);
  }

  const 摆对话框 = (编号) => {
    const 对话框项 = 对话框.find((候选项) => 候选项.编号 === 编号);
    const 对话框件 = document.createElement("div");
    对话框件.className = "易对话框";
    对话框件.style.width = 对话框项.cx + "px";
    对话框件.style.height = 对话框项.cy + "px";
    // 字号照资源的「字号」字段给；**字体族不在这里给** —— 进前端的这 18 个全是「宋体」，
    // 族链（宋体 → SimSun → Songti SC）只在 `页面样式.css` 里写一份，两处写就是两个来源。
    // 实测过：这里写 `fontFamily = "宋体"` 会在 macOS 上落到默认族（量到 PingFang SC），
    // 因为本机没有叫「宋体」的字面；走 CSS 那条链才会落到 Songti SC。资源的字体名照旧显示在读数里。
    对话框件.style.fontSize = 对话框项.字号 + "pt";
    for (const 控项 of 对话框项.控件) {
      const 控件件 = document.createElement("div");
      控件件.className = "易控件 " + (类样式[控项.控件类] || "他") + (控项.禁用 ? " 灰" : "");
      控件件.style.left = 控项.左边距 + "px";
      控件件.style.top = 控项.上 + "px";
      控件件.style.width = 控项.cx + "px";
      控件件.style.height = 控项.cy + "px";
      控件件.textContent = 控项.标题;
      控件件.title = "类 " + 控项.控件类 + " · id " + 控项.id + " · 样式 " + 控项.控件样式
        + (控项.禁用 ? " · WS_DISABLED" : "");
      对话框件.append(控件件);
    }
    台容器.replaceChildren(对话框件);
    读数元素.textContent = "对话框 " + 对话框项.编号 + " · " + 对话框项.标题 + " · 字体 " + 对话框项.字体 + " " + 对话框项.字号
      + "pt · 尺寸 " + 对话框项.cx + "×" + 对话框项.cy + " 对话框单位 · 控件 " + 对话框项.控件数
      + " · 可达命令 " + 对话框项.命令依据 + " · 只摆样子，未接动作";
  };

  选中.addEventListener("change", () => 摆对话框(选中.value));
  摆对话框(对话框[0].编号);
}
