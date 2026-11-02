//! 控件类样式（宽 · 高 · 圆角 · 边框 · 背景 · 文字 · 字号 · 字重 · 内边距）的拼装与范围校验。

use serde_json::Value;

use crate::编号与码面::错误码;

use super::{取尺寸, 取对象文本, 校验颜色值, 背景样式文本, 间距合法};

const 字号下限: f64 = 8.0;
const 字号上限: f64 = 72.0;
const 字重下限: f64 = 100.0;
const 字重上限: f64 = 900.0;

/// 控件上的文字与内边距也归声明，按钮 / chip 才不必靠固定皮肤。
/// 越界值一律报「内容不合法」——静默丢弃会让声明方以为生效了。
pub(crate) fn 控件样式文本(节点: &Value) -> Result<String, u32> {
    let mut 样式 = String::new();
    for (字段, 属性) in [("宽", "width"), ("高", "height"), ("圆角", "border-radius")] {
        let 值 = 取尺寸(节点, 字段);
        if !值.is_empty() {
            样式.push_str(&format!("{属性}:{值};"));
        }
    }
    let 边框颜色 = 取对象文本(节点, "边框颜色");
    if !边框颜色.is_empty() {
        校验颜色值(&边框颜色)?;
        样式.push_str(&format!("border-color:{边框颜色};"));
    }
    let 背景文本 = 背景样式文本(节点);
    if !背景文本.is_empty() {
        样式.push_str(&背景文本);
        样式.push(';');
    }
    let 文字颜色 = 取对象文本(节点, "文字颜色");
    if !文字颜色.is_empty() {
        校验颜色值(&文字颜色)?;
        样式.push_str(&format!("color:{文字颜色};"));
    }
    if let Some(字号) = 节点.get("字号").and_then(|取值项| 取值项.as_f64()) {
        if !(字号下限..=字号上限).contains(&字号) {
            return Err(错误码::内容不合法);
        }
        样式.push_str(&format!("font-size:{字号}px;"));
    }
    if let Some(字重) = 节点.get("字重").and_then(|取值项| 取值项.as_f64()) {
        if !(字重下限..=字重上限).contains(&字重) || (字重 as u32) % 100 != 0 {
            return Err(错误码::内容不合法);
        }
        样式.push_str(&format!("font-weight:{};", 字重 as u32));
    }
    let 内边距 = 取对象文本(节点, "内边距");
    if !内边距.is_empty() {
        if !间距合法(&内边距) {
            return Err(错误码::内容不合法);
        }
        样式.push_str(&format!("padding:{内边距};"));
    }
    if 样式.ends_with(';') {
        样式.pop();
    }
    Ok(样式)
}
