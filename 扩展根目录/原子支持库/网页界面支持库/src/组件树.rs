//! 组件树：窗口内容与整页都由一棵可递归嵌套的节点树描述。
//!
//! 容器（行 / 列 / 网格 / 侧栏 / 分区 / 画布）可以无限嵌套，叶子出真正的界面元素。
//! 产品语义上不限制嵌套层数；工程上拦两道闸（深度 32 层、节点 2000 个），
//! 只防「写错了的树把渲染拖死」，正常界面远远用不到。

use serde_json::Value;

use crate::业务实现::{
    取对象文本, 拼装聊天片段, 拼装表单字段, 拼装表格行, 转义网页文本
};
use crate::编号与码面::错误码;

pub(crate) const 树最大深度: u16 = 32;
pub(crate) const 树最大节点数: usize = 2000;

/// 尺寸类字段：数字当像素，字符串原样（"100%"、"auto"）。
fn 取尺寸(节点: &Value, 字段名: &str) -> String {
    match 节点.get(字段名) {
        Some(Value::Number(数值)) => format!("{数值}px"),
        Some(Value::String(文本)) => 文本.clone(),
        _ => String::new(),
    }
}

/// 对齐词：居中 / 起点 / 终点 / 两端。
fn 取对齐(节点: &Value, 字段名: &str) -> &'static str {
    match 取对象文本(节点, 字段名).as_str() {
        "居中" => "center",
        "终点" => "flex-end",
        "两端" => "space-between",
        _ => "flex-start",
    }
}

/// 通用样式：所有节点都能带，拼成 style 属性值。
fn 拼通用样式(节点: &Value, 基础: &str) -> String {
    let mut 样式 = String::from(基础);
    let 宽 = 取尺寸(节点, "宽");
    let 高 = 取尺寸(节点, "高");
    if !宽.is_empty() {
        样式.push_str(&format!(";width:{宽}"));
    }
    if !高.is_empty() {
        样式.push_str(&format!(";height:{高}"));
    }
    if let Some(Value::Number(数值)) = 节点.get("间距") {
        样式.push_str(&format!(";gap:{数值}px"));
    }
    let 内边距 = 取尺寸(节点, "内边距");
    if !内边距.is_empty() {
        样式.push_str(&format!(";padding:{内边距}"));
    }
    let 背景 = 取对象文本(节点, "背景");
    if !背景.is_empty() {
        样式.push_str(&format!(";background:{背景}"));
    }
    let 圆角 = 取尺寸(节点, "圆角");
    if !圆角.is_empty() {
        样式.push_str(&format!(";border-radius:{圆角}"));
    }
    let 边框 = 取对象文本(节点, "边框");
    if !边框.is_empty() {
        样式.push_str(&format!(";border:{边框}"));
    }
    let 溢出 = 取对象文本(节点, "溢出");
    if !溢出.is_empty() {
        样式.push_str(&format!(";overflow:{溢出}"));
    }
    let 最小高 = 取尺寸(节点, "最小高");
    if !最小高.is_empty() {
        样式.push_str(&format!(";min-height:{最小高}"));
    }
    样式
}

/// 递归出口：子节点表
fn 拼子节点(节点: &Value, 深度: u16, 计数: &mut usize) -> Result<String, u32> {
    let 子节点表 = match 节点.get("子").and_then(|子项| 子项.as_array()) {
        Some(子项) => 子项,
        None => return Ok(String::new()),
    };
    let mut 子文本 = String::new();
    for 子节点 in 子节点表 {
        子文本.push_str(&拼装树节点(子节点, 深度 + 1, 计数)?);
    }
    Ok(子文本)
}

