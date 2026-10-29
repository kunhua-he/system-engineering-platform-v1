use crate::编号与码面::错误码;
use crate::协议构造;
use crate::协议解析::生成状态;
use crate::连接与句柄;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::hash::{BuildHasher, RandomState};
use std::io::{BufRead, BufReader, Read};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

struct 任务登记 {
    取消标志: Arc<AtomicBool>,
    状态容器: Arc<Mutex<生成状态>>,
    工作线程: Option<JoinHandle<()>>,
}

#[derive(Default)]
struct 任务总表 {
    登记表: HashMap<u64, 任务登记>,
    停止接收: bool,
}

const 任务上限: usize = 64;
const 请求正文上限: usize = 1048576;
const 内容上限: usize = 8 * 1024 * 1024;
const 错误片段上限: u64 = 4096;

static 任务存储: OnceLock<Mutex<任务总表>> = OnceLock::new();

fn 任务锁() -> Result<std::sync::MutexGuard<'static, 任务总表>, u32> {
    任务存储.get_or_init(Default::default).lock().map_err(|_| 错误码::资源受限)
}

fn 说明(失败码: u32) -> &'static str {
    match 失败码 {
        错误码::参数不合法 => "生成参数不合法",
        错误码::协议不支持 => "协议不支持",
        错误码::句柄无效 => "句柄不存在或已释放",
        错误码::任务无效 => "生成任务不存在",
        错误码::资源受限 => "生成内容或资源超出上限",
        错误码::响应不合法 => "上游响应不是可解析的流式事件",
        _ => "上游调用失败",
    }
}

/// 一次生成请求的业务载荷；字段数量固定，避免长参数表。
pub(crate) struct 生成请求<'a> {
    pub(crate) 消息列表: &'a Value,
    pub(crate) 系统提示词: &'a str,
    pub(crate) 温度: f64,
    pub(crate) 最大令牌数: u64,
    pub(crate) 工具: &'a Value,
    pub(crate) 响应格式: &'a Value,
    pub(crate) 附加请求头: &'a Value,
}

pub(crate) fn 提交(句柄编号: u64, 请求: 生成请求<'_>) -> Result<u64, u32> {
    let 连接值 = 连接与句柄::取句柄与协议(句柄编号, "chat_completions")?;
    let 请求正文 = 协议构造::构造请求(&连接值.模型, 请求.消息列表, 请求.系统提示词, 请求.温度, 请求.最大令牌数, 请求.工具, 请求.响应格式)?;
    if 请求正文.len() > 请求正文上限 { return Err(错误码::资源受限); }
    let 单次头表 = crate::业务实现::解析头表(请求.附加请求头)?;
    let mut 附加头表 = 连接值.静态头表.clone();
    附加头表.extend(单次头表);
    let mut 任务表 = 任务锁()?;
    if 任务表.停止接收 { return Err(错误码::资源受限); }
    if 任务表.登记表.len() >= 任务上限 { return Err(错误码::资源受限); }
    let 任务句柄 = 新任务号(&任务表)?;
    let 取消标志 = Arc::new(AtomicBool::new(false));
    let 状态容器 = Arc::new(Mutex::new(生成状态::default()));
    任务表.登记表.insert(任务句柄, 任务登记 {
        取消标志: 取消标志.clone(),
        状态容器: 状态容器.clone(),
        工作线程: None,
    });
    let 线程取消标志 = 取消标志.clone();
    let 线程状态容器 = 状态容器.clone();
    let 请求地址 = 连接值.请求地址.clone();
    let 接口密钥 = 连接值.接口密钥.clone();
    let 启动结果 = std::thread::Builder::new().name("模型生成任务".into()).spawn(move || {
        let 执行结果 = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            跑流式请求(&请求地址, &接口密钥, &附加头表, &请求正文, &线程取消标志, &线程状态容器)
        }))
        .unwrap_or(Err(错误码::上游失败));
        if let Ok(mut 状态值) = 线程状态容器.lock() {
            状态值.收尾();
            if let Err(失败码) = 执行结果 && 状态值.失败说明.is_empty() {
                状态值.失败说明 = 说明(失败码).to_owned();
            }
            状态值.已完成 = true;
        }
    });
    match 启动结果 {
        Ok(工作线程) => {
            if let Some(登记项) = 任务表.登记表.get_mut(&任务句柄) { 登记项.工作线程 = Some(工作线程); }
            Ok(任务句柄)
        }
        Err(_) => {
            任务表.登记表.remove(&任务句柄);
            Err(错误码::资源受限)
        }
    }
}

fn 新任务号(任务表: &任务总表) -> Result<u64, u32> {
    for _ in 0..64 {
        let 候选号 = RandomState::new().hash_one((Instant::now(), std::process::id()));
        if 候选号 != 0 && !任务表.登记表.contains_key(&候选号) { return Ok(候选号); }
    }
    Err(错误码::资源受限)
}

