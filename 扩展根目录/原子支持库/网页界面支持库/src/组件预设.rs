//! 组件预设：把「每次都要重写一遍的那串字段」内置成一张表。
//!
//! 华哥口径（2026-11-02）：传参越少越好，能内置的就内置，只把真正要变的东西传进来。
//! 用法：`{"类型":"按钮","预设":"主按钮","文字":"登录"}`。
//!
//! 预设表编译期随源码进制品（`include_str!`），不做运行时外部文件：
//! 外部文件会让「同一个制品在不同机器上渲染出不同结果」，制品就不再可复现。

use std::sync::OnceLock;

use serde_json::Value;

use crate::编号与码面::错误码;

const 预设表文本: &str = include_str!("预设表.json");

fn 预设表() -> &'static Value {
    static 表: OnceLock<Value> = OnceLock::new();
    表.get_or_init(|| serde_json::from_str(预设表文本).unwrap_or(Value::Null))
}

/// 按 `预设` 字段把内置字段铺到节点上：预设先铺底，节点自身字段压在上面。
///
/// 没有 `预设` 字段就原样返回；预设名找不到报参数不合法（不静默降级成空预设）。
pub(crate) fn 应用预设(节点: &Value) -> Result<Value, u32> {
    let 预设名 = match 节点.get("预设").and_then(|值| 值.as_str()) {
        Some(名) if !名.is_empty() => 名,
        _ => return Ok(节点.clone()),
    };
    let 类型文本 = 节点
        .get("类型")
        .and_then(|值| 值.as_str())
        .ok_or(错误码::内容不合法)?;
    let 基础 = 预设表()
        .get(类型文本)
        .and_then(|分组| 分组.get(预设名))
        .ok_or(错误码::参数不合法)?
        .clone();
    let mut 结果 = 基础;
    if let (Some(目标), Some(来源)) = (结果.as_object_mut(), 节点.as_object()) {
        for (键名, 值) in 来源 {
            if 键名 == "预设" {
                continue;
            }
            目标.insert(键名.clone(), 值.clone());
        }
    }
    // 节点没写类型时以入参为准（上面已确认有类型，这里只保证合并后带着它）。
    if let Some(对象) = 结果.as_object_mut() {
        对象.insert("类型".to_string(), Value::from(类型文本));
    }
    Ok(结果)
}