fn 拼装树节点(节点: &Value, 深度: u16, 计数: &mut usize) -> Result<String, u32> {
    if 深度 > 树最大深度 {
        return Err(错误码::资源受限);
    }
    *计数 += 1;
    if *计数 > 树最大节点数 {
        return Err(错误码::资源受限);
    }
    let 类型文本 = 取对象文本(节点, "类型");
    let 片段文本 = match 类型文本.as_str() {
        "行" => {
            let 样式 = 拼通用样式(
                节点,
                &format!(
                    "display:flex;flex-direction:row;align-items:{};justify-content:{};min-width:0",
                    取对齐(节点, "垂直对齐"),
                    取对齐(节点, "水平对齐")
                ),
            );
            format!(
                "<div class=\"hs-tree-node hs-tree-row\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                拼子节点(节点, 深度, 计数)?
            )
        }
        "列" => {
            let 样式 = 拼通用样式(
                节点,
                &format!(
                    "display:flex;flex-direction:column;align-items:{};justify-content:{};min-width:0",
                    取对齐(节点, "水平对齐"),
                    取对齐(节点, "垂直对齐")
                ),
            );
            format!(
                "<div class=\"hs-tree-node hs-tree-col\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                拼子节点(节点, 深度, 计数)?
            )
        }
        "网格" => {
            let 列数 = match 节点.get("列数") {
                Some(Value::Number(数值)) => 数值.as_u64().unwrap_or(3).clamp(1, 24),
                _ => 3,
            };
            let 样式 = 拼通用样式(
                节点,
                &format!(
                    "display:grid;grid-template-columns:repeat({列数},minmax(0,1fr));align-items:{}",
                    取对齐(节点, "垂直对齐")
                ),
            );
            format!(
                "<div class=\"hs-tree-node hs-tree-grid\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                拼子节点(节点, 深度, 计数)?
            )
        }
        "侧栏" => {
            let 栏宽 = {
                let 原值 = 取尺寸(节点, "栏宽");
                if 原值.is_empty() {
                    "232px".to_string()
                } else {
                    原值
                }
            };
            let 菜单条目表 = 节点
                .get("菜单")
                .and_then(|菜单项| 菜单项.as_array())
                .cloned()
                .unwrap_or_default();
            let mut 菜单文本 = String::new();
            for 条目项 in &菜单条目表 {
                let 激活 = 条目项
                    .get("激活")
                    .and_then(|激活项| 激活项.as_bool())
                    .unwrap_or(false);
                菜单文本.push_str("<div class=\"hs-tree-menu-item");
                if 激活 {
                    菜单文本.push_str(" is-active");
                }
                菜单文本.push_str("\">");
                let 图标文本 = 取对象文本(条目项, "图标");
                if !图标文本.is_empty() {
                    菜单文本.push_str("<span class=\"hs-tree-menu-icon\">");
                    菜单文本.push_str(&转义网页文本(&图标文本));
                    菜单文本.push_str("</span>");
                }
                菜单文本.push_str("<span class=\"hs-tree-menu-label\">");
                菜单文本.push_str(&转义网页文本(&取对象文本(条目项, "名称")));
                菜单文本.push_str("</span></div>");
            }
            let 侧栏标题文本 = 取对象文本(节点, "标题");
            let 样式 = 拼通用样式(节点, "display:flex;align-items:stretch");
            format!(
                "<div class=\"hs-tree-node hs-tree-sidebar\" style=\"{}\"><aside class=\"hs-tree-sidebar-pane\" style=\"flex:0 0 {}\">{}<div class=\"hs-tree-menu\">{}</div></aside><section class=\"hs-tree-sidebar-main\">{}</section></div>",
                转义网页文本(&样式),
                转义网页文本(&栏宽),
                if 侧栏标题文本.is_empty() {
                    String::new()
                } else {
                    format!(
                        "<div class=\"hs-tree-sidebar-title\">{}</div>",
                        转义网页文本(&侧栏标题文本)
                    )
                },
                菜单文本,
                拼子节点(节点, 深度, 计数)?
            )
        }
        "分区" => {
            let 样式 = 拼通用样式(节点, "display:flex;flex-direction:column;min-width:0");
            let 标题文本 = 取对象文本(节点, "标题");
            format!(
                "<section class=\"hs-tree-node hs-tree-panel\" style=\"{}\">{}{}</section>",
                转义网页文本(&样式),
                if 标题文本.is_empty() {
                    String::new()
                } else {
                    format!(
                        "<h3 class=\"hs-tree-panel-title\">{}</h3>",
                        转义网页文本(&标题文本)
                    )
                },
                拼子节点(节点, 深度, 计数)?
            )
        }
        "画布" => {
            let 样式 = 拼通用样式(节点, "position:relative;min-width:0");
            let 子节点表 = 节点
                .get("子")
                .and_then(|子项| 子项.as_array())
                .cloned()
                .unwrap_or_default();
            let mut 子文本 = String::new();
            for 子节点 in &子节点表 {
                let 定位 = format!(
                    "position:absolute;left:{};top:{};width:{};height:{}",
                    取尺寸(子节点, "左").if_empty("0px"),
                    取尺寸(子节点, "上").if_empty("0px"),
                    取尺寸(子节点, "宽").if_empty("auto"),
                    取尺寸(子节点, "高").if_empty("auto")
                );
                let 内层 = 拼装树节点(子节点, 深度 + 1, 计数)?;
                子文本.push_str(&format!(
                    "<div class=\"hs-tree-canvas-item\" style=\"{}\">{}</div>",
                    转义网页文本(&定位),
                    内层
                ));
            }
            format!(
                "<div class=\"hs-tree-node hs-tree-canvas\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                子文本
            )
        }
        "标题" => format!(
            "<h2 class=\"hs-tree-node hs-tree-title\">{}</h2>",
            转义网页文本(&取对象文本(节点, "文本"))
        ),
        "文字" => {
            let 样式 = 拼通用样式(节点, "white-space:pre-wrap;word-break:break-word");
            format!(
                "<div class=\"hs-tree-node hs-tree-text\" style=\"{}\">{}</div>",
                转义网页文本(&样式),
                转义网页文本(&取对象文本(节点, "文本"))
            )
        }
        "分隔条" => {
            let 样式 = 拼通用样式(节点, "");
            format!(
                "<div class=\"hs-tree-node hs-tree-divider\" style=\"{}\"></div>",
                转义网页文本(&样式)
            )
        }
        "表格" => {
            let 列定义 = 节点
                .get("列")
                .and_then(|列项| 列项.as_array())
                .ok_or(错误码::内容不合法)?;
            let 行数据 = 节点
                .get("行")
                .and_then(|行项| 行项.as_array())
                .ok_or(错误码::内容不合法)?;
            format!(
                "<div class=\"hs-tree-node hs-card\">{}</div>",
                拼装表格行(列定义, 行数据)?
            )
        }
        "表单" => {
            let 字段定义 = 节点
                .get("字段")
                .and_then(|字段项| 字段项.as_array())
                .ok_or(错误码::内容不合法)?;
            let 缺省值 = 节点
                .get("值")
                .cloned()
                .unwrap_or_else(|| Value::Object(serde_json::Map::new()));
            format!(
                "<div class=\"hs-tree-node hs-card\">{}</div>",
                拼装表单字段(字段定义, &缺省值)?
            )
        }
        "聊天流" => {
            let 消息表 = match 节点.get("消息").and_then(|消息项| 消息项.as_array()) {
                Some(消息项) => 消息项.clone(),
                None => Vec::new(),
            };
            let 空态文本 = 取对象文本(节点, "空态文案");
            format!(
                "<div class=\"hs-tree-node\">{}</div>",
                拼装聊天片段(&消息表, &空态文本)?
            )
        }
        "原样" => {
            let 片段文本 = 取对象文本(节点, "html");
            if 片段文本.len() > 200_000 {
                return Err(错误码::资源受限);
            }
            片段文本
        }
        _ => return Err(错误码::内容不合法),
    };
    Ok(片段文本)
}

/// 4928 渲染组件树：一棵可无限嵌套的节点树 → HTML 片段。
pub(crate) fn 渲染组件树(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 树定义原文 = crate::业务实现::取文本参数(参数表, 0)?;
    let 树定义值: Value =
        serde_json::from_str(&树定义原文).map_err(|_| 错误码::内容不合法)?;
    let 根节点 = 树定义值.get("根").ok_or(错误码::内容不合法)?;
    let mut 计数 = 0usize;
    let 根文本 = 拼装树节点(根节点, 0, &mut 计数)?;
    let 样式 = 取对象文本(根节点, "容器样式");
    Ok((
        4,
        format!(
            "<div class=\"hs-tree\" data-tree=\"1\" style=\"{}\">{}</div>",
            转义网页文本(&样式),
            根文本
        )
        .into_bytes(),
    ))
}

/// 空串兜底的小工具（画布定位用）。
trait 空值兜底 {
    fn if_empty(self, 兜底: &str) -> String;
}

impl 空值兜底 for String {
    fn if_empty(self, 兜底: &str) -> String {
        if self.is_empty() {
            兜底.to_string()
        } else {
            self
        }
    }
}
