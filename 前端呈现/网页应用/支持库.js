// 支持库 / 能力浏览 —— 把两个只读端点的结果摆清楚。
//
//   `GET /接口`            → 端点表 + 能力全量清单 + 契约版本 + 端口来源   → 「搜寻1」
//   `GET /接口/能力/<编号>` → 单条能力的完整契约：参数表（**行序即契约**）· 返回表 ·
//                            **可抛错误码**（每项带 可重试 / 可自愈 / 需人工）→ 「搜寻2」
//
// 「变量表」那一格也由本件填：同一个应答的**顶层每一个值**按类型摆出来（标量成一行、
// 数组成一张表）。键名与行序都取自应答本身，本件不写死一个字段名。
//
// 摆法一律走 `呈现.js`：不看键名，只看值的类型。所以后端加字段本页不改一行。

import { 取根, 取能力 } from "./取接口.js";
import { 建, 清空, 摆, 摆应答, 摆消息, 写状态 } from "./呈现.js";

/** 顶层每一个值 → 一行读数；是数组就再把整张表摊在它下面。键名照抄应答，不翻译。 */
function 摆变量(容器, 体) {
  清空(容器);
  if (!体 || typeof 体 !== "object" || Array.isArray(体)) {
    容器.append(建("p", "提示 坏", "应答顶层不是对象，摆不出「变量表」。"));
    return;
  }
  for (const 键 of Object.keys(体)) {
    const 值 = 体[键];
    const 行 = 建("div", "行内");
    行.append(建("span", "键", 键 + "："));
    行.append(建("span", "文", Array.isArray(值) ? "表 " + 值.length + " 项"
      : 值 !== null && typeof 值 === "object" ? "对象 " + Object.keys(值).length + " 键"
        : String(值)));
    容器.append(行);
    if (Array.isArray(值)) {
      const 盒 = 建("div", "果");
      摆(盒, 值);
      容器.append(盒);
    }
  }
}

export function 装支持库(取) {
  const 清单果 = 取("清单果");
  const 契约果 = 取("契约果");

  async function 取清单() {
    const 状态 = 取("清单状态");
    const 连 = 取("连接状态");
    写状态(状态, "请求中…");
    try {
      const 应答 = await 取根();
      摆应答(清单果, 应答);
      摆变量(取("变量体"), 应答.体);
      // HTTP 状态只表达「请求本身合不合法」：非 200 说明请求没走到端点（业务失败一律 200）。
      // 所以这里按状态码判「连上了没有」是传输层的事，不是对契约的解释。
      if (应答.状态 === 200) {
        写状态(状态, "已回", true);
        写状态(取("变量状态"), "已回（顶层 " + Object.keys(应答.体 || {}).length + " 个值）", true);
        连.textContent = "网关已回";
        连.className = "状态 好";
        取("条_连接").textContent = "已回";
        取("条_连接").className = "状态 好";
      } else {
        写状态(状态, "HTTP " + 应答.状态, false);
        写状态(取("变量状态"), "HTTP " + 应答.状态, false);
        连.textContent = "网关连不上（HTTP " + 应答.状态 + "）";
        连.className = "状态 坏";
        取("条_连接").textContent = "HTTP " + 应答.状态;
        取("条_连接").className = "状态 坏";
      }
      return 应答;
    } catch (错) {
      摆消息(
        清单果,
        "发不出去：" + 错.message +
        "。本页用同源相对路径调 /接口，所以它必须由接口面同源托管（或由同源反代把 /接口 转给接口面）才调得通。"
      );
      写状态(状态, "失败", false);
      写状态(取("变量状态"), "发不出去", false);
      连.textContent = "网关连不上";
      连.className = "状态 坏";
      取("条_连接").textContent = "连不上";
      取("条_连接").className = "状态 坏";
      return null;
    }
  }

  async function 取契约(编号) {
    const 状态 = 取("契约状态");
    写状态(状态, "请求中…");
    try {
      const 应答 = await 取能力(编号);
      摆应答(契约果, 应答);
      写状态(状态, 应答.状态 === 200 ? "已回" : "HTTP " + 应答.状态, 应答.状态 === 200);
      return 应答;
    } catch (错) {
      摆消息(契约果, "发不出去：" + 错.message);
      写状态(状态, "失败", false);
      return null;
    }
  }

  取("清单按钮").addEventListener("click", 取清单);
  取("契约按钮").addEventListener("click", () => 取契约(取("契约编号").value.trim()));

  return { 取清单, 取契约 };
}
