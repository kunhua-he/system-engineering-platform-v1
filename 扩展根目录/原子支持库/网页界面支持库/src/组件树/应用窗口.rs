//! 应用窗口：窗口容器把应用内容装进桌面同一棵组件树，三键与可移动都由声明变量决定。

use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本};
use crate::编号与码面::错误码;
use crate::组件树::{拼子节点, 拼通用样式, 渲染状态};

use super::外观属性::{合法标识, 校验颜色值};

/// 拼装一扇窗口：标题栏（标题 + 可选的三个按钮）+ 正文。
pub(crate) fn 拼装窗口(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 标识文本 = 取对象文本(节点, "标识");
    if !合法标识(&标识文本) {
        return Err(错误码::内容不合法);
    }
    let 标题文本 = 取对象文本(节点, "标题");
    let 初始隐藏 = 节点
        .get("初始隐藏")
        .and_then(|隐藏项| 隐藏项.as_bool())
        .unwrap_or(true);
    let mut 标题栏样式 = String::from("height:38px");
    if let Some(Value::Number(栏高)) = 节点.get("标题栏高") {
        let 栏高值 = 栏高.as_f64().unwrap_or(0.0);
        if !(24.0..=64.0).contains(&栏高值) {
            return Err(错误码::内容不合法);
        }
        标题栏样式 = format!("height:{栏高值}px");
    }
    for (字段名, 样式属性) in [("标题栏背景", "background"), ("标题栏文字颜色", "color")] {
        let 取值 = 取对象文本(节点, 字段名);
        if 取值.is_empty() {
            continue;
        }
        校验颜色值(&取值)?;
        标题栏样式.push_str(&format!(";{样式属性}:{取值}"));
    }
    // 三个窗口按钮与可移动性都是声明变量：缺省只留关闭、窗口可拖
    let 取开关 = |字段名: &str, 缺省值: bool| {
        节点
            .get(字段名)
            .and_then(|开关项| 开关项.as_bool())
            .unwrap_or(缺省值)
    };
    let 可关闭 = 取开关("可关闭", true);
    let 可最小化 = 取开关("可最小化", false);
    let 可最大化 = 取开关("可最大化", false);
    let 可移动 = 取开关("可移动", true);
    // 圆点形态：给了按钮直径就按圆点渲染，颜色来自声明；否则退回符号形态
    let 按钮直径 = match 节点.get("按钮直径").and_then(|直径项| 直径项.as_f64()) {
        Some(直径值) => {
            if !(6.0..=24.0).contains(&直径值) {
                return Err(错误码::内容不合法);
            }
            Some(直径值)
        }
        None => None,
    };
    let mut 按钮片段 = String::new();
    for (开关, 类名后缀, 数据属性, 符号, 说明, 颜色字段) in [
        (可最小化, "min", "data-window-min", "—", "最小化", "最小化颜色"),
        (可最大化, "max", "data-window-max", "▢", "最大化", "最大化颜色"),
        (可关闭, "close", "data-window-close", "✕", "关闭", "关闭颜色"),
    ] {
        if !开关 {
            continue;
        }
        let 按钮样式 = match 按钮直径 {
            Some(直径值) => {
                let 颜色文本 = 取对象文本(节点, 颜色字段);
                let mut 样式 = format!(
                    "width:{直径值}px;height:{直径值}px;border-radius:50%;padding:0;flex:none;box-sizing:border-box"
                );
                if !颜色文本.is_empty() {
                    校验颜色值(&颜色文本)?;
                    样式.push_str(&format!(";background:{颜色文本}"));
                }
                样式
            }
            None => String::new(),
        };
        按钮片段.push_str(&format!(
            "<button class=\"hs-tree-window-{类名后缀}\" type=\"button\" {数据属性}=\"{}\" style=\"{}\" aria-label=\"{说明}\">{}</button>",
            转义网页文本(&标识文本),
            转义网页文本(&按钮样式),
            if 按钮直径.is_some() { String::new() } else { format!("<span aria-hidden=\"true\">{符号}</span>") }
        ));
    }
    let 样式 = 拼通用样式(
        节点,
        "position:relative;display:flex;flex-direction:column;overflow:hidden;width:100%;height:100%",
    );
    状态.需要窗口脚本 = true;
    Ok(format!(
        "<div class=\"hs-tree-node hs-tree-window{}\" data-window=\"{}\" data-movable=\"{}\" style=\"{}\"><div class=\"hs-tree-window-bar\" style=\"{}\"><span class=\"hs-tree-window-title\">{}</span>{}</div><div class=\"hs-tree-window-body\">{}</div></div>",
        if 初始隐藏 { " is-hidden" } else { "" },
        转义网页文本(&标识文本),
        if 可移动 { "1" } else { "0" },
        转义网页文本(&样式),
        转义网页文本(&标题栏样式),
        转义网页文本(&标题文本),
        按钮片段,
        拼子节点(节点, 深度, 状态)?
    ))
}
