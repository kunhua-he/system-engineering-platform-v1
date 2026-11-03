//! 条目列表：一维条目，可单选 / 多选、可上移下移排序。
//!
//! 对应易语言的 列表框 / 选择列表框（2026-11-02 组件收敛裁决：只做这一个，
//! 需要二维列头时用 `表格`，两者不合并）。
//!
//! 选中与顺序都是**底座状态**：`__选中`（键或键数组）、条目顺序由 `4929` 改写后重渲染。

use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本};
use crate::组件树::渲染状态;
use crate::编号与码面::错误码;

/// 取选中键集合：单选给字符串，多选给数组，两种都认。
fn 取选中集合(节点: &Value) -> Vec<String> {
    match 节点.get("__选中") {
        Some(Value::String(键)) => vec![键.clone()],
        Some(Value::Array(项表)) => 项表
            .iter()
            .filter_map(|项| 项.as_str().map(|文本| 文本.to_string()))
            .collect(),
        _ => Vec::new(),
    }
}

fn 条目键(条目: &Value, 序: usize) -> String {
    let 写的 = 取对象文本(条目, "键");
    if 写的.is_empty() {
        format!("项{序}")
    } else {
        写的
    }
}

/// 拼装列表。`可拖排序` 打开时每条右侧出上移 / 下移按钮，排序由底座做。
pub(crate) fn 拼装条目列表(节点: &Value, 状态: &mut 渲染状态) -> Result<String, u32> {
    状态.需要组件引导脚本 = true;
    let 条目表 = 节点
        .get("条目")
        .and_then(|项| 项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 选中集 = 取选中集合(节点);
    let 多选 = 节点
        .get("多选")
        .and_then(|项| 项.as_bool())
        .unwrap_or(false);
    let 可拖排序 = 节点
        .get("可拖排序")
        .and_then(|项| 项.as_bool())
        .unwrap_or(false);
    let 行高 = 节点.get("行高").and_then(|项| 项.as_f64()).unwrap_or(32.0);
    let mut 正文 = String::new();
    for (序, 条目) in 条目表.iter().enumerate() {
        let 对象 = 条目.as_object().ok_or(错误码::内容不合法)?;
        let 文本 = 对象
            .get("文本")
            .and_then(|项| 项.as_str())
            .ok_or(错误码::内容不合法)?;
        let 键 = 条目键(条目, 序);
        let 转义键 = 转义网页文本(&键);
        let 已选中 = 选中集.contains(&键);
        let 禁用 = 对象
            .get("禁用")
            .and_then(|项| 项.as_bool())
            .unwrap_or(false);
        let 图标 = 取对象文本(条目, "图标");
        let 图标块 = if 图标.is_empty() {
            String::new()
        } else {
            format!(
                "<span class=\"hs-list-icon\">{}</span>",
                转义网页文本(&图标)
            )
        };
        let mut 类名 = String::from("hs-list-item");
        if 已选中 {
            类名.push_str(" 已选中");
        }
        if 禁用 {
            类名.push_str(" 已禁用");
        }
        let 点击属性 = if 禁用 {
            String::new()
        } else {
            format!(" data-hs-op=\"选中\" data-hs-key=\"{转义键}\"")
        };
        let 排序块 = if 可拖排序 && !禁用 {
            format!(
                "<span class=\"hs-list-order\">\
                 <button class=\"hs-button\" data-hs-op=\"上移\" data-hs-key=\"{转义键}\">↑</button>\
                 <button class=\"hs-button\" data-hs-op=\"下移\" data-hs-key=\"{转义键}\">↓</button></span>"
            )
        } else {
            String::new()
        };
        正文.push_str(&format!(
            "<div class=\"{类名}\"{点击属性} data-hs-key=\"{转义键}\" \
             style=\"display:flex;align-items:center;gap:8px;height:{行高}px;padding:0 8px;cursor:pointer\">\
             {图标块}<span class=\"hs-list-label\" style=\"flex:1\">{}</span>{排序块}</div>",
            转义网页文本(文本)
        ));
    }
    let 模式属性 = if 多选 { " data-multi=\"1\"" } else { "" };
    Ok(format!(
        "<div class=\"hs-list\"{模式属性} style=\"overflow:auto\">{正文}</div>"
    ))
}
