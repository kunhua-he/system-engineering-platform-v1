//! 表格事件只更新实例，不以重绘模拟事件，避免悬停引发重绘循环。
use crate::{组件实例, 编号与码面::错误码};
use serde_json::{Value, json};

pub(super) fn 记录事件状态(组件句柄: u64, 事件参数: &Value) -> Result<(), u32> {
    let 事件名称 = 事件参数
        .get("事件名")
        .and_then(Value::as_str)
        .ok_or(错误码::参数不合法)?;
    if ![
        "当前表项被改变",
        "表项被激活",
        "表头被单击",
        "表项跟踪",
        "左键单击表项",
        "右键单击表项",
        "开始编辑",
        "结束编辑",
        "检查框状态被改变",
    ]
    .contains(&事件名称)
    {
        return Err(错误码::参数不合法);
    }
    组件实例::改节点(组件句柄, |节点对象| {
        let mut 事件列表 = 节点对象
            .get("__事件记录")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        事件列表.push(事件参数.clone());
        if 事件列表.len() > 32 {
            事件列表.remove(0);
        }
        节点对象.insert("__事件记录".to_string(), Value::Array(事件列表));
        节点对象.insert("__最后事件".to_string(), 事件参数.clone());
    })?;
    Ok(())
}

pub(super) fn 采集操作事件(
    组件句柄: u64,
    操作名称: &str,
    操作参数: &Value,
    旧节点: &Value,
) -> Result<(), u32> {
    if 操作名称 == "记录事件" {
        return Ok(());
    }
    let 新节点 = 组件实例::取节点(组件句柄)?;
    let mut 事件列表 = Vec::new();
    if let Some(事件名称) = 操作参数.get("事件名").and_then(Value::as_str) {
        事件列表.push(事件名称);
    }
    if 新节点.get("__选中") != 旧节点.get("__选中") {
        事件列表.push("当前表项被改变");
    }
    match 操作名称 {
        "进入编辑" => 事件列表.push("开始编辑"),
        "结束编辑" => 事件列表.push("结束编辑"),
        _ => (),
    }
    for 事件名称 in 事件列表 {
        let mut 事件记录 = 操作参数.as_object().cloned().unwrap_or_default();
        事件记录.insert("事件名".to_string(), json!(事件名称));
        if !事件记录.contains_key("表项索引")
            && let Some(行键) = 操作参数
                .get("键")
                .and_then(Value::as_str)
                .and_then(|文本| 文本.parse::<usize>().ok())
        {
            事件记录.insert("表项索引".to_string(), json!(行键));
        }
        记录事件状态(组件句柄, &Value::Object(事件记录))?;
    }
    Ok(())
}
