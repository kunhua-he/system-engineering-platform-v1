use std::collections::VecDeque;
use std::io::{self, Read, Write};
use std::os::unix::net::UnixStream;
use std::num::NonZeroU64;
use std::time::{Duration, Instant};

const 帧头字节数: usize = 24;
/// 单帧载荷上限。**公开**：`线协议.rs` 的编码侧与 `进程池` 的发送侧用的是**同一个上界**
/// —— 两处各写一个数就是第二套口径（与 [`调用载荷上限`] 同一条理由）。
pub const 单帧载荷上限: usize = 1024 * 1024;
/// 单次调用的载荷上限（发送与接收两侧各自累计，先校界限再分配的上界之一）。
///
/// **公开**：`线协议.rs` 的数据区累计字节判据（冻结件 §二 第 ④ 条）与帧层用的是
/// **同一个上界** —— 两处各写一个数就是第二套口径。
pub const 调用载荷上限: usize = 4 * 1024 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u16)]
pub enum 消息类别 {
    调用 = 1,
    调用结果 = 2,
    通知 = 3,
    通知回执 = 4,
    就绪 = 5,
    停止 = 6,
    停止回执 = 7,
    /// **留痕记录**（工作进程 → 宿主，只读旁路）：工作进程内层调用记下的留痕，经**同一条 IPC**
    /// 回传宿主，由宿主追加进本实例那份留痕缓冲。
    ///
    /// **只增不复用**：8 在既有类别里未占用；`调用` / `调用结果` 的载荷形状一字未动。
    /// 归属靠**通道（= 一个执行域）+ 帧请求标识（= 该次调用）**钉住，不往留痕九键里加字段
    /// （`留痕` 是冻结形状）。
    留痕记录 = 8,
}

#[derive(Debug, PartialEq, Eq)]
pub struct 消息帧 {
    pub 消息类型: 消息类别,
    pub 请求标识: NonZeroU64,
    pub 载荷: Vec<u8>,
}

pub struct 调用帧预算 {
    截止时间: Instant,
    发送剩余: usize,
    接收剩余: usize,
}

impl 调用帧预算 {
    pub fn 创建(截止时间: Instant) -> io::Result<Self> {
        let 当前时间 = Instant::now();
        if 截止时间 <= 当前时间 || 截止时间.duration_since(当前时间) > Duration::from_secs(5) {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "调用截止须在剩余五秒内"));
        }
        Ok(Self { 截止时间, 发送剩余: 调用载荷上限, 接收剩余: 调用载荷上限 })
    }

    pub(crate) fn 检查剩余(&self) -> io::Result<()> {
        self.剩余时限().map(|_| ())
    }

    fn 剩余时限(&self) -> io::Result<Duration> {
        self.截止时间.checked_duration_since(Instant::now())
            .filter(|时长| !时长.is_zero())
            .ok_or_else(|| io::Error::new(io::ErrorKind::TimedOut, "调用预算耗尽"))
    }
}

#[repr(C)]
struct 轮询描述 {
    描述符: std::ffi::c_int,
    关注事件: std::ffi::c_short,
    就绪事件: std::ffi::c_short,
}
#[cfg(any(target_vendor = "apple", target_os = "freebsd", target_os = "openbsd", target_os = "netbsd", target_os = "dragonfly"))]
type 轮询项数 = u32;
#[cfg(not(any(target_vendor = "apple", target_os = "freebsd", target_os = "openbsd", target_os = "netbsd", target_os = "dragonfly")))]
type 轮询项数 = usize;
unsafe extern "C" {
    fn poll(描述表: *mut 轮询描述, 描述项数: 轮询项数, 超时毫秒: std::ffi::c_int) -> std::ffi::c_int;
}

fn 继续等待(通信通道: &UnixStream, 关注事件: i16, 预算: &调用帧预算) -> io::Result<()> {
    use std::os::fd::AsRawFd;
    let mut 描述表 = 轮询描述 { 描述符: 通信通道.as_raw_fd(), 关注事件, 就绪事件: 0 };
    loop {
        let 超时毫秒 = 预算.剩余时限()?.as_nanos().div_ceil(1_000_000).min(i32::MAX as u128) as i32;
        // SAFETY: 单项C布局与目标平台pollfd一致，借用的通道在调用期间保持有效。
        let 就绪数 = unsafe { poll(&mut 描述表, 1, 超时毫秒) };
        if 就绪数 > 0 {
            if 描述表.就绪事件 & 0x20 != 0 { return Err(io::Error::new(io::ErrorKind::InvalidInput, "IPC描述符已失效")); }
            return Ok(());
        }
        if 就绪数 < 0 {
            let 错误 = io::Error::last_os_error();
            if 错误.kind() != io::ErrorKind::Interrupted { return Err(错误); }
        }
        预算.剩余时限()?;
    }
}

