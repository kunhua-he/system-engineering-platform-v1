// 菜单栏 —— 照 `菜单表.js` 的树摆 DOM：10 个顶层弹出 / 181 项，1:1 取自 `e.exe` 的菜单资源 127。
//
// 判据：`项目文档/设计文档/界面实测.md` §十「菜单结构能 1:1 复刻」。
// 本文件只做两件事：照数据摆 DOM（含子层 · 分隔线 · 灰化项 · 快捷键文本）· 点一下写一条**真实读数**。
//
// 为什么不是「每个菜单项都能用」：命令的实现不在资源里 —— 资源里只有 id 与文字，
// 没有 id → 命令 的映射表（`界面实测.md` §八 第 4 条：那张表在 `.text` 里）。
// 所以只有**平台真有端点**的那一族接线：编译族 12 个 id 通向同一条编译动作，
// 走的是 `GET /接口` **实时给的**那条链（链上有哪几步、各叫什么、编号几，本文件一个字都不写）。
// 其余 169 项点了**问后端**：`POST /接口/运维/菜单命令`（§七 运维端点），把后端的**结构化回执**
// 原样摆出来 —— 此刻后端一律回 `9001 端点未实现`（命令没有后端落点），本页**如实显示**，
// 不自行编一句「未接线」、不假装成功。

import { 主菜单 } from "../菜单表.js";
import { 跑编译 } from "../编译调试/编译.js";
import { 发菜单命令 } from "../接口请求/请求客户端.js";
import { 摆应答, 摆消息, 清空容器, 取应答摘要, 写状态 } from "./呈现.js";
import { 记流水 } from "../交互编辑/剪辑历史.js";

const 编译族 = new Set(["0x8053", "0x8090", "0x808f", "0x80d4",
  "0x80d9", "0x80da", "0x80db", "0x80dc", "0x80e1", "0x80e4", "0x80e5", "0x808d"]);

/** 助记字加下划线：`&` 只是标记，资源里真正显示的是「下一个字带下划线」。 */
function 摆文字(菜单项) {
  const 容器盒 = document.createElement("span");
  if (菜单项.助记位 < 0) {
    容器盒.textContent = 菜单项.菜单文字;
    return 容器盒;
  }
  容器盒.append(菜单项.菜单文字.slice(0, 菜单项.助记位));
  const 下划线 = document.createElement("u");
  下划线.textContent = 菜单项.菜单文字[菜单项.助记位];
  容器盒.append(下划线, 菜单项.菜单文字.slice(菜单项.助记位 + 1));
  return 容器盒;
}

