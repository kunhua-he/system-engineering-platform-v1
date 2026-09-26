// 菜单栏 —— 照 `菜单表.js` 的树摆 DOM：10 个顶层弹出 / 181 项，1:1 取自 `e.exe` 的菜单资源 127。
//
// 判据：`项目文档/设计文档/界面实测.md` §十「菜单结构能 1:1 复刻」。
// 本文件只做两件事：照数据摆 DOM（含子层 · 分隔线 · 灰化项 · 快捷键文本）· 点一下写一条**真实读数**。
//
// 为什么不是「每个菜单项都能用」：命令的实现不在资源里 —— 资源里只有 id 与文字，
// 没有 id → 命令 的映射表（`界面实测.md` §八 第 4 条：那张表在 `.text` 里）。
// 所以只有**平台真有端点**的那一族接线：编译族 12 个 id 通向同一条编译动作，
// 走的是 `GET /接口` **实时给的**那条链（链上有哪几步、各叫什么、编号几，本文件一个字都不写）。
// 其余 169 项点了写「未接线 + 死在哪一步」，不做假按钮。

import { 主菜单 } from "./菜单表.js";
import { 跑编译 } from "./编译.js";

const 编译族 = new Set(["0x8053", "0x8090", "0x808f", "0x80d4",
  "0x80d9", "0x80da", "0x80db", "0x80dc", "0x80e1", "0x80e4", "0x80e5", "0x808d"]);

/** 助记字加下划线：`&` 只是标记，资源里真正显示的是「下一个字带下划线」。 */
function 摆文字(项) {
  const 盒 = document.createElement("span");
  if (项.助记位 < 0) {
    盒.textContent = 项.文字;
    return 盒;
  }
  盒.append(项.文字.slice(0, 项.助记位));
  const 下 = document.createElement("u");
  下.textContent = 项.文字[项.助记位];
  盒.append(下, 项.文字.slice(项.助记位 + 1));
  return 盒;
}

export function 装菜单栏(取, 编辑) {
  const 栏 = 取("易菜单栏");
  // 菜单读数原来住「中带」，现在住最底下那条状态条（参考图 y=742..754 那一条）。
  const 条 = 取("条_菜单");
  let 开着的 = null;

  const 报 = (文, 色) => {
    条.textContent = 文;
    条.className = "格" + (色 === "好" ? " 好" : 色 === "坏" ? " 坏" : "");
  };

  const 合上 = () => {
    if (!开着的) return;
    开着的.盒.hidden = true;
    开着的.钮.setAttribute("aria-expanded", "false");
    开着的 = null;
  };

  const 点叶子 = (项) => {
    合上();
    const 头 = "命令 " + 项.编号 + " · " + 项.文字 + (项.快捷键 ? " " + 项.快捷键 : "");
    if (编译族.has(项.编号)) {
      报(头 + " · 已接线：真调 `GET /接口` 实时给的编译链（逐级读数见「提示」栏）", "好");
      跑编译(取, 编辑);
      return;
    }
    报(头 + " · 未接线 —— 死在这一步：本前端只有四个冻结端点（外加 §七 的工具族旁路），没有这条命令的路；"
      + "命令实现不在资源里（`界面实测.md` §八 第 4 条：id → 命令 的映射表在 .text）", "警");
  };

  const 摆层 = (项表, 深度) => {
    const 盒 = document.createElement("div");
    盒.className = "易弹出";
    盒.hidden = true;
    for (const 项 of 项表) {
      if (项.分隔) {
        const 隔 = document.createElement("div");
        隔.className = "易分隔";
        盒.append(隔);
        continue;
      }
      const 行 = document.createElement("div");
      行.className = "易项" + (项.灰化 ? " 灰" : "");
      行.append(摆文字(项));
      if (项.项) {
        const 角 = document.createElement("span");
        角.className = "角";
        角.textContent = "▸";
        const 子 = 摆层(项.项, 深度 + 1);
        行.append(角, 子);
        行.addEventListener("mouseenter", () => { 子.hidden = false; });
        行.addEventListener("mouseleave", () => { 子.hidden = true; });
      } else {
        if (项.快捷键) {
          const 键 = document.createElement("span");
          键.className = "键";
          键.textContent = 项.快捷键;
          行.append(键);
        }
        if (项.灰化) {
          // 资源里带 MF_GRAYED 位：照它的做派，灰化项点不动（不是「点了没反应」，是禁用项）。
          行.setAttribute("aria-disabled", "true");
          行.title = "资源里带 MF_GRAYED 位（实测 181 项里只有这一项）—— 在易语言里也是点不动的";
        } else {
          行.addEventListener("click", (e) => { e.stopPropagation(); 点叶子(项); });
        }
      }
      盒.append(行);
    }
    return 盒;
  };

  for (const 顶层 of 主菜单) {
    const 钮 = document.createElement("button");
    钮.type = "button";
    钮.className = "易顶层";
    钮.append(摆文字(顶层));
    钮.setAttribute("aria-expanded", "false");
    const 盒 = 摆层(顶层.项, 0);
    钮.addEventListener("click", (e) => {
      e.stopPropagation();
      if (开着的 && 开着的.钮 === 钮) { 合上(); return; }
      合上();
      盒.hidden = false;
      钮.setAttribute("aria-expanded", "true");
      开着的 = { 盒, 钮 };
    });
    钮.addEventListener("mouseenter", () => { if (开着的 && 开着的.钮 !== 钮) 钮.click(); });
    const 包 = document.createElement("div");
    包.className = "易顶层包";
    包.append(钮, 盒);
    栏.append(包);
  }

  document.addEventListener("click", 合上);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") 合上(); });

  报("菜单结构 1:1 取自 e.exe 菜单资源 127（10 个顶层弹出 / 181 项）· 已接线 "
    + 编译族.size + " 项（编译族）· 其余点了写「未接线」");
}
