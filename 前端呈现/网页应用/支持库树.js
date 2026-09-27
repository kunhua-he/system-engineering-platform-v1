// 支持库树 —— 左栏那棵组件箱。**叶子全部来自实时应答，枝干来自号段抄件。**
//
// 参考图左栏是「系统核心支持库」下面挂一长串支持库名；那是**易语言的**支持库。
// 本页摆**我们自身的**：叶子是 `GET /接口` 此刻回的全部能力（编号与名称都实时取，本页不抄一个），
// 按**号段层级**组织成树 —— 号段（`契约声明/号段图.json`）→ 扩展（各扩展的 `包声明.json`）
// → 能力（`GET /接口` 的实时应答）。三层分别对应平台的「支持库 / 模块 / 技能」那套说法。
//
// 为什么枝干不抄：`GET /接口/扩展`（§七 端点）直接回「哪个扩展占哪段号」，
// 前端实时取即可（`号段表.js` 的 `拉扩展表()`）。以前抄成常量，代价是加一个扩展就要改底座
// （README §五 硬边界 2），且底座里出现扩展的名字本身就破硬边界 1 ⇒ 判据 ⑯ 守着这条。
// 号段骨架（`契约声明/号段图.json`）仍是抄件：那是**底座自身的**布局声明，且没有对应端点。
//
// 本件只做两件事：把三层摆成 DOM · 点一片叶子就**真调**一次 `GET /接口/能力/<编号>`。
// 没有一处写着「这个编号合不合法」——发出去，后端说了算。

import { 取根 } from "./取接口.js";
import { 建元素, 清空, 写状态 } from "./呈现.js";
import { 号段, 找段, 找扩展, 拉扩展表 } from "./号段表.js";
import { 画图标 } from "./图标.js";

/** 从 `GET /接口` 的应答里取能力清单。键名 `能力` 是冻结的返回体形状（`接口面形状.md` §二）。 */
function 取能力表(应答体) {
  if (应答体 && typeof 应答体 === "object" && Array.isArray(应答体.能力)) return 应答体.能力;
  return [];
}

/**
 * 把扁平的能力表折成「号段 → 扩展 → 能力」三层。
 * 折法是**照扩展清单比对编号**，不是猜：编号落在哪个扩展申报的号段里，就归那个扩展
 * （扩展名与号段都来自 `GET /接口/扩展` 的实时应答，本页不写任何一个名字）。
 */
function 折树(能力表) {
  const 枝 = new Map();
  for (const 段 of 号段) 枝.set(段.名, { 段, 扩: new Map(), 直挂: [] });
  for (const 能 of 能力表) {
    const 编号 = Number(能.编号);
    const 段 = 找段(编号);
    if (!段) continue;
    const 槽 = 枝.get(段.名);
    const 扩 = 找扩展(编号);
    if (扩) {
      if (!槽.扩.has(扩.名)) 槽.扩.set(扩.名, { 扩, 能: [] });
      槽.扩.get(扩.名).能.push(能);
    } else {
      槽.直挂.push(能);
    }
  }
  return 枝;
}

function 种类说明(种类) {
  if (种类 === "支持库") return "支持库：随扩展根载入的原子能力（1xxx–6xxx）";
  if (种类 === "模块") return "模块：组合件（7xxx）";
  return "技能：一份用法说明，不含实现（8xxx）";
}

