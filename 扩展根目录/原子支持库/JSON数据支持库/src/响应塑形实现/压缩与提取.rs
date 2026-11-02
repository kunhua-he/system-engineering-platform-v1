//! 压缩与提取：指定字段的连续空白折叠、文本末尾按行首前缀回溯提取 JSON。

pub(super) fn 压缩描述字段值(条目值: &serde_json::Value, 字段名: &str) -> serde_json::Value {
    match 条目值 {
        serde_json::Value::Array(列表值) => {
            let 折叠项: Vec<serde_json::Value> = 列表值
                .iter()
                .map(|条目项| 压缩描述字段值(条目项, 字段名))
                .collect();
            serde_json::Value::Array(折叠项)
        }
        serde_json::Value::Object(成员表) => {
            let mut 新成员 = serde_json::Map::new();
            for (成员键, 条目项) in 成员表 {
                let 压缩后值 = if 成员键 == 字段名 && 条目项.is_string() {
                    serde_json::Value::String(
                        条目项.as_str()
                            .unwrap_or("")
                            .split_whitespace()
                            .collect::<Vec<_>>()
                            .join(" "),
                    )
                } else {
                    压缩描述字段值(条目项, 字段名)
                };
                新成员.insert(成员键.clone(), 压缩后值);
            }
            serde_json::Value::Object(新成员)
        }
        其他值 => 其他值.clone(),
    }
}

pub(super) fn 提取前缀JSON值(文本值: &str, 行首前缀: &str) -> serde_json::Value {
    use serde_json::json;
    for 单行 in 文本值.lines().rev() {
        let 行文本 = 单行.trim();
        if !行文本.starts_with(行首前缀) {
            continue;
        }
        let 剩余文本 = 行文本[行首前缀.len()..].trim();
        return match serde_json::from_str::<serde_json::Value>(剩余文本) {
            Ok(解析值 @ serde_json::Value::Object(_)) => {
                json!({ "找到": true, "数据": 解析值 })
            }
            _ => json!({ "找到": false }),
        };
    }
    json!({ "找到": false })
}
