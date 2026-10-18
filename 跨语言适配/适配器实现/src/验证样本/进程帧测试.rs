use std::io::Write;
use std::num::NonZeroU64;
use std::os::unix::net::UnixStream;
use std::time::{Duration, Instant};

use crate::进程帧::{发送帧, 接收帧, 有界帧队列, 消息帧, 消息类别, 调用帧预算};

fn 测试预算() -> 调用帧预算 {
    调用帧预算::创建(Instant::now() + Duration::from_millis(200)).unwrap()
}

fn 测试帧(请求标识: u64, 字节数: usize) -> 消息帧 {
    消息帧 { 消息类型: 消息类别::调用, 请求标识: NonZeroU64::new(请求标识).unwrap(), 载荷: vec![7u8; 字节数] }
}

#[test]
fn 帧字段与载荷完整往返() {
    let (mut 发送通道, mut 接收通道) = UnixStream::pair().unwrap();
    let 原帧 = 测试帧(41, 512);
    发送帧(&mut 发送通道, &原帧, &mut 测试预算()).unwrap();
    assert_eq!(接收帧(&mut 接收通道, NonZeroU64::new(41).unwrap(), &mut 测试预算()).unwrap(), 原帧);
}

#[test]
fn 帧请求标识不符执行前拒绝() {
    let (mut 发送通道, mut 接收通道) = UnixStream::pair().unwrap();
    发送帧(&mut 发送通道, &测试帧(41, 0), &mut 测试预算()).unwrap();
    assert_eq!(接收帧(&mut 接收通道, NonZeroU64::new(42).unwrap(), &mut 测试预算()).unwrap_err().kind(), std::io::ErrorKind::InvalidData);
}

#[test]
fn 半帧断连与无响应均有界拒绝() {
    let (mut 发送通道, mut 接收通道) = UnixStream::pair().unwrap();
    发送通道.write_all(b"V1IP").unwrap();
    drop(发送通道);
    assert_eq!(接收帧(&mut 接收通道, NonZeroU64::new(41).unwrap(), &mut 测试预算()).unwrap_err().kind(), std::io::ErrorKind::UnexpectedEof);
    let (_发送通道, mut 接收通道) = UnixStream::pair().unwrap();
    let 开始时间 = Instant::now();
    assert_eq!(接收帧(&mut 接收通道, NonZeroU64::new(41).unwrap(), &mut 测试预算()).unwrap_err().kind(), std::io::ErrorKind::TimedOut);
    assert!(开始时间.elapsed() < Duration::from_millis(500));
}

#[test]
fn 超长帧只读帧头不分配载荷() {
    let (mut 发送通道, mut 接收通道) = UnixStream::pair().unwrap();
    let mut 帧头 = [0u8; 24];
    帧头[..4].copy_from_slice(b"V1IP");
    帧头[4..6].copy_from_slice(&1u16.to_le_bytes());
    帧头[6..8].copy_from_slice(&1u16.to_le_bytes());
    帧头[8..16].copy_from_slice(&41u64.to_le_bytes());
    帧头[16..20].copy_from_slice(&u32::MAX.to_le_bytes());
    帧头[20..24].copy_from_slice(&100u32.to_le_bytes());
    发送通道.write_all(&帧头).unwrap();
    assert_eq!(接收帧(&mut 接收通道, NonZeroU64::new(41).unwrap(), &mut 测试预算()).unwrap_err().kind(), std::io::ErrorKind::InvalidData);
}

#[test]
fn 满队列保留拒绝帧且控制队列独立() {
    let mut 业务队列 = 有界帧队列::业务队列();
    for 请求标识 in 1..=8 {
        业务队列.尝试入队(测试帧(请求标识, 0)).unwrap();
    }
    let 拒绝帧 = 业务队列.尝试入队(测试帧(9, 0)).unwrap_err();
    assert_eq!(拒绝帧.请求标识.get(), 9);
    let mut 控制队列 = 有界帧队列::控制队列();
    控制队列.尝试入队(消息帧 { 消息类型: 消息类别::停止, 请求标识: NonZeroU64::new(9).unwrap(), 载荷: Vec::new() }).unwrap();
    assert_eq!(控制队列.取队首().unwrap().消息类型, 消息类别::停止);
    assert_eq!(业务队列.取队首().unwrap().请求标识.get(), 1);
}

#[test]
fn 队列累计字节配额不能用少量大帧绕过() {
    let mut 业务队列 = 有界帧队列::业务队列();
    业务队列.尝试入队(测试帧(1, 1024 * 1024)).unwrap();
    业务队列.尝试入队(测试帧(2, 1024 * 1024)).unwrap();
    assert!(业务队列.尝试入队(测试帧(3, 1)).is_err());
    业务队列.取队首();
    assert!(业务队列.尝试入队(测试帧(3, 1)).is_ok());
}
