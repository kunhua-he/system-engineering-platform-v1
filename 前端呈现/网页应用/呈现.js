// 呈现 —— 把后端返回的 JSON **原样摆成 DOM**。
//
// 本文件是「前端零逻辑」那条判据的落点：它**不看任何键名**，只看值的类型
// （空 / 布尔 / 数 / 文 / 表 / 对象）。所以后端新增一个旁路字段，本页不用改一行 ——
// 反过来说，本页也绝不会把某个字段的含义写死。
//
// 行序由本页标出（数组项前写「第 N 项」），那是界面上的位置，不是对契约的解释。
// 摘要（成功 / 失败）也是**按值的类型**扫出来的：顶层出现 `false` 就是失败、只出现 `true`
// 就是成功 —— 没有任何一处写着「某个字段叫这个名字所以它表示那个意思」。

/** 建一个节点。`文本` 走 textContent，**不当 HTML 用**（返回里带尖括号也不会被解释）。 */
export function 建元素(标签, 类名, 文本) {
  const 节 = document.createElement(标签);
  if (类名) 节.className = 类名;
  if (文本 !== undefined && 文本 !== null) 节.textContent = String(文本);
  return 节;
}

/** 清空一个容器。 */
export function 清空(容器) {
  while (容器.firstChild) 容器.removeChild(容器.firstChild);
}

/** 标量 → 显示文本。 */
export function 字面(待处理值) {
  if (待处理值 === null || 待处理值 === undefined) return "null";
  if (typeof 待处理值 === "boolean") return 待处理值 ? "true" : "false";
  return String(待处理值);
}

/** 标量 → 类名（只看类型）。 */
export function 取类别(待处理值) {
  if (待处理值 === null || 待处理值 === undefined) return "空";
  if (typeof 待处理值 === "boolean") return 待处理值 ? "真" : "假";
  if (typeof 待处理值 === "number") return "数";
  return "文";
}

function 是对象(待处理值) {
  return 待处理值 !== null && typeof 待处理值 === "object" && !Array.isArray(待处理值);
}

/** 任意 JSON 值 → DOM。深度只用于缩进类名。 */
export function 摆值(容器, 待处理值, 深度 = 0) {
  if (待处理值 === null || 待处理值 === undefined) {
    容器.append(建元素("span", "空", "null"));
    return;
  }
  if (typeof 待处理值 !== "object") {
    容器.append(建元素("span", 取类别(待处理值), 字面(待处理值)));
    return;
  }
  if (Array.isArray(待处理值)) {
    const 表 = 建元素("div", "表 数组");
    if (待处理值.length === 0) 表.append(建元素("div", "空", "（空表）"));
    待处理值.forEach((一项, 位置) => {
      const 行 = 建元素("div", "数组项");
      行.append(建元素("div", "位", "第 " + (位置 + 1) + " 项"));
      const 内 = 建元素("div", "内");
      摆值(内, 一项, 深度 + 1);
      行.append(内);
      表.append(行);
    });
    容器.append(表);
    return;
  }
  const 表 = 建元素("div", "表 对象");
  const 键集 = Object.keys(待处理值);
  if (键集.length === 0) 表.append(建元素("div", "空", "（空对象）"));
  for (const 键 of 键集) {
    const 行 = 建元素("div", "键值行");
    行.append(建元素("div", "键", 键));
    const 内 = 建元素("div", "内");
    摆值(内, 待处理值[键], 深度 + 1);
    行.append(内);
    表.append(行);
  }
  容器.append(表);
}

/** 一层对象 → 一行「键 值 · 键 值」（标签取自数据本身，不是源码里写死的名字）。 */
export function 扁平(待处理值) {
  if (!是对象(待处理值)) return 字面(待处理值);
  return Object.keys(待处理值)
    .map((键名) => 键名 + " " + 字面(待处理值[键名]))
    .join(" · ");
}

/** 摆成「一行读数」：顶层每个键值对一行内联，够一眼扫出来。 */
export function 摆行内(容器, 待处理值) {
  if (!是对象(待处理值)) {
    容器.append(建元素("span", 取类别(待处理值), 字面(待处理值)));
    return;
  }
  for (const 键 of Object.keys(待处理值)) {
    const 对 = 建元素("span", "对");
    对.append(建元素("span", "键", 键 + "："));
    对.append(建元素("span", "文", 扁平(待处理值[键])));
    容器.append(对);
  }
}

/**
 * 按值的类型扫出一个词：顶层有 `false` ⇒ 失败；只有 `true` ⇒ 成功；都不是 ⇒ 未知。
 * **不读键名**，所以后端把字段改名也不影响它。
 */
export function 摘要(应答体) {
  if (!是对象(应答体)) return { 词: "未知", 类: "灰" };
  let 见真 = false;
  let 见假 = false;
  for (const 键 of Object.keys(应答体)) {
    if (应答体[键] === true) 见真 = true;
    if (应答体[键] === false) 见假 = true;
  }
  if (见假) return { 词: "失败", 类: "坏" };
  if (见真) return { 词: "成功", 类: "好" };
  return { 词: "未知", 类: "灰" };
}

/** 一条应答 → DOM：HTTP 状态 + 体 + 可展开的原文。 */
export function 摆应答(容器, 应答) {
  清空(容器);
  const 头 = 建元素("div", "应答头");
  头.append(建元素("span", 应答.状态 === 200 ? "状态 好" : "状态 坏", "HTTP " + 应答.状态));
  const 词 = 摘要(应答.体);
  if (词.类 !== "灰") 头.append(建元素("span", "徽标 " + 词.类, 词.词));
  容器.append(头);

  const 体盒 = 建元素("div", "体盒");
  if (应答.体 === null) {
    体盒.append(建元素("p", "提示", "这段原文不是 JSON（多半是同源托管没接上：静态服务把 /接口 当文件找了）。原文如下。"));
    体盒.append(建元素("pre", "原文", 应答.文));
  } else {
    if (摘要(应答.体).类 === "坏") 体盒.classList.add("有假");
    摆值(体盒, 应答.体);
  }
  容器.append(体盒);

  const 详 = 建元素("details", "原文盒");
  详.append(建元素("summary", null, "应答原文"));
  详.append(建元素("pre", "原文", 应答.文));
  容器.append(详);
}

/** 一份静态件 → DOM：HTTP 状态 + 原文。 */
export function 摆件(容器, 路径, 节点件) {
  清空(容器);
  const 头 = 建元素("div", "应答头");
  头.append(建元素("span", 节点件.状态 === 200 ? "状态 好" : "状态 坏", "HTTP " + 节点件.状态));
  头.append(建元素("span", "步号", 路径));
  容器.append(头);
  const 体盒 = 建元素("div", "体盒");
  if (节点件.状态 !== 200) {
    体盒.append(建元素("p", "提示 坏", "取不到。同源静态托管那一侧没把这个路径交出来（接口面只实现四个端点，实测请求 / 回 404）—— 这是托管侧的缺口，不是本页能补的。"));
  }
  体盒.append(建元素("pre", "原文", 节点件.文));
  容器.append(体盒);
}

/** 一段说明文字（用于网络层失败这类本页自身要报的事）。 */
export function 摆消息(容器, 文本) {
  清空(容器);
  容器.append(建元素("p", "提示 坏", 文本));
}

/** 给一个状态节点写一句话。`是否好` 三态：true 绿 · false 红 · undefined 灰。 */
export function 写状态(节点, 文本, 是否好) {
  if (!节点) return;
  节点.textContent = 文本 || "";
  节点.className = "状态" + (是否好 === undefined ? "" : 是否好 ? " 好" : " 坏");
}
