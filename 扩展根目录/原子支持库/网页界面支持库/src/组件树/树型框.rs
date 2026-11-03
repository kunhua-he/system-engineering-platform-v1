//! 树型框：分层条目，可展开收起、可选中、可带图标。
//!
//! 对应易语言的 树型框 / 目录框 / 驱动器框 / 文件框（2026-11-02 组件收敛裁决：只做这一个，
//! 其余文件类组件用它的数据表达）。
//!
//! 展开与选中是**底座状态**：节点声明里带 `__展开`（展开集合）与 `__收起`（收起集合）、
//! `__选中`（选中键），由 `4929 操作组件` 改写后重渲染，页面只负责把点击交回来。

use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本};
use crate::组件树::渲染状态;
use crate::编号与码面::错误码;

/// 条目最多套这么多层，防一份坏声明把渲染拖死。
const 条目深度上限: u16 = 16;

/// 取一个字符串集合字段（`__展开` / `__收起`）。
fn 取集合(节点: &Value, 字段名: &str) -> Vec<String> {
    节点
        .get(字段名)
        .and_then(|项| 项.as_array())
        .map(|数组| {
            数组
                .iter()
                .filter_map(|项| 项.as_str().map(|文本| 文本.to_string()))
                .collect()
        })
        .unwrap_or_default()
}

fn 含(集合: &[String], 键: &str) -> bool {
    集合.iter().any(|项| 项 == 键)
}

/// 条目键：声明里没写就用「项序号」，保证每个条目都能被操作。
fn 条目键(条目: &Value, 序: usize) -> String {
    let 写的 = 取对象文本(条目, "键");
    if 写的.is_empty() {
        format!("项{序}")
    } else {
        写的
    }
}

/// 拼装一条条目（含子层）。
fn 拼一条(
    条目: &Value,
    序: usize,
    层级: u16,
    展开集: &[String],
    收起集: &[String],
    选中键: &str,
    外观设置: (f64, f64, bool),
) -> Result<String, u32> {
    let (缩进, 行高, 连线) = 外观设置;
    if 层级 > 条目深度上限 {
        return Err(错误码::资源受限);
    }
    let 对象 = 条目.as_object().ok_or(错误码::内容不合法)?;
    let 文本 = 对象
        .get("文本")
        .and_then(|项| 项.as_str())
        .ok_or(错误码::内容不合法)?;
    let 键 = 条目键(条目, 序);
    let 子表 = 对象.get("子").and_then(|项| 项.as_array());
    let 有子 = 子表.map(|数组| !数组.is_empty()).unwrap_or(false);
    let 默认展开 = 对象
        .get("展开")
        .and_then(|项| 项.as_bool())
        .unwrap_or(false);
    let 已展开 = if 含(收起集, &键) {
        false
    } else if 含(展开集, &键) {
        true
    } else {
        默认展开
    };
    let 已选中 = !选中键.is_empty() && 选中键 == 键;
    let 图标 = 取对象文本(条目, "图标");
    let 转义键 = 转义网页文本(&键);
    let 转义文本 = 转义网页文本(文本);
    let 缩进像素 = 缩进.max(0.0);

    let 折叠符号 = if !有子 {
        ""
    } else if 已展开 {
        "▾"
    } else {
        "▸"
    };
    let 折叠按钮 = if 有子 {
        format!(
            "<span class=\"hs-tree-twisty\" data-hs-op=\"展开\" data-hs-key=\"{转义键}\" \
             style=\"cursor:pointer;width:14px;display:inline-block;flex:0 0 14px\">{折叠符号}</span>"
        )
    } else {
        "<span style=\"width:14px;display:inline-block;flex:0 0 14px\"></span>".to_string()
    };
    let 图标块 = if 图标.is_empty() {
        String::new()
    } else {
        format!(
            "<span class=\"hs-tree-icon\">{}</span>",
            转义网页文本(&图标)
        )
    };
    let 选中类 = if 已选中 { " 已选中" } else { "" };
    let 行样式 = format!(
        "display:flex;align-items:center;gap:6px;height:{行高}px;padding-left:{}px;cursor:pointer",
        缩进像素 * 层级 as f64
    );
    let mut 结果 = format!(
        "<li class=\"hs-tree-item\" data-hs-key=\"{转义键}\">\
         <div class=\"hs-tree-row{选中类}\" data-hs-op=\"选中\" data-hs-key=\"{转义键}\" style=\"{行样式}\">\
         {折叠按钮}{图标块}<span class=\"hs-tree-label\">{转义文本}</span></div>"
    );
    if 有子 && 已展开 {
        let 空表: Vec<Value> = Vec::new();
        let 子数组 = 子表.unwrap_or(&空表);
        let 连线类 = if 连线 { " 显示连线" } else { "" };
        结果.push_str(&format!(
            "<ul class=\"hs-tree-children{连线类}\" style=\"margin:0;padding:0;list-style:none\">"
        ));
        for (子序, 子条目) in 子数组.iter().enumerate() {
            结果.push_str(&拼一条(
                子条目,
                子序,
                层级 + 1,
                展开集,
                收起集,
                选中键,
                外观设置,
            )?);
        }
        结果.push_str("</ul>");
    }
    结果.push_str("</li>");
    Ok(结果)
}

/// 拼装树型框。`状态` 里开组件引导脚本，页面才认 `data-hs-op`。
pub(crate) fn 拼装树型框(节点: &Value, 状态: &mut 渲染状态) -> Result<String, u32> {
    状态.需要组件引导脚本 = true;
    let 条目表 = 节点
        .get("条目")
        .and_then(|项| 项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 展开集 = 取集合(节点, "__展开");
    let 收起集 = 取集合(节点, "__收起");
    let 选中键 = 取对象文本(节点, "__选中");
    let 缩进 = 节点.get("缩进").and_then(|项| 项.as_f64()).unwrap_or(16.0);
    let 行高 = 节点.get("行高").and_then(|项| 项.as_f64()).unwrap_or(28.0);
    let 连线 = 节点
        .get("连线")
        .and_then(|项| 项.as_bool())
        .unwrap_or(false);
    let mut 正文 = String::new();
    for (序, 条目) in 条目表.iter().enumerate() {
        正文.push_str(&拼一条(
            条目,
            序,
            0,
            &展开集,
            &收起集,
            &选中键,
            (缩进, 行高, 连线),
        )?);
    }
    Ok(format!(
        "<div class=\"hs-tree-box\" style=\"overflow:auto\"><ul class=\"hs-tree-root\" \
         style=\"margin:0;padding:0;list-style:none\">{正文}</ul></div>"
    ))
}
