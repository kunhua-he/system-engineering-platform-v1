//! 查找与排序：单项命中判定、值类型序号与比较、比较键取用、标量文本化。

pub(super) fn 单项命中(条目: &serde_json::Value, 字段名: &str, 直接匹配: bool, 期望值: &serde_json::Value) -> bool {
    if 直接匹配 || 字段名.is_empty() {
        条目 == 期望值
    } else {
        条目.get(字段名).is_some_and(|字段值| 字段值 == 期望值)
    }
}

pub(super) fn 值序号(候选值: &serde_json::Value) -> u8 {
    match 候选值 {
        serde_json::Value::Null => 0,
        serde_json::Value::Bool(_) => 1,
        serde_json::Value::Number(_) => 2,
        serde_json::Value::String(_) => 3,
        serde_json::Value::Array(_) => 4,
        serde_json::Value::Object(_) => 5,
    }
}

pub(super) fn 比较值(左项: &serde_json::Value, 右项: &serde_json::Value) -> std::cmp::Ordering {
    let (左序, 右序) = (值序号(左项), 值序号(右项));
    if 左序 != 右序 {
        return 左序.cmp(&右序);
    }
    match (左项, 右项) {
        (serde_json::Value::Number(左数), serde_json::Value::Number(右数)) => {
            左数.as_f64().unwrap_or(0.0).total_cmp(&右数.as_f64().unwrap_or(0.0))
        }
        (serde_json::Value::String(左文), serde_json::Value::String(右文)) => 左文.cmp(右文),
        (serde_json::Value::Bool(左逻), serde_json::Value::Bool(右逻)) => 左逻.cmp(右逻),
        _ => std::cmp::Ordering::Equal,
    }
}

pub(super) fn 取比较键<'a>(条目: &'a serde_json::Value, 字段名: &str, 直接匹配: bool) -> &'a serde_json::Value {
    if 直接匹配 || 字段名.is_empty() {
        条目
    } else {
        条目.get(字段名).unwrap_or(&serde_json::Value::Null)
    }
}

pub(super) fn 标量文本(候选值: &serde_json::Value) -> String {
    match 候选值 {
        serde_json::Value::String(内文) => 内文.clone(),
        serde_json::Value::Null => String::new(),
        serde_json::Value::Bool(逻辑值) => {
            if *逻辑值 {
                "真".to_owned()
            } else {
                "假".to_owned()
            }
        }
        其他值 => 其他值.to_string(),
    }
}
