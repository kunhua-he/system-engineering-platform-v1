use std::num::NonZeroU64;
use std::os::unix::net::UnixStream;
use std::thread;
use std::time::{Duration, Instant};

use v1_contract::{类型标签, 数据槽};

use crate::进程帧::{调用帧预算, 接收帧, 发送帧, 消息帧, 消息类别};
use crate::线协议::{
    单次调用槽数上限, 编码调用请求, 编码调用结果, 解码调用请求, 解码调用结果,
    线协议错误, 线协议会话,
};
use crate::协议结果;

fn 内联槽(标签: u32, 值: u64) -> 数据槽 {
    数据槽::内联槽(类型标签::构造(标签), 值, 0)
}

fn 请求标识(号: u64) -> NonZeroU64 {
    NonZeroU64::new(号).unwrap()
}

fn 测试预算() -> 调用帧预算 {
    调用帧预算::创建(Instant::now() + Duration::from_millis(500)).unwrap()
}

#[test]
fn 调用请求编解码往返() {
    let 槽表 = vec![内联槽(1, 1101), 数据槽::空槽()];
    let 载荷 = 编码调用请求(1101, &槽表).unwrap();
    let (号值, 回读槽表) = 解码调用请求(&载荷).unwrap();
    assert_eq!(号值, 1101);
    assert_eq!(回读槽表, 槽表);
}

#[test]
fn 解码调用请求先校界限() {
    assert_eq!(解码调用请求(&[0u8; 4]).unwrap_err(), 线协议错误::载荷过短);
    let mut 载荷 = Vec::new();
    载荷.extend_from_slice(&1101u32.to_le_bytes());
    载荷.extend_from_slice(&((单次调用槽数上限 + 1) as u32).to_le_bytes());
    assert_eq!(解码调用请求(&载荷).unwrap_err(), 线协议错误::槽数越界);
}

#[test]
fn 编码拒绝带数据的引用槽() {
    let 槽表 = vec![数据槽::指针(类型标签::构造(1), 4096, 64, false)];
    assert_eq!(编码调用请求(1101, &槽表).unwrap_err(), 线协议错误::含引用槽);
}

#[test]
fn 调用结果只在两个协议码内() {
    let 载荷 = 编码调用结果(协议结果::成功, &内联槽(1, 42)).unwrap();
    let (协议码值, 返回槽) = 解码调用结果(&载荷).unwrap();
    assert_eq!(协议码值, 协议结果::成功);
    assert_eq!(返回槽, 内联槽(1, 42));
    let mut 坏载荷 = 7i32.to_le_bytes().to_vec();
    坏载荷.extend_from_slice(&载荷[4..]);
    assert_eq!(解码调用结果(&坏载荷).unwrap_err(), 线协议错误::协议码越界);
    assert_eq!(解码调用结果(&载荷[..5]).unwrap_err(), 线协议错误::结果头不符);
}

#[test]
fn 会话收发一次调用结果() {
    let (客户端, 服务端) = UnixStream::pair().unwrap();
    let 服务线程 = thread::spawn(move || {
        let mut 服务端 = 服务端;
        let 请求帧 = 接收帧(&mut 服务端, 请求标识(7), &mut 测试预算()).unwrap();
        let (号值, _参数槽表) = 解码调用请求(&请求帧.载荷).unwrap();
        let 返回槽 = 内联槽(2, u64::from(号值));
        let 结果帧 = 消息帧 {
            消息类型: 消息类别::调用结果,
            请求标识: 请求标识(7),
            载荷: 编码调用结果(协议结果::成功, &返回槽).unwrap(),
        };
        发送帧(&mut 服务端, &结果帧, &mut 测试预算()).unwrap();
    });
    let mut 会话 = 线协议会话::新建(客户端);
    let 标识 = 请求标识(7);
    会话.发起调用(标识, 1101, &[内联槽(1, 5)]).unwrap();
    let (协议码值, 返回槽) = 会话.收调用结果(标识).unwrap();
    服务线程.join().unwrap();
    assert_eq!(协议码值, 协议结果::成功);
    assert_eq!(返回槽, 内联槽(2, 1101));
}

#[test]
fn 收到别的类别即拒() {
    let (客户端, 服务端) = UnixStream::pair().unwrap();
    let 服务线程 = thread::spawn(move || {
        let mut 服务端 = 服务端;
        let 通知帧 = 消息帧 { 消息类型: 消息类别::通知, 请求标识: 请求标识(8), 载荷: Vec::new() };
        发送帧(&mut 服务端, &通知帧, &mut 测试预算()).unwrap();
    });
    let mut 会话 = 线协议会话::新建(客户端);
    assert_eq!(会话.收调用结果(请求标识(8)), Err(线协议错误::非调用结果帧));
    服务线程.join().unwrap();
}

#[test]
fn 排队投递满了结构化拒绝() {
    let (客户端, 服务端) = UnixStream::pair().unwrap();
    let 服务线程 = thread::spawn(move || {
        let mut 服务端 = 服务端;
        let 帧 = 消息帧 {
            消息类型: 消息类别::调用结果,
            请求标识: 请求标识(5),
            载荷: 编码调用结果(协议结果::成功, &数据槽::空槽()).unwrap(),
        };
        for _次 in 0..9 {
            发送帧(&mut 服务端, &帧, &mut 测试预算()).unwrap();
        }
    });
    let mut 会话 = 线协议会话::新建(客户端);
    let mut 结果 = Ok(());
    for _次 in 0..9 {
        结果 = 会话.排队投递(请求标识(5));
    }
    服务线程.join().unwrap();
    assert_eq!(结果, Err(线协议错误::队列已满));
    assert!(会话.取一件().is_some());
}
