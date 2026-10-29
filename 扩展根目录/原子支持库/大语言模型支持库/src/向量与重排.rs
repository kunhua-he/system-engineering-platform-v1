use crate::编号与码面::错误码;
use crate::连接与句柄;
use serde_json::{Value, json};
use std::io::Read;
use std::time::Duration;

/// 同步调用的预算：连接、响应头、响应体各五秒，与平台五秒口径一致。
const 同步预算毫秒: u64 = 5000;
const 请求正文上限: usize = 1 << 20;
const 响应正文上限: u64 = 8 << 20;
const 错误片段上限: u64 = 4096;
/// 一次调用可带的条目数：向量文本至 16 条，重排文档至 32 条。
const 文本条数上限: usize = 16;
const 文档条数上限: usize = 32;
const 单文本字节上限: usize = 2048;
const 单文档字节上限: usize = 4096;
const 维度上限: u64 = 8192;

fn 建代理() -> ureq::Agent {
    let 代理配置 = ureq::Agent::config_builder()
        .timeout_connect(Some(Duration::from_millis(同步预算毫秒)))
        .timeout_recv_response(Some(Duration::from_millis(同步预算毫秒)))
        .timeout_recv_body(Some(Duration::from_millis(同步预算毫秒)))
        .proxy(None)
        .max_redirects(0)
        .http_status_as_error(false)
        .build();
    ureq::Agent::new_with_config(代理配置)
}

fn 发送(连接值: &连接与句柄::连接句柄, 请求体: &Value) -> Result<Value, u32> {
    let 正文字节 = serde_json::to_vec(请求体).map_err(|_| 错误码::参数不合法)?;
    if 正文字节.len() > 请求正文上限 { return Err(错误码::资源受限); }
    let 代理 = 建代理();
    let mut 请求构造 = 代理.post(&连接值.请求地址).header("Content-Type", "application/json");
    if !连接值.接口密钥.is_empty() {
        请求构造 = 请求构造.header("Authorization", &format!("Bearer {}", 连接值.接口密钥));
    }
    for (头名称, 头内容) in &连接值.静态头表 {
        请求构造 = 请求构造.header(头名称.as_str(), 头内容.as_str());
    }
    let mut 响应 = 请求构造.send(&正文字节[..]).map_err(|失败原因| {
        eprintln!("大语言模型支持库 同步调用失败：{失败原因}");
        错误码::上游失败
    })?;
    if 响应.status() != 200 {
        let mut 错误片段 = String::new();
        let _ = 响应.body_mut().as_reader().take(错误片段上限).read_to_string(&mut 错误片段);
        eprintln!("大语言模型支持库 上游状态 {}：{}", 响应.status(), 错误片段.trim());
        return Err(错误码::上游失败);
    }
    let mut 响应正文 = String::new();
    响应.body_mut().as_reader().take(响应正文上限).read_to_string(&mut 响应正文)
        .map_err(|_| 错误码::响应不合法)?;
    serde_json::from_str(&响应正文).map_err(|_| 错误码::响应不合法)
}

/// 校验文本列表：1 至 16 条、每条非空且不超过 2048 字节。
fn 取文本表(文本列表: &Value, 条数上限: usize, 单条上限: usize) -> Result<Vec<String>, u32> {
    let 数组内容 = 文本列表.as_array().ok_or(错误码::参数不合法)?;
    if 数组内容.is_empty() || 数组内容.len() > 条数上限 { return Err(错误码::参数不合法); }
    let mut 文本表 = Vec::with_capacity(数组内容.len());
    for 条目 in 数组内容 {
        let 条目文本 = 条目.as_str().ok_or(错误码::参数不合法)?.trim();
        if 条目文本.is_empty() || 条目文本.len() > 单条上限 { return Err(错误码::参数不合法); }
        文本表.push(条目文本.to_owned());
    }
    Ok(文本表)
}

/// 生成嵌入：返回与入参同序的向量表；维度非 0 时逐条校验长度。
pub(crate) fn 生成嵌入(句柄编号: u64, 文本列表: &Value, 维度: u64) -> Result<Vec<Vec<f64>>, u32> {
    if 维度 > 维度上限 { return Err(错误码::参数不合法); }
    let 连接值 = 连接与句柄::取句柄与协议(句柄编号, "embeddings")?;
    let 文本表 = 取文本表(文本列表, 文本条数上限, 单文本字节上限)?;
    let 响应值 = 发送(&连接值, &json!({"model": 连接值.模型, "input": 文本表}))?;
    let 数据数组 = 响应值.get("data").and_then(Value::as_array).ok_or(错误码::响应不合法)?;
    if 数据数组.len() != 文本表.len() { return Err(错误码::响应不合法); }
    let mut 向量表 = Vec::with_capacity(数据数组.len());
    for 数据项 in 数据数组 {
        let 向量数组 = 数据项.get("embedding").and_then(Value::as_array).ok_or(错误码::响应不合法)?;
        if 维度 != 0 && 向量数组.len() as u64 != 维度 { return Err(错误码::响应不合法); }
        let mut 向量 = Vec::with_capacity(向量数组.len());
        for 分量 in 向量数组 {
            向量.push(分量.as_f64().ok_or(错误码::响应不合法)?);
        }
        向量表.push(向量);
    }
    Ok(向量表)
}

/// 执行重排：返回 (文档序, 分数) 列表，按分数降序；返回条数 0 表示全部。
pub(crate) fn 执行重排(句柄编号: u64, 查询: &str, 文档列表: &Value, 返回条数: u64) -> Result<Vec<(u64, f64)>, u32> {
    let 查询文本 = 查询.trim();
    if 查询文本.is_empty() || 查询文本.len() > 单文本字节上限 { return Err(错误码::参数不合法); }
    let 连接值 = 连接与句柄::取句柄与协议(句柄编号, "rerank")?;
    let 文档表 = 取文本表(文档列表, 文档条数上限, 单文档字节上限)?;
    if 返回条数 > 文档表.len() as u64 { return Err(错误码::参数不合法); }
    let 响应值 = 发送(&连接值, &json!({"model": 连接值.模型, "query": 查询文本, "documents": 文档表}))?;
    let 结果数组 = 响应值.get("results").and_then(Value::as_array).ok_or(错误码::响应不合法)?;
    if 结果数组.is_empty() { return Err(错误码::响应不合法); }
    let mut 结果表 = Vec::with_capacity(结果数组.len());
    for 结果项 in 结果数组 {
        let 文档序 = 结果项.get("index").and_then(Value::as_u64).ok_or(错误码::响应不合法)?;
        if 文档序 >= 文档表.len() as u64 { return Err(错误码::响应不合法); }
        let 分数 = 结果项.get("relevance_score").and_then(Value::as_f64).ok_or(错误码::响应不合法)?;
        结果表.push((文档序, 分数));
    }
    结果表.sort_by(|左项, 右项| 右项.1.total_cmp(&左项.1));
    if 返回条数 > 0 { 结果表.truncate(返回条数 as usize); }
    Ok(结果表)
}
