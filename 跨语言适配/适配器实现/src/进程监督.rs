use std::io::{self, Read};
use std::os::fd::OwnedFd;
use std::os::unix::net::UnixStream;
use std::os::unix::process::CommandExt;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::time::{Duration, Instant};

const 输出保留上限: usize = 64 * 1024;
const 回收预算: Duration = Duration::from_millis(500);
const 轮询间隔: Duration = Duration::from_millis(2);

unsafe extern "C" {
    fn kill(进程组号: i32, 信号编号: i32) -> i32;
    #[cfg(all(target_os = "macos", target_pointer_width = "64"))]
    fn waitid(身份种类: i32, 进程标识: u32, 退出记录: *mut 退出观测, 观察选项: i32) -> i32;
}

#[cfg(all(target_os = "macos", target_pointer_width = "64"))]
#[repr(C)]
struct 退出观测 {
    信号编号: i32,
    错误编号: i32,
    消息代码: i32,
    进程编号: i32,
    用户编号: u32,
    退出值: i32,
    故障地址: *mut std::ffi::c_void,
    信号载荷: u64,
    事件带宽: i64,
    保留字段: [u64; 7],
}

fn 观察进程退出(进程标识: u32) -> io::Result<bool> {
    #[cfg(all(target_os = "macos", target_pointer_width = "64"))]
    {
        let mut 退出记录: 退出观测 = unsafe { std::mem::zeroed() };
        let 观察结果 = unsafe { waitid(1, 进程标识, &mut 退出记录, 0x01 | 0x04 | 0x20) };
        if 观察结果 < 0 { return Err(io::Error::last_os_error()); }
        Ok(退出记录.进程编号 != 0)
    }
    #[cfg(not(all(target_os = "macos", target_pointer_width = "64")))]
    {
        let _ = 进程标识;
        Err(io::Error::new(io::ErrorKind::Unsupported, "当前只验收macOS64位退出观测"))
    }
}