export function 装支持库树(取元素, 钩子) {
  const 容器 = 取元素("支持库树");
  const 状态 = 取元素("树状态");
  let 选中行 = null;

  /** 一行：缩进 + 折标 + 小图 + 文字 +（可选）条数。 */
  function 建行(深度, 名称, 图名, 折标, 尾巴, 类名) {
    const 行 = 建元素("div", "树行" + (类名 ? " " + 类名 : ""));
    行.style.paddingLeft = 2 + 深度 * 12 + "px";
    行.append(建元素("span", "折标", 折标 || ""));
    const 图槽 = 建元素("span", "图槽");
    图槽.append(画图标(图名));
    行.append(图槽);
    行.append(建元素("span", null, 名称));
    if (尾巴) 行.append(建元素("span", "多", " " + 尾巴));
    return 行;
  }

  /**
   * 把一行接成「可折的枝」：点它（或 Enter / 空格）就把它的子盒收起来、再点放出来。
   *
   * 为什么必须接上：这一行画了 `▾` 却点不动，就是**空响的指示符** —— 指示符是给用户看的承诺，
   * 承诺了「这里能收放」就得真能收放。段行、扩展行、根行三处都走这一条。
   */
  function 接折(源码行, 容器盒) {
    const 标 = 源码行.querySelector(".折标");
    const 翻 = () => {
      const 收 = !容器盒.hidden;
      容器盒.hidden = 收;
      标.textContent = 收 ? "▸" : "▾";
      源码行.setAttribute("aria-expanded", 收 ? "false" : "true");
    };
    源码行.classList.add("枝");
    源码行.tabIndex = 0;
    源码行.setAttribute("role", "button");
    源码行.setAttribute("aria-expanded", "true");
    源码行.addEventListener("click", 翻);
    源码行.addEventListener("keydown", (事件) => {
      if (事件.key === "Enter" || 事件.key === " ") {
        事件.preventDefault();
        翻();
      }
    });
  }

  function 建叶(深度, 能力) {
    const 编号 = Number(能力.编号);
    const 行 = 建行(深度, 编号 + " " + String(能力.名称), "能力", "", null, "叶");
    行.title = "点一下：真调 GET /接口/能力/" + 编号
      + "（参数 " + 能力.参数个数 + " 个 · 返回类型 " + 能力.返回类型 + "）";
    行.addEventListener("click", () => 点叶(行, 编号));
    return 行;
  }

  /** 点一片叶子：真调一次契约端点，读数落到「搜寻2」那一格。 */
  async function 点叶(源码行, 编号) {
    if (选中行) 选中行.classList.remove("选");
    选中行 = 源码行;
    源码行.classList.add("选");
    取元素("契约编号").value = String(编号);
    钩子.切页签("搜寻2");
    await 钩子.取契约(String(编号));
  }

  function 摆能力树(能力表) {
    const 枝 = 折树(能力表);
    清空(容器);
    let 总 = 0;
    const 根盒 = 建元素("div", "树子");
    for (const 段 of 号段) {
      const 槽 = 枝.get(段.名);
      const 条数 = 槽.直挂.length + [...槽.扩.values()].reduce((累加和, 一项) => 累加和 + 一项.能.length, 0);
      总 += 条数;
      const 段行 = 建行(0, 段.名 + "（" + 段.起 + "–" + 段.止 + "）", "段",
        条数 ? "▾" : "", 条数 + " 条");
      段行.title = 段.注;
      根盒.append(段行);
      if (!条数) continue;
      const 段盒 = 建元素("div", "树子");
      for (const 项 of 槽.扩.values()) {
        const 扩行 = 建行(1, 项.扩.名 + "（" + 项.扩.起 + "–" + 项.扩.止 + "）", "模块",
          "▾", 项.能.length + " 条");
        扩行.title = 种类说明(项.扩.种类);
        const 扩盒 = 建元素("div", "树子");
        for (const 能 of 项.能) 扩盒.append(建叶(2, 能));
        接折(扩行, 扩盒);
        段盒.append(扩行);
        段盒.append(扩盒);
      }
      for (const 能 of 槽.直挂) 段盒.append(建叶(1, 能));
      接折(段行, 段盒);
      根盒.append(段盒);
    }
    const 根行 = 建行(0, "平台扩展树", "组件", "▾", "共 " + 总 + " 条能力");
    接折(根行, 根盒);
    容器.append(根行);
    容器.append(根盒);
    写状态(状态, "GET /接口 回了 " + 能力表.length + " 条能力 · 按号段表折成 "
      + 号段.filter((号段) => 枝.get(号段.名).直挂.length
        || [...枝.get(号段.名).扩.values()].length).length + " 段有内容 / 共 " + 号段.length + " 段");
  }

  /** 拉一次清单，摆树。返回应答（好让别的格子复用同一次读数）。 */
  async function 拉清单() {
    写状态(状态, "取清单中…");
    try {
      const 应答 = await 取根();
      if (应答.状态 !== 200) {
        清空(容器);
        写状态(状态, "HTTP " + 应答.状态 + " —— 同源托管没把 /接口 交出来，树摆不出来", false);
        return null;
      }
      // 扩展分组**实时取**（判据 ⑯：底座不许点名扩展）。取不到就摆成「没有扩展这一层」，
      // 不拦着能力树 —— 那正是扩展缺了时底座该有的样子（README §五 硬边界 3）。
      await 拉扩展表();
      const 能力表 = 取能力表(应答.体);
      if (!能力表.length) {
        清空(容器);
        写状态(状态, "应答里没有能力清单（顶层键："
          + (应答.体 && typeof 应答.体 === "object" ? Object.keys(应答.体).join(" · ") : "不是对象")
          + "）", false);
        return null;
      }
      摆能力树(能力表);
      return 应答;
    } catch (错) {
      清空(容器);
      写状态(状态, "发不出去：" + 错.message, false);
      return null;
    }
  }

  return { 拉清单 };
}