fn 写全帧(通信通道: &mut UnixStream, mut 待写字节: &[u8], 预算: &调用帧预算) -> io::Result<()> {
    while !待写字节.is_empty() {
        预算.剩余时限()?;
        match 通信通道.write(待写字节) {
            Ok(0) => return Err(io::Error::new(io::ErrorKind::WriteZero, "通道不再接收帧")),
            Ok(写入长度) => 待写字节 = &待写字节[写入长度..],
            Err(错误) if 错误.kind() == io::ErrorKind::WouldBlock => 继续等待(通信通道, 4, 预算)?,
            Err(错误) if 错误.kind() == io::ErrorKind::Interrupted => continue,
            Err(错误) => return Err(错误),
        }
    }
    Ok(())
}

fn 读全帧(通信通道: &mut UnixStream, 待填字节: &mut [u8], 预算: &调用帧预算) -> io::Result<()> {
    let mut 已读长度 = 0;
    while 已读长度 < 待填字节.len() {
        预算.剩余时限()?;
        match 通信通道.read(&mut 待填字节[已读长度..]) {
            Ok(0) => return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "通道断开或帧截断")),
            Ok(读取长度) => 已读长度 += 读取长度,
            Err(错误) if 错误.kind() == io::ErrorKind::WouldBlock => 继续等待(通信通道, 1, 预算)?,
            Err(错误) if 错误.kind() == io::ErrorKind::Interrupted => continue,
            Err(错误) => return Err(错误),
        }
    }
    Ok(())
}

pub fn 发送帧(通信通道: &mut UnixStream, 消息体: &消息帧, 预算: &mut 调用帧预算) -> io::Result<()> {
    if 消息体.载荷.len() > 单帧载荷上限 || 消息体.载荷.len() > 预算.发送剩余 {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "请求标识或发送载荷越界"));
    }
    let 剩余毫秒 = u32::try_from(预算.剩余时限()?.as_millis())
        .map_err(io::Error::other)?;
    if 剩余毫秒 == 0 {
        return Err(io::Error::new(io::ErrorKind::TimedOut, "不足一毫秒预算"));
    }
    let mut 帧头 = [0u8; 帧头字节数];
    帧头[..4].copy_from_slice(b"V1IP");
    帧头[4..6].copy_from_slice(&1u16.to_le_bytes());
    帧头[6..8].copy_from_slice(&(消息体.消息类型 as u16).to_le_bytes());
    帧头[8..16].copy_from_slice(&消息体.请求标识.get().to_le_bytes());
    帧头[16..20].copy_from_slice(&(消息体.载荷.len() as u32).to_le_bytes());
    帧头[20..24].copy_from_slice(&剩余毫秒.to_le_bytes());
    通信通道.set_nonblocking(true)?;
    预算.发送剩余 -= 消息体.载荷.len();
    写全帧(通信通道, &帧头, 预算)?;
    写全帧(通信通道, &消息体.载荷, 预算)
}

/// 收一帧，**不校请求标识**：把帧头与载荷读全、校完魔数 / 版本 / 类别 / 长度 / 预算，
/// 原样交出帧里的那个请求标识。
///
/// 收调用侧（工作进程）收到的帧是**对方发起的**，它事先不知道请求标识 —— 只能
/// 「收一帧、按帧里写的标识答回去」。本函数就是那一口的**唯一实现**；
/// [`接收帧`] 只是它加一道标识比对（宿主侧「只收同标识的回帧」靠它）。
pub fn 接收任意帧(通信通道: &mut UnixStream, 预算: &mut 调用帧预算) -> io::Result<消息帧> {
    接收续帧(通信通道, 预算, None)
}

pub(crate) fn 接收续帧(
    通信通道: &mut UnixStream, 预算: &mut 调用帧预算, 首字节: Option<u8>,
) -> io::Result<消息帧> {
    通信通道.set_nonblocking(true)?;
    let mut 帧头 = [0u8; 帧头字节数];
    if let Some(首字节) = 首字节 {
        帧头[0] = 首字节;
        读全帧(通信通道, &mut 帧头[1..], 预算)?;
    } else {
        读全帧(通信通道, &mut 帧头, 预算)?;
    }
    if &帧头[..4] != b"V1IP" || u16::from_le_bytes([帧头[4], 帧头[5]]) != 1 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "IPC魔数或版本不符"));
    }
    let 消息类型 = match u16::from_le_bytes([帧头[6], 帧头[7]]) {
        1 => 消息类别::调用,
        2 => 消息类别::调用结果,
        3 => 消息类别::通知,
        4 => 消息类别::通知回执,
        5 => 消息类别::就绪,
        6 => 消息类别::停止,
        7 => 消息类别::停止回执,
        8 => 消息类别::留痕记录,
        _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "未知IPC消息类别")),
    };
    let 帧请求标识 = NonZeroU64::new(u64::from_le_bytes(帧头[8..16].try_into().unwrap()))
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "IPC请求标识为零"))?;
    let 载荷长度 = u32::from_le_bytes(帧头[16..20].try_into().unwrap()) as usize;
    let 剩余毫秒 = u32::from_le_bytes(帧头[20..24].try_into().unwrap());
    if 载荷长度 > 单帧载荷上限 || 载荷长度 > 预算.接收剩余 || 剩余毫秒 == 0 || 剩余毫秒 > 5000 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "IPC长度或预算不符"));
    }
    let 远端截止 = Instant::now() + Duration::from_millis(u64::from(剩余毫秒));
    预算.截止时间 = 预算.截止时间.min(远端截止);
    预算.接收剩余 -= 载荷长度;
    let mut 载荷 = vec![0u8; 载荷长度];
    读全帧(通信通道, &mut 载荷, 预算)?;
    Ok(消息帧 { 消息类型, 请求标识: 帧请求标识, 载荷 })
}

