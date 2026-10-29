use crate::编号与码面::错误码;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::hash::{BuildHasher, RandomState};
use std::io::Read;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

/// 单路输出上限：超出按截断标记，不再继续读。
const 单路输出上限: usize = 1048576;
/// 同时可挂在表里的任务上限。
const 任务表上限: usize = 16;
/// 完成后结果可读窗口。
const 结果保留时长: Duration = Duration::from_secs(10);
/// 单命令预算上限（秒）。
const 预算上限: f64 = 600.0;
/// 轮询子进程退出的间隔。
const 轮询间隔: Duration = Duration::from_millis(50);

struct 执行参数 {
    命令: String,
    工作目录: String,
    预算: Duration,
    走沙箱: bool,
}

impl 执行参数 {
    fn 解析(参数值: &Value) -> Result<Self, u32> {
        let 取文本 = |键名: &str| -> Result<String, u32> {
            参数值
                .get(键名)
                .and_then(Value::as_str)
                .map(str::to_string)
                .ok_or(错误码::参数不合法)
        };
        let 命令 = 取文本("命令")?;
        if 命令.trim().is_empty() || 命令.len() > 8192 || 命令.contains('\0') {
            return Err(错误码::参数不合法);
        }
        let 工作目录 = 取文本("工作目录")?;
        if !工作目录.starts_with('/') || 工作目录.len() > 4096 || !std::path::Path::new(&工作目录).is_dir() {
            return Err(错误码::参数不合法);
        }
        let 超时秒数 = 参数值.get("超时秒数").and_then(Value::as_f64).unwrap_or(30.0);
        if !(0.2..=预算上限).contains(&超时秒数) {
            return Err(错误码::参数不合法);
        }
        let 走沙箱 = 参数值.get("沙箱").and_then(Value::as_str).is_none_or(|模式值| 模式值 != "直跑");
        Ok(Self { 命令, 工作目录, 预算: Duration::from_secs_f64(超时秒数), 走沙箱 })
    }
}

struct 执行条目 {
    创建时刻: Instant,
    预算: Duration,
    完成时刻: Option<Instant>,
    执行结果: Option<Result<Value, u32>>,
    取消标志: Arc<AtomicBool>,
    丢弃结果: bool,
    超时触发: bool,
    工作线程: Option<JoinHandle<()>>,
}

#[derive(Default)]
struct 执行总表 {
    条目表: HashMap<u64, 执行条目>,
    停止接收: bool,
}

static 执行存储: OnceLock<Mutex<执行总表>> = OnceLock::new();

fn 任务表锁() -> Result<std::sync::MutexGuard<'static, 执行总表>, u32> {
    执行存储
        .get_or_init(Default::default)
        .lock()
        .map_err(|_| 错误码::资源受限)
}

fn 沙箱配置(工作目录: &str) -> String {
    let 转义目录 = 工作目录.replace('\\', "\\\\").replace('"', "\\\"");
    format!(
        "(version 1)(deny default)(allow process*)(allow signal)(allow sysctl-read)(allow mach-lookup)(allow file-read*)(allow file-write* (subpath \"{转义目录}\") (subpath \"/private/tmp\") (subpath \"/private/var/folders\") (literal \"/dev/null\"))"
    )
}

fn 建命令(参数: &执行参数) -> Result<Command, u32> {
    if 参数.走沙箱 {
        if !std::path::Path::new("/usr/bin/sandbox-exec").exists() {
            return Err(错误码::沙箱不可用);
        }
        let mut 命令构建 = Command::new("/usr/bin/sandbox-exec");
        命令构建.arg("-p").arg(沙箱配置(&参数.工作目录)).arg("/bin/sh").arg("-c").arg(&参数.命令);
        return Ok(命令构建);
    }
    let mut 命令构建 = Command::new("/bin/sh");
    命令构建.arg("-c").arg(&参数.命令);
    Ok(命令构建)
}

