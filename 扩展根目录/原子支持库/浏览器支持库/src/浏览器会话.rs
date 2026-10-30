//! 浏览器会话：起 Chrome 无头进程、开标签、维护底座进程内的会话表。
//!
//! 会话生命周期归底座 —— 句柄是底座进程内的一个整数，关掉句柄就杀掉对应的
//! Chrome 与标签，进程退出也不留孤儿（Chrome 以 `kill_on_drop` 语义收尾）。

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, OnceLock};

use serde_json::{json, Value};

use crate::编号与码面::错误码;
use crate::浏览器通道::{请求调试口, 调试连接};

/// 一条活着的浏览器会话
pub(crate) struct 会话 {
    pub 进程: Child,
    pub 标签连接: 调试连接,
    pub 指令序: u64,
    pub 临时目录: String,
}

static 会话表: OnceLock<Mutex<HashMap<u32, 会话>>> = OnceLock::new();

fn 表() -> &'static Mutex<HashMap<u32, 会话>> {
    会话表.get_or_init(|| Mutex::new(HashMap::new()))
}

const 会话上限: usize = 8;

/// Chrome 可执行文件位置；找不到就如实报平台不支持
fn 查浏览器路径() -> Result<String, u32> {
    let 候选 = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ];
    for 路径 in 候选 {
        if std::path::Path::new(路径).is_file() {
            return Ok(路径.to_string());
        }
    }
    Err(错误码::平台不支持)
}

/// 起 Chrome 并从它的输出里取调试端口。
///
/// **两条流都要读**：Chrome 把「DevTools listening on ws://…」打在 stderr，
/// 但某些构建/参数组合会走 stdout（实测踩过：只读一条永远等不到，进程挂到超时）。
fn 起浏览器(临时目录: &str) -> Result<(Child, u16), u32> {
    let 路径 = 查浏览器路径()?;
    let mut 子进程 = Command::new(&路径)
        .args([
            "--headless=new",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-extensions",
            "--mute-audio",
            &format!("--user-data-dir={}", 临时目录),
            "about:blank",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| 错误码::启动失败)?;
    let (发送端, 接收端) = std::sync::mpsc::channel::<u16>();
    for 管道 in [
        子进程.stdout.take().map(|流| Box::new(流) as Box<dyn Read + Send>),
        子进程.stderr.take().map(|流| Box::new(流) as Box<dyn Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let 发送副本 = 发送端.clone();
        std::thread::spawn(move || {
            let mut 读取器 = BufReader::new(管道);
            let mut 行缓冲 = String::new();
            loop {
                行缓冲.clear();
                if 读取器.read_line(&mut 行缓冲).unwrap_or(0) == 0 {
                    break;
                }
                const 前缀: &str = "DevTools listening on ws://";
                if let Some(位) = 行缓冲.find(前缀) {
                    let 尾巴 = &行缓冲[位 + 前缀.len()..];
                    let 主机段 = 尾巴.split('/').next().unwrap_or("");
                    if let Some(端口) = 主机段.rsplit(':').next().and_then(|文| 文.trim().parse::<u16>().ok()) {
                        let _ = 发送副本.send(端口);
                        break;
                    }
                }
            }
            // 之后继续把剩余输出读空，避免管道写满把 Chrome 卡住
            let mut 丢弃 = String::new();
            while 读取器.read_line(&mut 丢弃).unwrap_or(0) > 0 {
                丢弃.clear();
            }
        });
    }
    match 接收端.recv_timeout(std::time::Duration::from_secs(25)) {
        Ok(端口) => Ok((子进程, 端口)),
        Err(_) => {
            let _ = 子进程.kill();
            let _ = 子进程.wait();
            Err(错误码::启动失败)
        }
    }
}

/// 开一个新标签，返回它自己的调试地址路径
fn 开标签(端口: u16) -> Result<String, u32> {
    let 响应体 = 请求调试口(端口, "PUT", "/json/new?about:blank")?;
    let 值: Value = serde_json::from_str(&响应体).map_err(|_| 错误码::协议不符)?;
    let 地址 = 值.get("webSocketDebuggerUrl").and_then(|项| 项.as_str()).ok_or(错误码::协议不符)?;
    // ws://127.0.0.1:PORT/devtools/page/XXX → 取路径部分
    let 路径 = 地址.splitn(4, '/').nth(3).ok_or(错误码::协议不符)?;
    Ok(format!("/{}", 路径))
}

/// 造一个新会话，返回句柄
pub(crate) fn 创建会话(临时根: &str) -> Result<u32, u32> {
    let mut 表锁 = 表().lock().map_err(|_| 错误码::处理失败)?;
    if 表锁.len() >= 会话上限 {
        return Err(错误码::资源超限);
    }
    let 目录 = format!("{}/v1-browser-{}", 临时根, 时间戳());
    std::fs::create_dir_all(&目录).map_err(|_| 错误码::启动失败)?;
    let (进程, 端口) = 起浏览器(&目录)?;
    let 标签路径 = match 开标签(端口) {
        Ok(路径) => 路径,
        Err(码) => {
            let mut 进程 = 进程;
            let _ = 进程.kill();
            return Err(码);
        }
    };
    let 连接 = match 调试连接::建连(端口, &标签路径) {
        Ok(连接) => 连接,
        Err(码) => {
            let mut 进程 = 进程;
            let _ = 进程.kill();
            return Err(码);
        }
    };
    let 句柄 = 下一个句柄(&表锁);
    表锁.insert(句柄, 会话 { 进程, 标签连接: 连接, 指令序: 0, 临时目录: 目录 });
    Ok(句柄)
}

fn 下一个句柄(表: &HashMap<u32, 会话>) -> u32 {
    let mut 候选 = 1u32;
    while 表.contains_key(&候选) {
        候选 += 1;
    }
    候选
}

fn 时间戳() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|时长| 时长.as_millis())
        .unwrap_or(0)
}

