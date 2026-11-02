//! 展平：路径拼接、字典展平递归、结构条目展平递归与其上下文。

pub(super) fn 拼接路径(路径前缀: &str, 分隔符: &str, 末段: &str) -> String {
    if 路径前缀.is_empty() {
        末段.to_owned()
    } else {
        format!("{路径前缀}{分隔符}{末段}")
    }
}

pub(super) fn 展平字典递归(
    候选值: &serde_json::Value,
    路径前缀: &str,
    分隔符: &str,
    剩余深度: usize,
    收录: &mut serde_json::Map<String, serde_json::Value>,
) {
    match 候选值 {
        serde_json::Value::Object(成员表) if 剩余深度 > 1 => {
            for (字段名, 字段值) in 成员表 {
                展平字典递归(字段值, &拼接路径(路径前缀, 分隔符, 字段名), 分隔符, 剩余深度 - 1, 收录);
            }
        }
        其他值 => {
            收录.insert(路径前缀.to_owned(), 其他值.clone());
        }
    }
}

pub(super) struct 展平上下文<'a> {
    pub(super) 分隔符: &'a str,
    pub(super) 索引格式: &'a str,
    pub(super) 超深标记: &'a str,
    pub(super) 根路径: &'a str,
    pub(super) 最大条目数: usize,
    pub(super) 条目表: Vec<serde_json::Value>,
    pub(super) 已截断: bool,
}

pub(super) fn 渲染索引(格式: &str, 序号: usize) -> String {
    格式.replace("{索引}", &序号.to_string())
}

pub(super) fn 展平条目递归(候选值: &serde_json::Value, 路径: &str, 剩余深度: usize, 上下文: &mut 展平上下文<'_>) {
    if 上下文.条目表.len() >= 上下文.最大条目数 {
        上下文.已截断 = true;
        return;
    }
    match 候选值 {
        serde_json::Value::Object(成员表) if 剩余深度 > 0 => {
            if 成员表.is_empty() {
                上下文.条目表.push(serde_json::json!({
                    "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                    "值": serde_json::Value::Object(成员表.clone()),
                    "超深": false,
                }));
                return;
            }
            for (字段名, 字段值) in 成员表 {
                展平条目递归(字段值, &拼接路径(路径, 上下文.分隔符, 字段名), 剩余深度 - 1, 上下文);
            }
        }
        serde_json::Value::Array(列表值) if 剩余深度 > 0 => {
            if 列表值.is_empty() {
                上下文.条目表.push(serde_json::json!({
                    "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                    "值": serde_json::Value::Array(Vec::new()),
                    "超深": false,
                }));
                return;
            }
            for (序号, 元素值) in 列表值.iter().enumerate() {
                let 索引段 = 渲染索引(上下文.索引格式, 序号);
                展平条目递归(元素值, &拼接路径(路径, 上下文.分隔符, &索引段), 剩余深度 - 1, 上下文);
            }
        }
        serde_json::Value::Object(_) | serde_json::Value::Array(_) => {
            上下文.条目表.push(serde_json::json!({
                "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                "值": 上下文.超深标记,
                "超深": true,
            }));
        }
        标量值 => {
            上下文.条目表.push(serde_json::json!({
                "路径": if 路径.is_empty() { 上下文.根路径 } else { 路径 },
                "值": 标量值.clone(),
                "超深": false,
            }));
        }
    }
}
