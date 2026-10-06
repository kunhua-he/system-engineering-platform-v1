// 工具栏 —— 菜单栏下面那一条图标行（截图 y=59..127 的上半，图标自 x=12 起）。
//
// 参考图那一条上是「新建 / 打开 / 保存」这一类图标钮。本页照那个做派摆一排，
// 但**每一个钮点下去都必须有真读数**（硬要求 1：不许假成功）。所以：
//   · 有端点可调的（编译 · 诊断 · 取清单）→ 真调，读数进对应页签；
//   · 纯编辑器动作的（剪切 · 复制 · 粘贴 · 撤销 · 重做 · 新建 · 清空）→ 真做 DOM 动作，报真结果；
//   · **保存 → 真写盘**：经 §七 的 `POST /接口/程序文本` 写到「载入示例」选中的那份路径
//     （裁决定落点 = 调用方自带路径）；没选带路径的语料就如实报「没有落点」，不假装存了。
//
// 图标是内联 SVG（`图标.js`），不是位图 —— 位图在 e.exe 资源里是索引不是像素，本页量不到。

import { 建元素, 取应答摘要, 写状态 } from "./呈现.js";
import { 画图标 } from "./图标.js";
import { 选中路径 } from "./编辑器.js";
import { 发程序文本 } from "./取接口.js";

/**
 * 钮表：`[图标名, 提示语, 动作名]`，`null` 表示插一条竖分隔。
 * 行序＝参考图那一条从左到右的次序。
 */
export const 钮表 = [
  ["新建图", "新建：清空编辑区", "新建件"],
  ["打开", "打开：经 POST /接口/程序文本 真读「载入示例」选中的那份路径（没选路径则载入内置模板）", "打开"],
  ["保存", "保存：把编辑区文本经 POST /接口/程序文本 写到「载入示例」选中的那份路径", "保存"],
  null,
  ["剪切", "剪切：把选中文本剪到系统剪贴板", "剪切"],
  ["复制", "复制：把选中文本拷到系统剪贴板", "复制"],
  ["粘贴", "粘贴：把系统剪贴板文本插到光标处", "粘贴"],
  ["撤销", "撤销：编辑区回退一步", "撤销"],
  ["重做", "重做：编辑区重做一步", "重做"],
  null,
  ["查找", "查找：真调 GET /接口，能力清单落到「搜寻1」", "查找"],
  ["编译执行", "编译：把编辑区的文本按 GET /接口 给的链逐级送一遍（链上有哪几步、各叫什么，都实时取）", "编译执行"],
  ["诊断", "诊断：单独调链末一步（此刻是「诊断」，名字取自端点），读数落到「提示」", "诊断"],
  ["清空", "清空：把编辑区清空", "清空"],
  null,
  ["视图", "切换代码视图 / 窗口设计视图", "视图"],
];