/// 收一帧并校请求标识（宿主侧用法）。
pub fn 接收帧(通信通道: &mut UnixStream, 请求标识: NonZeroU64, 预算: &mut 调用帧预算) -> io::Result<消息帧> {
    let 帧体 = 接收任意帧(通信通道, 预算)?;
    if 帧体.请求标识 != 请求标识 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "IPC请求、长度或预算不符"));
    }
    Ok(帧体)
}

/// 一条留痕记录过线时的定宽字节数（`实例号 u64` + `能力号 u32` + `入参指纹 u64` + `结果码 i32`
/// + `耗时微秒 u64` + `追踪号 u64` + `调用类 u8` + `资源号 u32` + `操作号 u32`）。
pub const 留痕记录字节数: usize = 49;

/// 把一条留痕压成 `留痕记录` 帧的载荷（**唯一编码口**）。
///
/// 只搬字段，不解释语义：留痕的形状归 `v1_trace`，本层只负责让它过线。
pub fn 编码留痕记录(留痕项: &v1_trace::留痕) -> Vec<u8> {
    let mut 载荷 = Vec::with_capacity(留痕记录字节数);
    载荷.extend_from_slice(&留痕项.实例号.to_le_bytes());
    载荷.extend_from_slice(&留痕项.能力号.取号值().to_le_bytes());
    载荷.extend_from_slice(&留痕项.入参指纹.to_le_bytes());
    载荷.extend_from_slice(&留痕项.结果码.to_le_bytes());
    载荷.extend_from_slice(&留痕项.耗时微秒.to_le_bytes());
    载荷.extend_from_slice(&留痕项.追踪号.to_le_bytes());
    载荷.push(留痕项.调用类 as u8);
    载荷.extend_from_slice(&留痕项.资源号.取号值().to_le_bytes());
    载荷.extend_from_slice(&留痕项.操作号.取号值().to_le_bytes());
    载荷
}

/// 解一条 `留痕记录` 帧的载荷（**唯一解码口**）。长度不对 ⇒ `None`（不成形就丢，不猜）。
pub fn 解码留痕记录(载荷: &[u8]) -> Option<v1_trace::留痕> {
    if 载荷.len() != 留痕记录字节数 {
        return None;
    }
    let 实例号 = u64::from_le_bytes(载荷[0..8].try_into().ok()?);
    let 能力号 = u32::from_le_bytes(载荷[8..12].try_into().ok()?);
    let 入参指纹 = u64::from_le_bytes(载荷[12..20].try_into().ok()?);
    let 结果码 = i32::from_le_bytes(载荷[20..24].try_into().ok()?);
    let 耗时微秒 = u64::from_le_bytes(载荷[24..32].try_into().ok()?);
    let 追踪号 = u64::from_le_bytes(载荷[32..40].try_into().ok()?);
    let 调用类 = 载荷[40];
    let 资源号 = u32::from_le_bytes(载荷[41..45].try_into().ok()?);
    let 操作号 = u32::from_le_bytes(载荷[45..49].try_into().ok()?);
    match 调用类 {
        0 => Some(v1_trace::留痕::能力调用(
            实例号,
            v1_contract::能力号::构造(能力号),
            入参指纹,
            结果码,
            耗时微秒,
            追踪号,
        )),
        1 => Some(v1_trace::留痕::资源访问(
            实例号,
            v1_contract::资源号::构造(资源号),
            v1_contract::操作号::构造(操作号),
            入参指纹,
            结果码,
            耗时微秒,
            追踪号,
        )),
        _ => None,
    }
}

pub struct 有界帧队列 {
    队列表: VecDeque<消息帧>,
    累计字节: usize,
    字节上限: usize,
}

impl 有界帧队列 {
    pub fn 业务队列() -> Self {
        Self { 队列表: VecDeque::new(), 累计字节: 0, 字节上限: 2 * 1024 * 1024 }
    }

    pub fn 控制队列() -> Self {
        Self { 队列表: VecDeque::new(), 累计字节: 0, 字节上限: 64 * 1024 }
    }

    pub fn 尝试入队(&mut self, 消息体: 消息帧) -> Result<(), 消息帧> {
        if self.队列表.len() >= 8 || 消息体.载荷.len() > 单帧载荷上限
            || 消息体.载荷.len() > self.字节上限 - self.累计字节 {
            return Err(消息体);
        }
        self.累计字节 += 消息体.载荷.len();
        self.队列表.push_back(消息体);
        Ok(())
    }

    pub fn 取队首(&mut self) -> Option<消息帧> {
        let 消息体 = self.队列表.pop_front()?;
        self.累计字节 -= 消息体.载荷.len();
        Some(消息体)
    }
}
