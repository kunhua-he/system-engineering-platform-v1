use crate::编号与码面::错误码;
use serde_json::{Value, json};

/// 构造 chat_completions 流式请求体；只做形状校验，不改写调用方的业务字段。
pub(crate) fn 构造请求(
    模型: &str,
    消息列表: &Value,
    系统提示词: &str,
    温度: f64,
    最大令牌数: u64,
    工具: &Value,
    响应格式: &Value,
) -> Result<Vec<u8>, u32> {
    let 消息数组 = 消息列表.as_array().ok_or(错误码::参数不合法)?;
    if 消息数组.is_empty() { return Err(错误码::参数不合法); }
    if !(0.0..=2.0).contains(&温度) { return Err(错误码::参数不合法); }
    if 最大令牌数 > 131072 { return Err(错误码::参数不合法); }
    let mut 消息容器: Vec<Value> = Vec::with_capacity(消息数组.len() + 1);
    if !系统提示词.is_empty() {
        消息容器.push(json!({"role": "system", "content": 系统提示词}));
    }
    for 消息项 in 消息数组 {
        let 消息对象 = 消息项.as_object().ok_or(错误码::参数不合法)?;
        if !消息对象.get("role").is_some_and(Value::is_string) { return Err(错误码::参数不合法); }
        消息容器.push(消息项.clone());
    }
    let mut 请求体 = serde_json::Map::new();
    请求体.insert("model".into(), json!(模型));
    请求体.insert("messages".into(), Value::Array(消息容器));
    请求体.insert("stream".into(), json!(true));
    if 温度 > 0.0 { 请求体.insert("temperature".into(), json!(温度)); }
    if 最大令牌数 > 0 { 请求体.insert("max_tokens".into(), json!(最大令牌数)); }
    if 工具.as_array().is_some_and(|项表| !项表.is_empty()) { 请求体.insert("tools".into(), 工具.clone()); }
    if 响应格式.as_object().is_some_and(|格式对象| !格式对象.is_empty()) { 请求体.insert("response_format".into(), 响应格式.clone()); }
    serde_json::to_vec(&Value::Object(请求体)).map_err(|_| 错误码::参数不合法)
}