fn 进程组已消失(进程组号: i32) -> bool {
    (unsafe { kill(-进程组号, 0) }) < 0 && io::Error::last_os_error().raw_os_error() == Some(3)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 监督故障 {
    预算耗尽,
    输出超量,
    输出读取失败,
    进程状态失败,
    回收未确认,
}

#[derive(Debug)]
pub struct 监督回执 {
    pub 退出状态: Option<ExitStatus>,
    pub 标准输出: Vec<u8>,
    pub 标准错误: Vec<u8>,
    pub 丢弃输出字节: usize,
    pub 丢弃错误字节: usize,
    pub 故障: Option<监督故障>,
    pub 耗时: Duration,
    pub 待回收进程: Option<Child>,
    pub 进程组已回收: bool,
}

struct 输出收集 {
    通信通道: UnixStream,
    保留字节: Vec<u8>,
    丢弃字节: usize,
    通道已结束: bool,
}

impl 输出收集 {
    fn 创建通道() -> io::Result<(Self, Stdio)> {
        let (读取通道, 写入通道) = UnixStream::pair()?;
        读取通道.set_nonblocking(true)?;
        Ok((
            Self { 通信通道: 读取通道, 保留字节: Vec::new(), 丢弃字节: 0, 通道已结束: false },
            Stdio::from(OwnedFd::from(写入通道)),
        ))
    }

    fn 排空当前(&mut self) -> io::Result<()> {
        if self.通道已结束 { return Ok(()); }
        let mut 读取缓冲 = [0u8; 8192];
        for _ in 0..16 {
            match self.通信通道.read(&mut 读取缓冲) {
                Ok(0) => { self.通道已结束 = true; break; }
                Ok(读取长度) => {
                    let 保留长度 = 读取长度.min(输出保留上限 - self.保留字节.len());
                    self.保留字节.extend_from_slice(&读取缓冲[..保留长度]);
                    self.丢弃字节 = self.丢弃字节.saturating_add(读取长度 - 保留长度);
                }
                Err(错误) if 错误.kind() == io::ErrorKind::WouldBlock => break,
                Err(错误) if 错误.kind() == io::ErrorKind::Interrupted => continue,
                Err(错误) => return Err(错误),
            }
        }
        Ok(())
    }
}

pub fn 监督执行(执行命令: &mut Command, 截止时间: Instant) -> io::Result<监督回执> {
    if !cfg!(all(target_os = "macos", target_pointer_width = "64")) {
        return Err(io::Error::new(io::ErrorKind::Unsupported, "当前监督仅验收macOS64位"));
    }
    let 开始时间 = Instant::now();
    if 截止时间 <= 开始时间 || 截止时间.duration_since(开始时间) > Duration::from_secs(5) {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "截止时间须在剩余五秒预算内"));
    }
    let 回收预留 = 回收预算.min(截止时间.duration_since(开始时间) / 2);
    let 执行截止 = 截止时间 - 回收预留;
    let (mut 输出收集器, 输出写口) = 输出收集::创建通道()?;
    let (mut 错误收集器, 错误写口) = 输出收集::创建通道()?;
    执行命令.stdin(Stdio::null()).stdout(输出写口).stderr(错误写口).process_group(0);
    let mut 能力进程 = 执行命令.spawn()?;
    执行命令.stdout(Stdio::null()).stderr(Stdio::null());
    let 进程组号 = i32::try_from(能力进程.id()).map_err(io::Error::other)?;
    let mut 退出状态 = None;
    let mut 故障 = None;
    loop {
        if 输出收集器.排空当前().is_err() || 错误收集器.排空当前().is_err() {
            故障 = Some(监督故障::输出读取失败);
            break;
        }
        if 输出收集器.丢弃字节 > 0 || 错误收集器.丢弃字节 > 0 {
            故障 = Some(监督故障::输出超量);
            break;
        }
        match 观察进程退出(能力进程.id()) {
            Ok(true) => break,
            Ok(false) => {}
            Err(_) => {
                故障 = Some(监督故障::进程状态失败);
                break;
            }
        }
        let 当前时间 = Instant::now();
        if 当前时间 >= 执行截止 {
            故障 = Some(监督故障::预算耗尽);
            break;
        }
        std::thread::sleep(轮询间隔.min(执行截止 - 当前时间));
    }
    let 清理结果 = unsafe { kill(-进程组号, 9) };
    let 清理待确认 = 清理结果 < 0 && io::Error::last_os_error().raw_os_error() != Some(3);
    if 故障.is_some() || 清理待确认 {
        let _ = 能力进程.kill();
    }
    let 回收截止 = (Instant::now() + 回收预留).min(截止时间);
    let mut 进程组已回收 = false;
    while Instant::now() < 回收截止 {
        let _ = 输出收集器.排空当前();
        let _ = 错误收集器.排空当前();
        if 退出状态.is_none() {
            match 能力进程.try_wait() {
                Ok(Some(进程结局)) => 退出状态 = Some(进程结局),
                Ok(None) => {},
                Err(_) => break,
            }
        }
        if 退出状态.is_some() && 输出收集器.通道已结束 && 错误收集器.通道已结束
            && 进程组已消失(进程组号) {
            进程组已回收 = true;
            break;
        }
        std::thread::sleep(轮询间隔.min(回收截止.saturating_duration_since(Instant::now())));
    }
    if !进程组已回收 {
        故障 = Some(监督故障::回收未确认);
    }
    let _ = 输出收集器.排空当前();
    let _ = 错误收集器.排空当前();
    if 故障.is_none() && (输出收集器.丢弃字节 > 0 || 错误收集器.丢弃字节 > 0) {
        故障 = Some(监督故障::输出超量);
    }
    let 待回收进程 = if 退出状态.is_some() { None } else { Some(能力进程) };
    Ok(监督回执 {
        退出状态,
        标准输出: 输出收集器.保留字节,
        标准错误: 错误收集器.保留字节,
        丢弃输出字节: 输出收集器.丢弃字节,
        丢弃错误字节: 错误收集器.丢弃字节,
        故障,
        耗时: 开始时间.elapsed(),
        待回收进程,
        进程组已回收,
    })
}