export function 装工具栏(取元素, 钩子) {
  const 源码行 = 取元素("图标行");
  const 状态 = 取元素("工具状态");

  const 报状态 = (源文本, 是否好) => {
    写状态(状态, 源文本, 是否好);
    钩子.记流水("工具条", 源文本);
  };

  /** 真剪贴板：`navigator.clipboard` 要安全上下文；被挡就把原因原样报出来，不吞。 */
  async function 进剪贴板(源文本, 动作) {
    try {
      await navigator.clipboard.writeText(源文本);
      报状态(动作 + "：" + 源文本.length + " 字符已进系统剪贴板", true);
    } catch (错误) {
      报状态(动作 + "：系统剪贴板不给写（" + 错误.name + "）—— 页面不是安全上下文，或被权限挡了", false);
    }
  }

  const 动作 = {
    新建件() {
      钩子.清空();
      报状态("新建：编辑区已清空（0 字符）", true);
    },
    async 打开() {
      await 钩子.载入示例();
    },
    async 保存() {
      const 路径 = 选中路径(取元素("示例选"));
      if (!路径) {
        报状态("保存：先在「载入示例」里选一份**带路径**的语料 —— 内置模板没有落点，写不了"
          + "（裁决定「程序文本落在哪」由调用方给路径，本页不猜）。", false);
        return;
      }
      const 造应答 = await 发程序文本("写", 路径, 钩子.编辑.value);
      const 摘要结果 = 取应答摘要(造应答.体);
      if (摘要结果.判定档 === "好") {
        报状态("保存：已写入 " + 路径 + "（" + 钩子.编辑.value.length + " 字符）", true);
      } else {
        const 错误码 = 造应答.体 && 造应答.体.错误 && 造应答.体.错误.码;
        报状态("保存：写不进去 —— HTTP " + 造应答.状态 + (错误码 === undefined ? "" : " · 码 " + 错误码)
          + "（真读数，不是本页编的）", false);
      }
    },
    剪切() {
      const 编辑 = 钩子.编辑;
      const 源文本 = 编辑.value.slice(编辑.selectionStart, 编辑.selectionEnd);
      if (!源文本) { 报状态("剪切：没有选中文本（选区 0 字符）", false); return; }
      编辑.setRangeText("", 编辑.selectionStart, 编辑.selectionEnd, "start");
      编辑.dispatchEvent(new Event("input"));
      进剪贴板(源文本, "剪切");
    },
    复制() {
      const 编辑 = 钩子.编辑;
      const 源文本 = 编辑.value.slice(编辑.selectionStart, 编辑.selectionEnd);
      if (!源文本) { 报状态("复制：没有选中文本（选区 0 字符）", false); return; }
      进剪贴板(源文本, "复制");
    },
    async 粘贴() {
      const 编辑 = 钩子.编辑;
      try {
        const 源文本 = await navigator.clipboard.readText();
        编辑.setRangeText(源文本, 编辑.selectionStart, 编辑.selectionEnd, "end");
        编辑.dispatchEvent(new Event("input"));
        报状态("粘贴：" + 源文本.length + " 字符已插入光标处", true);
      } catch (错误) {
        报状态("粘贴：系统剪贴板不给读（" + 错误.name + "）—— 页面不是安全上下文，或被权限挡了", false);
      }
    },
    撤销() {
      const 编辑 = 钩子.编辑;
      编辑.focus();
      const 是否成功 = document.execCommand("undo");
      编辑.dispatchEvent(new Event("input"));
      报状态("撤销：" + (是否成功 ? "编辑区已回退一步（现在 " + 编辑.value.length + " 字符）"
        : "浏览器不给撤销（execCommand 回了 false）"), 是否成功);
    },
    重做() {
      const 编辑 = 钩子.编辑;
      编辑.focus();
      const 是否成功 = document.execCommand("redo");
      编辑.dispatchEvent(new Event("input"));
      报状态("重做：" + (是否成功 ? "编辑区已重做一步（现在 " + 编辑.value.length + " 字符）"
        : "浏览器不给重做（execCommand 回了 false）"), 是否成功);
    },
    async 查找() {
      钩子.切页签("搜寻1");
      报状态("查找：转到「搜寻1」并真调 GET /接口", true);
      await 钩子.取清单();
    },
    async 编译执行() {
      钩子.切页签("提示");
      await 钩子.跑编译();
    },
    async 诊断() {
      钩子.切页签("提示");
      await 钩子.跑诊断();
    },
    清空() {
      钩子.清空();
      报状态("清空：编辑区已清空（0 字符）", true);
    },
    视图() {
      钩子.切视图();
    },
  };

  for (const 钮表项 of 钮表) {
    if (!钮表项) {
      const 分隔件 = 建元素("span", "图标隔");
      源码行.append(分隔件);
      continue;
    }
    const [图名, 提示, 名称] = 钮表项;
    const 按钮 = 建元素("button", "图标钮");
    按钮.type = "button";
    按钮.title = 提示;
    按钮.setAttribute("aria-label", 提示);
    按钮.append(画图标(图名));
    按钮.addEventListener("click", () => {
      const 动作返回 = 动作[名称]();
      if (动作返回 && typeof 动作返回.catch === "function") 动作返回.catch((错误) => 报状态(名称 + "：动作抛了 —— " + 错误.message, false));
    });
    源码行.append(按钮);
  }

  return { 动作 };
}
