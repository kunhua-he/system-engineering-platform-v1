// 呈现 —— 把后端返回的 JSON 摆成 DOM，摘要读取服务端的成功字段。

/** 建一个节点。`文本` 走 textContent，**不当 HTML 用**（返回里带尖括号也不会被解释）。 */
export function 建元素(标签, 类名, 源文本) {
  const 界面元素 = document.createElement(标签);
  if (类名) 界面元素.className = 类名;
  if (源文本 !== undefined && 源文本 !== null) 界面元素.textContent = String(源文本);
  return 界面元素;
}

/** 清空一个容器。 */
export function 清空容器(容器) {
  while (容器.firstChild) 容器.removeChild(容器.firstChild);
}

/** 标量 → 显示文本。 */
export function 取字面文本(待处理值) {
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
    容器.append(建元素("span", 取类别(待处理值), 取字面文本(待处理值)));
    return;
  }
  if (Array.isArray(待处理值)) {
    const 项表 = 建元素("div", "表 数组");
    if (待处理值.length === 0) 项表.append(建元素("div", "空", "（空表）"));
    待处理值.forEach((值项, 位次) => {
      const 源码行 = 建元素("div", "数组项");
      源码行.append(建元素("div", "位", "第 " + (位次 + 1) + " 项"));
      const 内层 = 建元素("div", "内");
      摆值(内层, 值项, 深度 + 1);
      源码行.append(内层);
      项表.append(源码行);
    });
    容器.append(项表);
    return;
  }
  const 项表 = 建元素("div", "表 对象");
  const 键集 = Object.keys(待处理值);
  if (键集.length === 0) 项表.append(建元素("div", "空", "（空对象）"));
  for (const 键名 of 键集) {
    const 源码行 = 建元素("div", "键值行");
    源码行.append(建元素("div", "键", 键名));
    const 内层 = 建元素("div", "内");
    摆值(内层, 待处理值[键名], 深度 + 1);
    源码行.append(内层);
    项表.append(源码行);
  }
  容器.append(项表);
}

/** 一层对象 → 一行「键 值 · 键 值」（标签取自数据本身，不是源码里写死的名字）。 */
export function 转扁平行(待处理值) {
  if (!是对象(待处理值)) return 取字面文本(待处理值);
  return Object.keys(待处理值)
    .map((键名) => 键名 + " " + 取字面文本(待处理值[键名]))
    .join(" · ");
}

/** 摆成「一行读数」：顶层每个键值对一行内联，够一眼扫出来。 */
export function 摆行内(容器, 待处理值) {
  if (!是对象(待处理值)) {
    容器.append(建元素("span", 取类别(待处理值), 取字面文本(待处理值)));
    return;
  }
  for (const 键名 of Object.keys(待处理值)) {
    const 键值对 = 建元素("span", "对");
    键值对.append(建元素("span", "键", 键名 + "："));
    键值对.append(建元素("span", "文", 转扁平行(待处理值[键名])));
    容器.append(键值对);
  }
}

/** 摘要只读取明确的服务端成功判定，其余应答保持未知。 */
export function 取应答摘要(应答体) {
  if (!是对象(应答体)) return { 状态词: "未知", 判定档: "灰" };
  if (应答体.成功 === false) return { 状态词: "失败", 判定档: "坏" };
  if (应答体.成功 === true) return { 状态词: "成功", 判定档: "好" };
  return { 状态词: "未知", 判定档: "灰" };
}

/** 一条应答 → DOM：HTTP 状态 + 体 + 可展开的原文。 */
export function 摆应答(容器, 造应答) {
  清空容器(容器);
  const 头部 = 建元素("div", "应答头");
  头部.append(建元素("span", 造应答.状态 === 200 ? "状态" : "状态 坏", "HTTP " + 造应答.状态));
  const 摘要结果 = 取应答摘要(造应答.报文体);
  if (摘要结果.判定档 !== "灰") 头部.append(建元素("span", "徽标 " + 摘要结果.判定档, 摘要结果.状态词));
  容器.append(头部);

  const 体盒 = 建元素("div", "体盒");
  if (造应答.报文体 === null) {
    体盒.append(建元素("p", "提示", "这段原文不是 JSON（多半是同源托管没接上：静态服务把 /接口 当文件找了）。原文如下。"));
    体盒.append(建元素("pre", "原文", 造应答.应答文本));
  } else {
    if (取应答摘要(造应答.报文体).判定档 === "坏") 体盒.classList.add("有假");
    摆值(体盒, 造应答.报文体);
  }
  容器.append(体盒);

  const 原文详情 = 建元素("details", "原文盒");
  原文详情.append(建元素("summary", null, "应答原文"));
  原文详情.append(建元素("pre", "原文", 造应答.应答文本));
  容器.append(原文详情);
}

/** 一份静态件 → DOM：HTTP 状态 + 原文。 */
export function 摆静态件(容器, 路径, 节点件) {
  清空容器(容器);
  const 头部 = 建元素("div", "应答头");
  头部.append(建元素("span", 节点件.状态 === 200 ? "状态 好" : "状态 坏", "HTTP " + 节点件.状态));
  头部.append(建元素("span", "步号", 路径));
  容器.append(头部);
  const 体盒 = 建元素("div", "体盒");
  if (节点件.状态 !== 200) {
    体盒.append(建元素("p", "提示 坏", "取不到。同源静态托管那一侧没把这个路径交出来（接口面只实现四个端点，实测请求 / 回 404）—— 这是托管侧的缺口，不是本页能补的。"));
  }
  体盒.append(建元素("pre", "原文", 节点件.应答文本));
  容器.append(体盒);
}

/** 一段说明文字（用于网络层失败这类本页自身要报的事）。 */
export function 摆消息(容器, 源文本) {
  清空容器(容器);
  容器.append(建元素("p", "提示 坏", 源文本));
}

/** 给一个状态节点写一句话。`是否好` 三态：true 绿 · false 红 · undefined 灰。 */
export function 写状态(节点, 源文本, 是否好) {
  if (!节点) return;
  节点.textContent = 源文本 || "";
  节点.className = "状态" + (是否好 === undefined ? "" : 是否好 ? " 好" : " 坏");
}
