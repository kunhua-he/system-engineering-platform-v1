use serde_json::Value;
use std::collections::BTreeMap;

/// 一条流式生成的累计状态：逐行喂入，随时可读。
#[derive(Default)]
pub(crate) struct 生成状态 {
    pub(crate) 回复内容: String,
    pub(crate) 思考内容: String,
    pub(crate) 工具调用: Vec<Value>,
    工具分片: BTreeMap<u64, (String, String, String)>,
    pub(crate) 结束原因: String,
    pub(crate) 用量信息: Value,
    pub(crate) 已完成: bool,
    pub(crate) 失败说明: String,
}

impl 生成状态 {
    /// 处理一行 SSE 文本；心跳、注释与无法解析的行按忽略处理。
    pub(crate) fn 处理事件行(&mut self, 事件行文本: &str) {
        let 去空白行 = 事件行文本.trim_start();
        if 去空白行.is_empty() || 去空白行.starts_with(':') { return; }
        let Some(事件数据) = 去空白行.strip_prefix("data:") else { return; };
        let 事件数据 = 事件数据.trim();
        if 事件数据 == "[DONE]" { self.已完成 = true; return; }
        let Ok(事件值) = serde_json::from_str::<Value>(事件数据) else { return; };
        if let Some(错误对象) = 事件值.get("error") {
            self.失败说明 = 错误对象.get("message").and_then(Value::as_str).unwrap_or("上游返回错误").to_owned();
            return;
        }
        if let Some(用量值) = 事件值.get("usage") && !用量值.is_null() {
            self.用量信息 = 用量值.clone();
        }
        let Some(首个选项) = 事件值.get("choices").and_then(Value::as_array).and_then(|选项表| 选项表.first()) else { return; };
        if let Some(增量) = 首个选项.get("delta") {
            if let Some(增量文本) = 增量.get("content").and_then(Value::as_str) { self.回复内容.push_str(增量文本); }
            if let Some(思考文本) = 增量.get("reasoning_content").and_then(Value::as_str) { self.思考内容.push_str(思考文本); }
            if let Some(调用表) = 增量.get("tool_calls").and_then(Value::as_array) {
                for 调用项 in 调用表 {
                    let 调用序号 = 调用项.get("index").and_then(Value::as_u64).unwrap_or(0);
                    let 分片记录 = self.工具分片.entry(调用序号).or_default();
                    if let Some(调用标识) = 调用项.get("id").and_then(Value::as_str) { 分片记录.0 = 调用标识.to_owned(); }
                    if let Some(调用名称) = 调用项.get("function").and_then(|函数项| 函数项.get("name")).and_then(Value::as_str) { 分片记录.1 = 调用名称.to_owned(); }
                    if let Some(参数片段) = 调用项.get("function").and_then(|函数项| 函数项.get("arguments")).and_then(Value::as_str) { 分片记录.2.push_str(参数片段); }
                }
            }
        }
        if let Some(结束标识) = 首个选项.get("finish_reason").and_then(Value::as_str) { self.结束原因 = 结束标识.to_owned(); }
    }

    /// 线程收尾：把分片工具调用拼成完整表，补默认结束原因。
    pub(crate) fn 收尾(&mut self) {
        for (调用序号, (调用标识, 调用名称, 参数文本)) in std::mem::take(&mut self.工具分片) {
            self.工具调用.push(serde_json::json!({
                "序号": 调用序号, "id": 调用标识, "名称": 调用名称, "参数": 参数文本,
            }));
        }
        if self.结束原因.is_empty() { self.结束原因 = "stop".to_owned(); }
    }
}
