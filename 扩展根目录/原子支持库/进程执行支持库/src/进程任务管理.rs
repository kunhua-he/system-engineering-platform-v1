use crate::编号与码面::错误码;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::hash::{BuildHasher, RandomState};
use std::io::{ErrorKind, Read};
use std::os::fd::AsRawFd;
use std::os::unix::process::CommandExt;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

/// 单路输出上限：超出按截断标记，不再继续读。
const 单路输出上限: usize = 1048576;
/// 同时可挂在表里的任务上限。**按本机 CPU 核数算，不写死、不封顶**。
///
/// 为什么：每个进程任务主要吃一个核，36 核的机器压 16 个是浪费；
/// 每核留 4 个并发额度（含 IO 等待型的任务，它占着表项但不吃满核）。
/// 只保下限 16 兜住小机器，上限交给核数决定 —— 封顶等于又变回写死。
fn 算任务表上限() -> usize {
    let 核数 = std::thread::available_parallelism()
        .map(|并行数量| 并行数量.get())
        .unwrap_or(4);
    (核数 * 4).max(16)
}

/// 完成后结果可读窗口。
const 结果保留时长: Duration = Duration::from_secs(10);
/// 单命令预算上限（秒）。
const 预算上限: f64 = 600.0;
/// 轮询子进程退出的间隔。
const 轮询间隔: Duration = Duration::from_millis(10);

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
        if !工作目录.starts_with('/')
            || 工作目录.len() > 4096
            || !std::path::Path::new(&工作目录).is_dir()
        {
            return Err(错误码::参数不合法);
        }
        let 超时秒数 = 参数值
            .get("超时秒数")
            .and_then(Value::as_f64)
            .unwrap_or(30.0);
        if !(0.2..=预算上限).contains(&超时秒数) {
            return Err(错误码::参数不合法);
        }
        let 走沙箱 = 参数值
            .get("沙箱")
            .and_then(Value::as_str)
            .is_none_or(|模式值| 模式值 != "直跑");
        Ok(Self {
            命令,
            工作目录,
            预算: Duration::from_secs_f64(超时秒数),
            走沙箱,
        })
    }
}

struct 执行条目 {
    创建时刻: Instant,
    预算: Duration,
    完成时刻: Option<Instant>,
    执行结果: Option<Result<Value, u32>>,
    取消标志: Arc<AtomicBool>,
    丢弃结果: bool,
    超时触发: Arc<AtomicBool>,
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
        命令构建
            .arg("-p")
            .arg(沙箱配置(&参数.工作目录))
            .arg("/bin/sh")
            .arg("-c")
            .arg(&参数.命令);
        return Ok(命令构建);
    }
    let mut 命令构建 = Command::new("/bin/sh");
    命令构建.arg("-c").arg(&参数.命令);
    Ok(命令构建)
}

unsafe extern "C" {
    fn kill(进程号: i32, 信号值: i32) -> i32;
    fn fcntl(文件描述符: i32, 操作码: i32, ...) -> i32;
}

const 终止信号: i32 = 15;
const 强制终止信号: i32 = 9;
#[cfg(target_os = "macos")]
const 非阻塞标志: i32 = 4;
#[cfg(not(target_os = "macos"))]
const 非阻塞标志: i32 = 2048;

#[derive(Default)]
struct 管道读取结果 {
    输出字节: Vec<u8>,
    已截断: bool,
}

fn 设置非阻塞(管道: &impl AsRawFd) -> Result<(), u32> {
    let 文件描述符 = 管道.as_raw_fd();
    let 当前状态 = unsafe { fcntl(文件描述符, 3, 0) };
    if 当前状态 < 0 || unsafe { fcntl(文件描述符, 4, 当前状态 | 非阻塞标志) } < 0
    {
        return Err(错误码::命令执行失败);
    }
    Ok(())
}

fn 读取可用输出(
    管道: &mut impl Read, 输出结果: &mut 管道读取结果
) -> Result<(), u32> {
    let mut 分块 = [0u8; 8192];
    for _ in 0..16 {
        match 管道.read(&mut 分块) {
            Ok(0) => break,
            Ok(读到) => {
                let 剩余额度 = 单路输出上限.saturating_sub(输出结果.输出字节.len());
                输出结果
                    .输出字节
                    .extend_from_slice(&分块[..读到.min(剩余额度)]);
                输出结果.已截断 |= 读到 > 剩余额度;
            }
            Err(错误值) if 错误值.kind() == ErrorKind::WouldBlock => break,
            Err(错误值) if 错误值.kind() == ErrorKind::Interrupted => continue,
            Err(_) => return Err(错误码::命令执行失败),
        }
    }
    Ok(())
}