fn 读管道(管道: impl Read + Send + 'static) -> JoinHandle<(Vec<u8>, bool)> {
    std::thread::spawn(move || {
        let mut 缓冲 = Vec::new();
        let mut 分块 = [0u8; 8192];
        let mut 已截断 = false;
        let mut 输出源 = 管道;
        loop {
            match 输出源.read(&mut 分块) {
                Ok(0) => break,
                Ok(读到) => {
                    let 剩余额度 = 单路输出上限.saturating_sub(缓冲.len());
                    if 读到 > 剩余额度 {
                        if 剩余额度 > 0 {
                            缓冲.extend_from_slice(&分块[..剩余额度]);
                        }
                        已截断 = true;
                        break;
                    }
                    缓冲.extend_from_slice(&分块[..读到]);
                }
                Err(_) => break,
            }
        }
        (缓冲, 已截断)
    })
}

fn 执行命令(参数: &执行参数, 取消标志: &AtomicBool, 超时触发: &mut bool) -> Result<Value, u32> {
    let mut 命令构建 = 建命令(参数)?;
    命令构建
        .current_dir(&参数.工作目录)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut 子进程 = 命令构建.spawn().map_err(|_| 错误码::命令执行失败)?;
    let 标准输出线程 = 子进程.stdout.take().map(读管道);
    let 错误输出线程 = 子进程.stderr.take().map(读管道);
    let 起始时刻 = Instant::now();
    let 退出状态 = loop {
        match 子进程.try_wait() {
            Ok(Some(退出码)) => break Some(退出码),
            Ok(None) => {}
            Err(_) => return Err(错误码::命令执行失败),
        }
        if 取消标志.load(Ordering::Acquire) {
            let _ = 子进程.kill();
            *超时触发 = 起始时刻.elapsed() >= 参数.预算;
            break None;
        }
        if 起始时刻.elapsed() >= 参数.预算 {
            *超时触发 = true;
            取消标志.store(true, Ordering::Release);
            let _ = 子进程.kill();
            break None;
        }
        std::thread::sleep(轮询间隔);
    };
    let 标准输出 = 标准输出线程.and_then(|线程句柄| 线程句柄.join().ok()).unwrap_or_default();
    let 错误输出 = 错误输出线程.and_then(|线程句柄| 线程句柄.join().ok()).unwrap_or_default();
    let 退出码 = 退出状态.as_ref().and_then(std::process::ExitStatus::code);
    if 退出状态.is_none() && !*超时触发 {
        return Err(错误码::命令执行失败);
    }
    Ok(json!({
        "状态": if *超时触发 { "超时" } else if 退出状态.is_none() { "已取消" } else { "已完成" },
        "退出码": 退出码,
        "标准输出": String::from_utf8_lossy(&标准输出.0).to_string(),
        "错误输出": String::from_utf8_lossy(&错误输出.0).to_string(),
        "标准输出已截断": 标准输出.1,
        "错误输出已截断": 错误输出.1,
        "耗时毫秒": 起始时刻.elapsed().as_millis() as u64,
    }))
}

impl 执行总表 {
    fn 清到期(&mut self) {
        for 条目 in self.条目表.values_mut() {
            if 条目.执行结果.is_none()
                && 条目.创建时刻.elapsed() > 条目.预算
                && !条目.取消标志.load(Ordering::Acquire)
            {
                条目.超时触发 = true;
                条目.取消标志.store(true, Ordering::Release);
            }
        }
        self.条目表.retain(|_, 条目| {
            let 线程已退 = 条目.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
            let 结果已过期 = 条目.完成时刻.is_some_and(|完成时刻| 完成时刻.elapsed() >= 结果保留时长);
            if 线程已退 && (条目.丢弃结果 || 结果已过期) {
                if let Some(工作线程) = 条目.工作线程.take() {
                    let _ = 工作线程.join();
                }
                false
            } else {
                true
            }
        });
    }
}