export function 装菜单栏(取元素, 编辑, 依赖 = {}) {
  const 菜单栏 = 取元素("易菜单栏");
  // 菜单读数原来住「中带」，现在住最底下那条状态条（参考图 y=742..754 那一条）。
  const 菜单状态条 = 取元素("条_菜单");
  const 切页签 = 依赖.切页签;
  let 开着的 = null;

  const 报状态 = (源文本, 颜色) => {
    菜单状态条.textContent = 源文本;
    菜单状态条.className = "格" + (颜色 === "好" ? " 好" : 颜色 === "坏" ? " 坏" : "");
  };

  const 合上 = () => {
    if (!开着的) return;
    开着的.下拉盒.hidden = true;
    开着的.按钮.setAttribute("aria-expanded", "false");
    开着的 = null;
  };

  /**
   * 非编译族：把命令编号发去 `POST /接口/运维/菜单命令`，把结构化回执摆到「提示」栏。
   * 本页**不预判**这条命令落没落 —— 后端此刻一律回 `9001`，将来落了地本页不用改一行。
   */
  const 问后端 = async (菜单项, 头部) => {
    const 状态 = 取元素("菜单命令状态");
    const 结果盒 = 取元素("菜单命令果");
    if (切页签) 切页签("提示");
    if (!状态 || !结果盒) {
      报状态(头部 + " · 回执区不在页面上（缺 id：菜单命令状态 / 菜单命令果）", "坏");
      return;
    }
    清空容器(结果盒);
    写状态(状态, "问后端 " + 菜单项.编号 + " …");
    try {
      const 造应答 = await 发菜单命令(菜单项.编号);
      摆应答(结果盒, 造应答);
      const 摘要结果 = 取应答摘要(造应答.报文体);
      写状态(状态, "命令 " + 菜单项.编号 + " · HTTP " + 造应答.状态 + " · " + 摘要结果.状态词,
        摘要结果.判定档 === "好" ? true : 摘要结果.判定档 === "坏" ? false : undefined);
      报状态(头部 + " · 已问后端（POST /接口/运维/菜单命令）：HTTP " + 造应答.状态 + " · " + 摘要结果.状态词
        + " —— 结构化回执见「提示」栏", 摘要结果.判定档 === "好" ? "好" : "坏");
      记流水("菜单", 头部 + " · HTTP " + 造应答.状态 + " · " + 摘要结果.状态词);
    } catch (错误) {
      摆消息(结果盒, "发不出去：" + 错误.message);
      写状态(状态, "发不出去", false);
      报状态(头部 + " · 发不出去：" + 错误.message, "坏");
    }
  };

  const 点叶子 = (菜单项) => {
    合上();
    const 头部 = "命令 " + 菜单项.编号 + " · " + 菜单项.菜单文字 + (菜单项.快捷键 ? " " + 菜单项.快捷键 : "");
    if (编译族.has(菜单项.编号)) {
      报状态(头部 + " · 已接线：真调 `GET /接口` 实时给的编译链（逐级读数见「提示」栏）", "好");
      跑编译(取元素, 编辑);
      return;
    }
    问后端(菜单项, 头部);
  };

  const 摆层 = (项表, 深度) => {
    const 容器盒 = document.createElement("div");
    容器盒.className = "易弹出";
    容器盒.hidden = true;
    for (const 菜单项 of 项表) {
      if (菜单项.分隔) {
        const 分隔件 = document.createElement("div");
        分隔件.className = "易分隔";
        容器盒.append(分隔件);
        continue;
      }
      const 源码行 = document.createElement("div");
      源码行.className = "易项" + (菜单项.灰化 ? " 灰" : "");
      源码行.append(摆文字(菜单项));
      if (菜单项.子项) {
        const 箭头 = document.createElement("span");
        箭头.className = "角";
        箭头.textContent = "▸";
        const 子层 = 摆层(菜单项.子项, 深度 + 1);
        源码行.append(箭头, 子层);
        源码行.addEventListener("mouseenter", () => { 子层.hidden = false; });
        源码行.addEventListener("mouseleave", () => { 子层.hidden = true; });
      } else {
        if (菜单项.快捷键) {
          const 键名 = document.createElement("span");
          键名.className = "键";
          键名.textContent = 菜单项.快捷键;
          源码行.append(键名);
        }
        if (菜单项.灰化) {
          // 资源里带 MF_GRAYED 位：照它的做派，灰化项点不动（不是「点了没反应」，是禁用项）。
          源码行.setAttribute("aria-disabled", "true");
          源码行.title = "资源里带 MF_GRAYED 位（实测 181 项里只有这一项）—— 在易语言里也是点不动的";
        } else {
          源码行.addEventListener("click", (界面事件) => { 界面事件.stopPropagation(); 点叶子(菜单项); });
        }
      }
      容器盒.append(源码行);
    }
    return 容器盒;
  };

  for (const 顶层 of 主菜单) {
    const 按钮 = document.createElement("button");
    按钮.type = "button";
    按钮.className = "易顶层";
    按钮.append(摆文字(顶层));
    按钮.setAttribute("aria-expanded", "false");
    const 容器盒 = 摆层(顶层.子项, 0);
    按钮.addEventListener("click", (界面事件) => {
      界面事件.stopPropagation();
      if (开着的 && 开着的.按钮 === 按钮) { 合上(); return; }
      合上();
      容器盒.hidden = false;
      按钮.setAttribute("aria-expanded", "true");
      开着的 = { 下拉盒: 容器盒, 按钮: 按钮 };
    });
    按钮.addEventListener("mouseenter", () => { if (开着的 && 开着的.按钮 !== 按钮) 按钮.click(); });
    const 顶层包 = document.createElement("div");
    顶层包.className = "易顶层包";
    顶层包.append(按钮, 容器盒);
    菜单栏.append(顶层包);
  }

  document.addEventListener("click", 合上);
  document.addEventListener("keydown", (界面事件) => { if (界面事件.key === "Escape") 合上(); });

  报状态("菜单结构 1:1 取自 e.exe 菜单资源 127（10 个顶层弹出 / 181 项）· 已接线 "
    + 编译族.size + " 项（编译族）· 其余点了问后端（POST /接口/运维/菜单命令）取结构化回执");
}