fn 发送组信号(进程组号: u32, 信号值: i32) {
    if 进程组号 != 0 {
        let _ = unsafe { kill(-(进程组号 as i32), 信号值) };
    }
}

struct 进程收尾守卫 {
    子进程: std::process::Child,
    进程组号: u32,
    已回收: bool,
}

impl 进程收尾守卫 {
    fn 创建(子进程: std::process::Child) -> Self {
        let 进程组号 = 子进程.id();
        Self {
            子进程,
            进程组号,
            已回收: false,
        }
    }

    fn 终止并等待(&mut self) -> Result<std::process::ExitStatus, u32> {
        发送组信号(self.进程组号, 终止信号);
        std::thread::sleep(Duration::from_millis(20));
        发送组信号(self.进程组号, 强制终止信号);
        let 退出状态 = self.子进程.wait().map_err(|_| 错误码::命令执行失败)?;
        // wait 回收直接子进程；组仍存活时保留工作线程与任务额度。
        loop {
            if unsafe { kill(-(self.进程组号 as i32), 0) } != 0
                && std::io::Error::last_os_error().raw_os_error() == Some(3)
            {
                break;
            }
            发送组信号(self.进程组号, 强制终止信号);
            std::thread::sleep(Duration::from_millis(10));
        }
        self.已回收 = true;
        Ok(退出状态)
    }
}

impl Drop for 进程收尾守卫 {
    fn drop(&mut self) {
        if !self.已回收 {
            let _ = self.终止并等待();
        }
    }
}