/// 在指定会话上执行一条 CDP 指令，等它自己的回执（id 对得上才算）
pub(crate) fn 发指令(句柄: u32, 方法: &str, 参数: Value) -> Result<Value, u32> {
    let mut 表锁 = 表().lock().map_err(|_| 错误码::处理失败)?;
    let 项 = 表锁.get_mut(&句柄).ok_or(错误码::会话不存在)?;
    项.指令序 += 1;
    let 本次序 = 项.指令序;
    let 报文 = json!({"id": 本次序, "method": 方法, "params": 参数}).to_string();
    项.标签连接.发文本(&报文)?;
    let 截止 = std::time::Instant::now() + std::time::Duration::from_secs(30);
    while std::time::Instant::now() < 截止 {
        let 回 = 项.标签连接.收文本()?;
        let 值: Value = serde_json::from_str(&回).map_err(|_| 错误码::协议不符)?;
        if 值.get("id").and_then(|序| 序.as_u64()) == Some(本次序) {
            if let Some(_错) = 值.get("error") {
                return Err(错误码::指令失败);
            }
            return Ok(值.get("result").cloned().unwrap_or(Value::Null));
        }
    }
    Err(错误码::处理超时)
}

/// 关会话：杀 Chrome、清临时目录
pub(crate) fn 关闭会话(句柄: u32) -> Result<bool, u32> {
    let mut 表锁 = 表().lock().map_err(|_| 错误码::处理失败)?;
    let mut 项 = 表锁.remove(&句柄).ok_or(错误码::会话不存在)?;
    let _ = 项.进程.kill();
    let _ = 项.进程.wait();
    let _ = std::fs::remove_dir_all(&项.临时目录);
    Ok(true)
}

/// 进程退出前把还会话全收掉（避免留孤儿 Chrome）
pub(crate) fn 全部关闭() {
    if let Ok(mut 表锁) = 表().lock() {
        for (_, mut 项) in 表锁.drain() {
            let _ = 项.进程.kill();
            let _ = 项.进程.wait();
            let _ = std::fs::remove_dir_all(&项.临时目录);
        }
    }
}
