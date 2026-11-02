use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本};
use crate::编号与码面::错误码;
use crate::组件树::外观属性::{
    取尺寸, 取对齐, 合法标识, 取形态变量,
    菜单外观映射, 容器属性文本, };
use crate::组件树::{拼子节点, 拼装树节点, 拼通用样式, 空值兜底, 渲染状态};

pub(crate) fn 拼装行(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 样式 = 拼通用样式(
        节点,
        &format!(
            "display:flex;flex-direction:row;align-items:{};justify-content:{};min-width:0",
            取对齐(节点, "垂直对齐"),
            取对齐(节点, "水平对齐")
        ),
    );
    let 容器属性 = 容器属性文本(节点, 状态)?;Ok(
    format!(
        "<div class=\"hs-tree-node hs-tree-row\" style=\"{}\"{}>{}</div>",
        转义网页文本(&样式),
        容器属性,
        拼子节点(节点, 深度, 状态)?
    ))
}

pub(crate) fn 拼装列(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 样式 = 拼通用样式(
        节点,
        &format!(
            "display:flex;flex-direction:column;align-items:{};justify-content:{};min-width:0",
            取对齐(节点, "水平对齐"),
            取对齐(节点, "垂直对齐")
        ),
    );
    let 容器属性 = 容器属性文本(节点, 状态)?;Ok(
    format!(
        "<div class=\"hs-tree-node hs-tree-col\" style=\"{}\"{}>{}</div>",
        转义网页文本(&样式),
        容器属性,
        拼子节点(节点, 深度, 状态)?
    ))
}

pub(crate) fn 拼装网格(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
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
    let 容器属性 = 容器属性文本(节点, 状态)?;Ok(
    format!(
        "<div class=\"hs-tree-node hs-tree-grid\" style=\"{}\"{}>{}</div>",
        转义网页文本(&样式),
        容器属性,
        拼子节点(节点, 深度, 状态)?
    ))
}

pub(crate) fn 拼装侧栏(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
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
        let 打开地址 = 取对象文本(条目项, "打开地址");
        if !打开地址.is_empty()
            && (!打开地址.starts_with('/')
                || 打开地址.starts_with("//")
                || 打开地址.contains("..")
                || 打开地址.contains(':'))
        {
            return Err(错误码::内容不合法);
        }
        let 标签名 = if 打开地址.is_empty() { "div" } else { "a" };
        let 地址属性 = if 打开地址.is_empty() {
            String::new()
        } else {
            format!(" href=\"{}\"", 转义网页文本(&打开地址))
        };
        菜单文本.push_str(&format!("<{标签名} class=\"hs-tree-menu-item"));
        if 激活 {
            菜单文本.push_str(" is-active");
        }
        菜单文本.push_str(&format!("\"{地址属性}>"));
        let 图标文本 = 取对象文本(条目项, "图标");
        if !图标文本.is_empty() {
            菜单文本.push_str("<span class=\"hs-tree-menu-icon\">");
            菜单文本.push_str(&转义网页文本(&图标文本));
            菜单文本.push_str("</span>");
        }
        菜单文本.push_str("<span class=\"hs-tree-menu-label\">");
        菜单文本.push_str(&转义网页文本(&取对象文本(条目项, "名称")));
        菜单文本.push_str(&format!("</span></{标签名}>"));
    }
    let 侧栏标题文本 = 取对象文本(节点, "标题");
    let 菜单变量 = 取形态变量(节点, "菜单外观", &菜单外观映射)?;
    let mut 样式 = 拼通用样式(节点, "display:flex;align-items:stretch");
    样式.push_str(&菜单变量);Ok(
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
        拼子节点(节点, 深度, 状态)?
    ))
}

pub(crate) fn 拼装分区(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 样式 = 拼通用样式(节点, "display:flex;flex-direction:column;min-width:0");
    let 容器属性 = 容器属性文本(节点, 状态)?;
    let 标题文本 = 取对象文本(节点, "标题");
    Ok(format!(
        "<section class=\"hs-tree-node hs-tree-panel\" style=\"{}\"{}>{}{}</section>",
        转义网页文本(&样式),
        容器属性,
        if 标题文本.is_empty() {
            String::new()
        } else {
            format!(
                "<h3 class=\"hs-tree-panel-title\">{}</h3>",
                转义网页文本(&标题文本)
            )
        },
        拼子节点(节点, 深度, 状态)?
    ))
}

pub(crate) fn 拼装画布(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
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
        let 内层 = 拼装树节点(子节点, 深度 + 1, 状态)?;
        // 窗口要能被拖动/置顶：拖拽脚本移动的是画布给它的定位外壳
        let 拖拽标记 = if 取对象文本(子节点, "类型") == "窗口" {
            format!(
                " data-window-port=\"{}\"{}",
                转义网页文本(&取对象文本(子节点, "标识")),
                if 子节点.get("初始隐藏").and_then(Value::as_bool).unwrap_or(true) { " hidden" } else { "" }
            )
        } else {
            String::new()
        };
        子文本.push_str(&format!(
            "<div class=\"hs-tree-canvas-item\"{} style=\"{}\">{}</div>",
            拖拽标记,
            转义网页文本(&定位),
            内层
        ));
    }
    Ok(format!(
        "<div class=\"hs-tree-node hs-tree-canvas\" style=\"{}\">{}</div>",
        转义网页文本(&样式),
        子文本
    ))
}

pub(crate) fn 拼装悬浮层(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 标识文本 = 取对象文本(节点, "标识");
    if !合法标识(&标识文本) {
        return Err(错误码::内容不合法);
    }
    let 快捷键文本 = 取对象文本(节点, "快捷键");
    if 快捷键文本.chars().count() > 8 {
        return Err(错误码::内容不合法);
    }
    状态.需要显隐脚本 = true;
    let 初始隐藏 = 节点
        .get("初始隐藏")
        .and_then(|隐藏项| 隐藏项.as_bool())
        .unwrap_or(true);
    let 样式 = 拼通用样式(
        节点,
        "position:fixed;inset:0;z-index:60;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:auto",
    );Ok(
    format!(
        "<div class=\"hs-tree-overlay{}\" data-overlay=\"{}\"{} style=\"{}\">{}</div>",
        if 初始隐藏 { " is-hidden" } else { "" },
        转义网页文本(&标识文本),
        if 快捷键文本.is_empty() {
            String::new()
        } else {
            format!(" data-key=\"{}\"", 转义网页文本(&快捷键文本))
        },
        转义网页文本(&样式),
        拼子节点(节点, 深度, 状态)?
    ))
}