fn 执行命令(
    参数: &执行参数,
    取消标志: &AtomicBool,
    超时标志: &AtomicBool,
) -> Result<Value, u32> {
    let mut 命令构建 = 建命令(参数)?;
    命令构建
        .current_dir(&参数.工作目录)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .process_group(0);
    let 子进程 = 命令构建.spawn().map_err(|_| 错误码::命令执行失败)?;
    let mut 收尾守卫 = 进程收尾守卫::创建(子进程);
    let mut 标准管道 = 收尾守卫.子进程.stdout.take().ok_or(错误码::命令执行失败)?;
    let mut 错误管道 = 收尾守卫.子进程.stderr.take().ok_or(错误码::命令执行失败)?;
    设置非阻塞(&标准管道)?;
    设置非阻塞(&错误管道)?;
    let mut 标准输出 = 管道读取结果::default();
    let mut 错误输出 = 管道读取结果::default();
    let 起始时刻 = Instant::now();
    let mut 取消已确认 = false;
    loop {
        读取可用输出(&mut 标准管道, &mut 标准输出)?;
        读取可用输出(&mut 错误管道, &mut 错误输出)?;
        if 收尾守卫
            .子进程
            .try_wait()
            .map_err(|_| 错误码::命令执行失败)?
            .is_some()
        {
            break;
        }
        if 取消标志.load(Ordering::Acquire) {
            取消已确认 = true;
            break;
        }
        if 起始时刻.elapsed() >= 参数.预算 {
            超时标志.store(true, Ordering::Release);
            取消标志.store(true, Ordering::Release);
            取消已确认 = true;
            break;
        }
        std::thread::sleep(轮询间隔);
    }
    let 退出状态 = 收尾守卫.终止并等待()?;
    // 进程组确认退出后仅排空可读字节，不等待继承管道的 EOF。
    读取可用输出(&mut 标准管道, &mut 标准输出)?;
    读取可用输出(&mut 错误管道, &mut 错误输出)?;
    Ok(json!({
        "状态": if 超时标志.load(Ordering::Acquire) { "超时" } else if 取消已确认 { "已取消" } else { "已完成" },
        "退出码": 退出状态.code(),
        "标准输出": String::from_utf8_lossy(&标准输出.输出字节).to_string(),
        "错误输出": String::from_utf8_lossy(&错误输出.输出字节).to_string(),
        "标准输出已截断": 标准输出.已截断,
        "错误输出已截断": 错误输出.已截断,
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
                条目.超时触发.store(true, Ordering::Release);
                条目.取消标志.store(true, Ordering::Release);
            }
        }
        self.条目表.retain(|_, 条目| {
            let 线程已退 = 条目.工作线程.as_ref().is_some_and(JoinHandle::is_finished);
            let 结果已过期 = 条目
                .完成时刻
                .is_some_and(|完成时刻| 完成时刻.elapsed() >= 结果保留时长);
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
    if 总表.条目表.len() >= 算任务表上限() {
        return Err(错误码::资源受限);
    }
    let 任务句柄 = loop {
        let 候选号 = RandomState::new().hash_one((Instant::now(), std::process::id()));
        if 候选号 != 0 && !总表.条目表.contains_key(&候选号) {
            break 候选号;
        }
    };
    let 取消标志 = Arc::new(AtomicBool::new(false));
    let 超时标志 = Arc::new(AtomicBool::new(false));
    总表.条目表.insert(
        任务句柄,
        执行条目 {
            创建时刻: Instant::now(),
            预算: 参数.预算,
            完成时刻: None,
            执行结果: None,
            取消标志: 取消标志.clone(),
            丢弃结果: false,
            超时触发: 超时标志.clone(),
            工作线程: None,
        },
    );
    let 启动结果 = std::thread::Builder::new()
        .name("进程执行".into())
        .spawn(move || {
            let 执行结果 = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                执行命令(&参数, &取消标志, &超时标志)
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
            总表
                .条目表
                .get_mut(&任务句柄)
                .ok_or(错误码::任务无效)?
                .工作线程 = Some(工作线程);
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
    if !资源在途 && let Some(执行结果) = &条目.执行结果 {
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
        "状态": if 条目.超时触发.load(Ordering::Acquire) { "超时处理中" } else if 条目.取消标志.load(Ordering::Acquire) { "取消中" } else { "运行中" },
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

pub(crate) unsafe extern "C" fn 生命周期通知(
    通知编号: v1_contract::通知号,
    _: usize,
    _: usize,
) -> isize {
    let Ok(mut 总表) = 任务表锁() else {
        return v1_contract::通知返回::延迟释放;
    };
    match 通知编号.取号值() {
        2000 => {
            总表.停止接收 = false;
            0
        }
        2001..=2003 => {
            总表.停止接收 = true;
            for 条目 in 总表.条目表.values_mut() {
                条目.取消标志.store(true, Ordering::Release);
                条目.丢弃结果 = true;
            }
            总表.清到期();
            if 总表.条目表.is_empty() {
                0
            } else {
                v1_contract::通知返回::延迟释放
            }
        }
        _ => 0,
    }
}

#[cfg(test)]
mod 进程任务测试 {
    use super::*;

    fn 测试缓存根() -> std::path::PathBuf {
        let 缓存根 = std::path::PathBuf::from(std::env::var("HOME").expect("夹具用户目录"))
            .join(".hermes/cache/scratch");
        std::fs::create_dir_all(&缓存根).expect("建立测试缓存根");
        缓存根
    }

    #[test]
    fn 取消会终止继承管道的子孙() {
        let 工作目录 = 测试缓存根().join(format!("进程执行夹具-{}", std::process::id()));
        std::fs::create_dir_all(&工作目录).expect("建立夹具目录");
        let 参数 = 执行参数 {
            命令: "(/bin/sleep 2) & /bin/sleep 2".to_string(),
            工作目录: 工作目录.to_string_lossy().into_owned(),
            预算: Duration::from_secs(5),
            走沙箱: false,
        };
        let 取消标志 = Arc::new(AtomicBool::new(false));
        let 起始时刻 = Instant::now();
        let 线程取消标志 = 取消标志.clone();
        let 执行线程 = std::thread::spawn(move || {
            let 超时标志 = AtomicBool::new(false);
            执行命令(&参数, &线程取消标志, &超时标志)
        });
        std::thread::sleep(Duration::from_millis(100));
        取消标志.store(true, Ordering::Release);
        let 执行结果 = 执行线程
            .join()
            .expect("取消线程应收尾")
            .expect("取消应返回状态");
        assert_eq!(执行结果["状态"], "已取消");
        assert!(起始时刻.elapsed() < Duration::from_secs(1));
        std::fs::remove_dir_all(&工作目录).expect("清理夹具目录");
    }

    #[test]
    fn 超时终止继承管道的子孙() {
        let 工作目录 = 测试缓存根().join(format!("进程执行超时夹具-{}", std::process::id()));
        std::fs::create_dir_all(&工作目录).expect("建立超时夹具目录");
        let 参数 = 执行参数 {
            命令: "(/bin/sleep 2) & /bin/sleep 2".to_string(),
            工作目录: 工作目录.to_string_lossy().into_owned(),
            预算: Duration::from_millis(200),
            走沙箱: false,
        };
        let 取消标志 = AtomicBool::new(false);
        let 超时标志 = AtomicBool::new(false);
        let 执行结果 = 执行命令(&参数, &取消标志, &超时标志).expect("超时应返回状态");
        assert_eq!(执行结果["状态"], "超时");
        std::fs::remove_dir_all(&工作目录).expect("清理超时夹具目录");
    }

    #[test]
    fn 正常退出也清理后台后代() {
        let 参数 = 执行参数 {
            命令: "(/bin/sleep 2) & printf complete".to_string(),
            工作目录: 测试缓存根().to_string_lossy().into_owned(),
            预算: Duration::from_secs(2),
            走沙箱: false,
        };
        let 起始时刻 = Instant::now();
        let 执行结果 =
            执行命令(&参数, &AtomicBool::new(false), &AtomicBool::new(false)).expect("正常执行");
        assert_eq!(执行结果["标准输出"], "complete");
        assert_eq!(执行结果["退出码"], 0);
        assert!(起始时刻.elapsed() < Duration::from_secs(1));
    }

    #[test]
    fn 异常展开会回收所属进程组() {
        let mut 命令构建 = Command::new("/bin/sh");
        命令构建
            .arg("-c")
            .arg("(/bin/sleep 2) & /bin/sleep 2")
            .process_group(0);
        let 子进程 = 命令构建.spawn().expect("建立异常夹具");
        let 进程组号 = 子进程.id();
        let 执行结果 = std::panic::catch_unwind(move || {
            let _收尾守卫 = 进程收尾守卫::创建(子进程);
            panic!("夹具异常展开");
        });
        assert!(执行结果.is_err());
        assert_ne!(unsafe { kill(-(进程组号 as i32), 0) }, 0);
    }

    #[test]
    fn 生命周期等待任务真实退场() {
        let 通知函数 = crate::扩展声明().通知函数.expect("必须登记生命周期通知");
        unsafe {
            通知函数(v1_contract::通知号::构造(2000), 0, 0);
        }
        let 任务句柄 = 提交执行(json!({"命令":"(/bin/sleep 2) & /bin/sleep 2", "工作目录":测试缓存根().to_string_lossy(), "超时秒数":2.0,"沙箱":"直跑"})).expect("提交夹具任务");
        assert!(取消执行(任务句柄).expect("请求取消"));
        let 起始时刻 = Instant::now();
        loop {
            let 执行结果 = 读取执行(任务句柄).expect("读取取消状态");
            if 执行结果["已完成"] == true {
                assert_eq!(执行结果["资源在途"], false);
                assert_eq!(执行结果["状态"], "已取消");
                break;
            }
            assert_eq!(执行结果["资源在途"], true);
            assert_ne!(执行结果["状态"], "已取消");
            assert!(起始时刻.elapsed() < Duration::from_secs(2));
            std::thread::sleep(Duration::from_millis(10));
        }
        let 返回码 = unsafe { 通知函数(v1_contract::通知号::构造(2001), 0, 0) };
        assert_eq!(返回码, 0);
        assert!(提交执行(json!({"命令":"true","工作目录":测试缓存根().to_string_lossy(),"超时秒数":1.0,"沙箱":"直跑"})).is_err());
        unsafe {
            通知函数(v1_contract::通知号::构造(2000), 0, 0);
        }
        let 任务句柄 = 提交执行(json!({"命令":"/bin/sleep 2", "工作目录":测试缓存根().to_string_lossy(), "超时秒数":2.0,"沙箱":"直跑"})).expect("提交卸载夹具");
        let 返回码 = unsafe { 通知函数(v1_contract::通知号::构造(2002), 0, 0) };
        assert_eq!(返回码, v1_contract::通知返回::延迟释放);
        assert!(读取执行(任务句柄).is_err());
        let 起始时刻 = Instant::now();
        loop {
            let 返回码 = unsafe { 通知函数(v1_contract::通知号::构造(2002), 0, 0) };
            if 返回码 == 0 {
                break;
            }
            assert!(起始时刻.elapsed() < Duration::from_secs(2));
            std::thread::sleep(Duration::from_millis(10));
        }
        unsafe {
            通知函数(v1_contract::通知号::构造(2000), 0, 0);
        }
    }
}