fn 跑流式请求(
    请求地址: &str,
    接口密钥: &str,
    附加头表: &[(String, String)],
    请求正文: &[u8],
    取消标志: &AtomicBool,
    状态容器: &Mutex<生成状态>,
) -> Result<(), u32> {
    let 代理配置 = ureq::Agent::config_builder()
        .timeout_connect(Some(Duration::from_millis(5000)))
        .timeout_recv_response(Some(Duration::from_millis(5000)))
        .timeout_recv_body(Some(Duration::from_millis(5000)))
        .proxy(None)
        .max_redirects(0)
        .http_status_as_error(false)
        .build();
    let 请求代理 = ureq::Agent::new_with_config(代理配置);
    let mut 请求构造 = 请求代理
        .post(请求地址)
        .header("Content-Type", "application/json")
        .header("Accept", "text/event-stream");
    if !接口密钥.is_empty() {
        请求构造 = 请求构造.header("Authorization", format!("Bearer {接口密钥}"));
    }
    for (头名称, 头内容) in 附加头表 {
        请求构造 = 请求构造.header(头名称.as_str(), 头内容.as_str());
    }
    let mut 响应 = 请求构造.send(请求正文).map_err(|_| 错误码::上游失败)?;
    let 响应状态码 = 响应.status().as_u16();
    if 响应状态码 != 200 {
        let mut 错误片段 = String::new();
        let _ = 响应.body_mut().as_reader().take(错误片段上限).read_to_string(&mut 错误片段);
        let mut 状态值 = 状态容器.lock().map_err(|_| 错误码::资源受限)?;
        状态值.失败说明 = format!("上游状态 {响应状态码}：{}", 错误片段.trim());
        状态值.已完成 = true;
        return Ok(());
    }
    let 响应读取器 = BufReader::new(响应.body_mut().as_reader());
    for 行结果 in 响应读取器.lines() {
        if 取消标志.load(Ordering::Acquire) { return Ok(()); }
        let Ok(事件行文本) = 行结果 else { break; };
        let mut 状态值 = 状态容器.lock().map_err(|_| 错误码::资源受限)?;
        if 状态值.回复内容.len() + 状态值.思考内容.len() > 内容上限 { return Err(错误码::资源受限); }
        状态值.处理事件行(&事件行文本);
        let 已完成 = 状态值.已完成;
        drop(状态值);
        if 已完成 { break; }
    }
    Ok(())
}

pub(crate) fn 读取(任务句柄: u64) -> Result<Value, u32> {
    let 任务表 = 任务锁()?;
    let 登记项 = 任务表.登记表.get(&任务句柄).ok_or(错误码::任务无效)?;
    let 线程已退 = 登记项.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
    let 状态值 = 登记项.状态容器.lock().map_err(|_| 错误码::资源受限)?;
    let 失败码 = if 状态值.失败说明.is_empty() { 0 } else { 错误码::上游失败 };
    Ok(json!({
        "已完成": 状态值.已完成 && 线程已退,
        "资源在途": !线程已退,
        "内容": 状态值.回复内容.clone(),
        "思考": 状态值.思考内容.clone(),
        "工具调用": 状态值.工具调用.clone(),
        "结束原因": 状态值.结束原因.clone(),
        "用量": 状态值.用量信息.clone(),
        "错误码": 失败码,
        "错误信息": 状态值.失败说明.clone(),
    }))
}

pub(crate) fn 取消(任务句柄: u64) -> Result<bool, u32> {
    let 任务表 = 任务锁()?;
    let 登记项 = 任务表.登记表.get(&任务句柄).ok_or(错误码::任务无效)?;
    登记项.取消标志.store(true, Ordering::Release);
    Ok(true)
}

/// 真 = 线程已退出且归属已移除；假 = 线程仍在跑，仍持归属。
pub(crate) fn 释放(任务句柄: u64) -> Result<bool, u32> {
    let mut 任务表 = 任务锁()?;
    let 线程已退 = {
        let 登记项 = 任务表.登记表.get_mut(&任务句柄).ok_or(错误码::任务无效)?;
        登记项.取消标志.store(true, Ordering::Release);
        登记项.工作线程.as_ref().is_some_and(JoinHandle::is_finished)
    };
    if !线程已退 { return Ok(false); }
    let 待释放登记 = 任务表.登记表.remove(&任务句柄).ok_or(错误码::任务无效)?;
    if let Some(工作线程) = 待释放登记.工作线程 { let _ = 工作线程.join(); }
    Ok(true)
}

pub(crate) fn 统计() -> Result<(usize, usize), u32> {
    let 任务表 = 任务锁()?;
    let 在途数 = 任务表.登记表.values().filter(|登记项| !登记项.工作线程.as_ref().is_some_and(JoinHandle::is_finished)).count();
    Ok((任务表.登记表.len(), 在途数))
}

pub(crate) unsafe extern "C" fn 生命周期通知(通知编号: v1_contract::通知号, _: usize, _: usize) -> isize {
    let Ok(mut 任务表) = 任务锁() else { return v1_contract::通知返回::延迟释放; };
    match 通知编号.取号值() {
        2000 => { 任务表.停止接收 = false; 0 }
        2001..=2003 => {
            任务表.停止接收 = true;
            for 登记项 in 任务表.登记表.values_mut() { 登记项.取消标志.store(true, Ordering::Release); }
            let 仍有在途 = 任务表.登记表.values().any(|登记项| !登记项.工作线程.as_ref().is_some_and(JoinHandle::is_finished));
            if 仍有在途 { v1_contract::通知返回::延迟释放 } else { 0 }
        }
        _ => 0,
    }
}
