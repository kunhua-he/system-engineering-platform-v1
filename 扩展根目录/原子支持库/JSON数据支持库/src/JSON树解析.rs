// 使用引擎原始值逐层装配，避免任意精度数字的私有键通道吞掉同名普通对象。
pub fn 解析JSON树(原文: &str) -> Result<serde_json::Value, serde_json::Error> {
    let 首字节 = 原文
        .trim_start_matches([' ', '\r', '\n', '\t'])
        .as_bytes()
        .first()
        .copied();
    Ok(match 首字节 {
        Some(b'{') => {
            let 原始成员表: std::collections::BTreeMap<String, Box<serde_json::value::RawValue>> =
                serde_json::from_str(原文)?;
            let mut 成员表 = serde_json::Map::new();
            for (键名, 原始项) in 原始成员表 {
                成员表.insert(键名, 解析JSON树(原始项.get())?);
            }
            serde_json::Value::Object(成员表)
        }
        Some(b'[') => {
            let 原始元素表: Vec<Box<serde_json::value::RawValue>> = serde_json::from_str(原文)?;
            let 元素表 = 原始元素表
                .into_iter()
                .map(|原始项| 解析JSON树(原始项.get()))
                .collect::<Result<Vec<_>, _>>()?;
            serde_json::Value::Array(元素表)
        }
        Some(b'"') => serde_json::Value::String(serde_json::from_str(原文)?),
        Some(b't' | b'f') => serde_json::Value::Bool(serde_json::from_str(原文)?),
        Some(b'n') => {
            serde_json::from_str::<()>(原文)?;
            serde_json::Value::Null
        }
        _ => serde_json::Value::Number(serde_json::from_str(原文)?),
    })
}
