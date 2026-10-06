use std::collections::VecDeque;
use std::io::{self, Read, Write};
use std::os::unix::net::UnixStream;
use std::num::NonZeroU64;
use std::time::{Duration, Instant};

const 帧头字节数: usize = 24;
const 单帧载荷上限: usize = 1024 * 1024;
const 调用载荷上限: usize = 4 * 1024 * 1024;

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

    fn 剩余时限(&self) -> io::Result<Duration> {
        self.截止时间.checked_duration_since(Instant::now())
            .filter(|时长| !时长.is_zero())
            .ok_or_else(|| io::Error::new(io::ErrorKind::TimedOut, "调用预算耗尽"))
    }
}

fn 继续等待(预算: &调用帧预算) -> io::Result<()> {
    std::thread::sleep(预算.剩余时限()?.min(Duration::from_millis(1)));
    Ok(())
}

fn 写全帧(通信通道: &mut UnixStream, mut 待写字节: &[u8], 预算: &调用帧预算) -> io::Result<()> {
    while !待写字节.is_empty() {
        预算.剩余时限()?;
        match 通信通道.write(待写字节) {
            Ok(0) => return Err(io::Error::new(io::ErrorKind::WriteZero, "通道不再接收帧")),
            Ok(写入长度) => 待写字节 = &待写字节[写入长度..],
            Err(错误) if 错误.kind() == io::ErrorKind::WouldBlock => 继续等待(预算)?,
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
            Err(错误) if 错误.kind() == io::ErrorKind::WouldBlock => 继续等待(预算)?,
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

pub fn 接收帧(通信通道: &mut UnixStream, 请求标识: NonZeroU64, 预算: &mut 调用帧预算) -> io::Result<消息帧> {
    通信通道.set_nonblocking(true)?;
    let mut 帧头 = [0u8; 帧头字节数];
    读全帧(通信通道, &mut 帧头, 预算)?;
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
        _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "未知IPC消息类别")),
    };
    let 帧请求标识 = NonZeroU64::new(u64::from_le_bytes(帧头[8..16].try_into().unwrap()))
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "IPC请求标识为零"))?;
    let 载荷长度 = u32::from_le_bytes(帧头[16..20].try_into().unwrap()) as usize;
    let 剩余毫秒 = u32::from_le_bytes(帧头[20..24].try_into().unwrap());
    if 帧请求标识 != 请求标识 || 载荷长度 > 单帧载荷上限
        || 载荷长度 > 预算.接收剩余 || 剩余毫秒 == 0 || 剩余毫秒 > 5000 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "IPC请求、长度或预算不符"));
    }
    let 远端截止 = Instant::now() + Duration::from_millis(u64::from(剩余毫秒));
    预算.截止时间 = 预算.截止时间.min(远端截止);
    预算.接收剩余 -= 载荷长度;
    let mut 载荷 = vec![0u8; 载荷长度];
    读全帧(通信通道, &mut 载荷, 预算)?;
    Ok(消息帧 { 消息类型, 请求标识: 帧请求标识, 载荷 })
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