pub(crate) fn 提交执行(参数值: Value) -> Result<u64, u32> {
    let 参数 = 执行参数::解析(&参数值)?;
    let mut 总表 = 任务表锁()?;
    if 总表.停止接收 {
        return Err(错误码::资源受限);
    }
    总表.清到期();
    if 总表.条目表.len() >= 任务表上限 {
        return Err(错误码::资源受限);
    }
    let 任务句柄 = loop {
        let 候选号 = RandomState::new().hash_one((Instant::now(), std::process::id()));
        if 候选号 != 0 && !总表.条目表.contains_key(&候选号) {
            break 候选号;
        }
    };
    let 取消标志 = Arc::new(AtomicBool::new(false));
    总表.条目表.insert(
        任务句柄,
        执行条目 {
            创建时刻: Instant::now(),
            预算: 参数.预算,
            完成时刻: None,
            执行结果: None,
            取消标志: 取消标志.clone(),
            丢弃结果: false,
            超时触发: false,
            工作线程: None,
        },
    );
    let 启动结果 = std::thread::Builder::new().name("进程执行".into()).spawn(move || {
        let mut 超时触发 = false;
        let 执行结果 = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            执行命令(&参数, &取消标志, &mut 超时触发)
        }))
        .unwrap_or(Err(错误码::命令执行失败));
        if let Ok(mut 总表) = 任务表锁()
            && let Some(条目) = 总表.条目表.get_mut(&任务句柄)
        {
            条目.执行结果 = Some(执行结果);
            条目.完成时刻 = Some(Instant::now());
        }
    });
    match 启动结果 {
        Ok(工作线程) => {
            总表.条目表.get_mut(&任务句柄).ok_or(错误码::任务无效)?.工作线程 = Some(工作线程);
            Ok(任务句柄)
        }
        Err(_) => {
            总表.条目表.remove(&任务句柄);
            Err(错误码::资源受限)
        }
    }
}

pub(crate) fn 读取执行(任务句柄: u64) -> Result<Value, u32> {
    let mut 总表 = 任务表锁()?;
    总表.清到期();
    let 条目 = 总表.条目表.get(&任务句柄).ok_or(错误码::任务无效)?;
    if 条目.丢弃结果 {
        return Err(错误码::任务无效);
    }
    let 资源在途 = !条目.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
    if let Some(执行结果) = &条目.执行结果 {
        let mut 完成结果 = match 执行结果 {
            Ok(完成值) => 完成值.clone(),
            Err(失败码) => json!({
                "状态": "失败",
                "错误码": 失败码,
                "错误信息": match *失败码 {
                    错误码::任务无效 => "任务句柄无效",
                    错误码::资源受限 => "在途任务过多或输出超限",
                    错误码::沙箱不可用 => "本机没有可用的沙箱执行器",
                    错误码::参数不合法 => "执行参数不符合契约",
                    _ => "进程执行失败",
                },
            }),
        };
        完成结果["已完成"] = json!(!资源在途);
        完成结果["资源在途"] = json!(资源在途);
        return Ok(完成结果);
    }
    Ok(json!({
        "已完成": false,
        "资源在途": true,
        "状态": if 条目.超时触发 { "超时" } else { "运行中" },
        "取消已请求": 条目.取消标志.load(Ordering::Acquire),
    }))
}

pub(crate) fn 取消执行(任务句柄: u64) -> Result<bool, u32> {
    let mut 总表 = 任务表锁()?;
    总表.清到期();
    let 条目 = 总表.条目表.get_mut(&任务句柄).ok_or(错误码::任务无效)?;
    条目.取消标志.store(true, Ordering::Release);
    Ok(true)
}

pub(crate) fn 释放执行(任务句柄: u64) -> Result<bool, u32> {
    let mut 总表 = 任务表锁()?;
    let 条目 = 总表.条目表.get_mut(&任务句柄).ok_or(错误码::任务无效)?;
    条目.取消标志.store(true, Ordering::Release);
    条目.丢弃结果 = true;
    总表.清到期();
    Ok(true)
}
