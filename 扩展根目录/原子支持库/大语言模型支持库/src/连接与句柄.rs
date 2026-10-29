use crate::编号与码面::错误码;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

/// 一个已登记的模型连接；不含任何租约计时，句柄显式释放。
#[derive(Clone)]
pub(crate) struct 连接句柄 {
    pub(crate) 请求地址: String,
    pub(crate) 接口密钥: String,
    pub(crate) 模型: String,
    pub(crate) 协议: String,
    pub(crate) 静态头表: Vec<(String, String)>,
}

/// 快照里每条句柄的摘要：编号、模型名、请求地址。
pub(crate) type 句柄摘要 = Vec<(u64, String, String)>;

/// 句柄上限：满则明确拒绝，不静默顶掉别人。
const 句柄上限: usize = 64;

static 句柄存储: OnceLock<Mutex<HashMap<u64, 连接句柄>>> = OnceLock::new();
static 句柄序号: AtomicU64 = AtomicU64::new(0);

fn 句柄锁() -> Result<std::sync::MutexGuard<'static, HashMap<u64, 连接句柄>>, u32> {
    句柄存储.get_or_init(Default::default).lock().map_err(|_| 错误码::资源受限)
}

/// 对话连接：协议只接受 chat_completions。
pub(crate) fn 连接对话模型(模型: &str, 模型地址: &str, 接口密钥: &str, 协议: &str, 静态头表: Vec<(String, String)>) -> Result<u64, u32> {
    if 协议 != "chat_completions" { return Err(错误码::协议不支持); }
    登记(模型, 模型地址, 接口密钥, "chat_completions", 静态头表)
}

/// 向量连接：协议只接受 embeddings。
pub(crate) fn 连接向量模型(模型: &str, 模型地址: &str, 接口密钥: &str, 协议: &str, 静态头表: Vec<(String, String)>) -> Result<u64, u32> {
    if 协议 != "embeddings" { return Err(错误码::协议不支持); }
    登记(模型, 模型地址, 接口密钥, "embeddings", 静态头表)
}

/// 重排连接：协议只接受 rerank。
pub(crate) fn 连接重排模型(模型: &str, 模型地址: &str, 接口密钥: &str, 协议: &str, 静态头表: Vec<(String, String)>) -> Result<u64, u32> {
    if 协议 != "rerank" { return Err(错误码::协议不支持); }
    登记(模型, 模型地址, 接口密钥, "rerank", 静态头表)
}

fn 登记(模型: &str, 模型地址: &str, 接口密钥: &str, 协议: &str, 静态头表: Vec<(String, String)>) -> Result<u64, u32> {
    if 模型.trim().is_empty() { return Err(错误码::参数不合法); }
    let 请求地址 = 补全地址(模型地址, 协议)?;
    let mut 句柄表 = 句柄锁()?;
    if 句柄表.len() >= 句柄上限 { return Err(错误码::资源受限); }
    let 新句柄号 = 句柄序号.fetch_add(1, Ordering::AcqRel) + 1;
    句柄表.insert(新句柄号, 连接句柄 {
        请求地址,
        接口密钥: 接口密钥.to_owned(),
        模型: 模型.to_owned(),
        协议: 协议.to_owned(),
        静态头表,
    });
    Ok(新句柄号)
}

/// 端点后缀按协议定，未带端点时补全；地址只收 http/https。
fn 补全地址(模型地址: &str, 协议: &str) -> Result<String, u32> {
    let 地址文本 = 模型地址.trim();
    if 地址文本.is_empty() || !(地址文本.starts_with("http://") || 地址文本.starts_with("https://")) {
        return Err(错误码::参数不合法);
    }
    let 端点后缀 = match 协议 {
        "chat_completions" => "chat/completions",
        "embeddings" => "embeddings",
        "rerank" => "rerank",
        _ => return Err(错误码::协议不支持),
    };
    if 地址文本.ends_with(&format!("/{端点后缀}")) { return Ok(地址文本.to_owned()); }
    let 基地址 = 地址文本.trim_end_matches('/');
    if 基地址.ends_with("/v1") {
        Ok(format!("{基地址}/{端点后缀}"))
    } else {
        Ok(format!("{基地址}/v1/{端点后缀}"))
    }
}

pub(crate) fn 取句柄(句柄编号: u64) -> Result<连接句柄, u32> {
    句柄锁()?.get(&句柄编号).cloned().ok_or(错误码::句柄无效)
}

/// 取句柄并核对协议：对话任务不认向量/重排句柄，反之亦然。
pub(crate) fn 取句柄与协议(句柄编号: u64, 期望协议: &str) -> Result<连接句柄, u32> {
    let 连接值 = 取句柄(句柄编号)?;
    if 连接值.协议 != 期望协议 { return Err(错误码::协议不支持); }
    Ok(连接值)
}

pub(crate) fn 释放(句柄编号: u64) -> Result<bool, u32> {
    Ok(句柄锁()?.remove(&句柄编号).is_some())
}

pub(crate) fn 快照() -> Result<(usize, 句柄摘要), u32> {
    let 句柄表 = 句柄锁()?;
    Ok((句柄表.len(), 句柄表.iter().map(|(编号, 连接值)| (*编号, 连接值.模型.clone(), 连接值.请求地址.clone())).collect()))
}
