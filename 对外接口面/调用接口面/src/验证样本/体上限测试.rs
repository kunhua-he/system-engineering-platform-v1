//! 体上限的**验收样本** —— 命中上限时必须给结构化拒绍，不许把调用方打成连接复位。
//!
//! 现象（本件要挡的缺陷）：服务端读完头就回包并关连接，而调用方还在上传数 MB。
//! 读侧一个字节都不读就 `close()` ⇒ 内核回 RST ⇒ 调用方 `sendall` 抛
//! `ConnectionResetError`（Python `urllib` 实测 `[Errno 54]`），**拿不到 400 的正文**，
//! 也就拿不到「上限是多少、该怎么改」这两条信息。
//!
//! 四条样本各钉一件事：
//!
//! ① 真正超限（`Content-Length` 超上限、体也真写出去）⇒ 400 + JSON 信封 + 说明含上限字节数；
//! ② 刚好等于上限 ⇒ 正常受理（边界不许误杀）；
//! ③ 远超上限、调用方**边写边收** ⇒ 仍拿拒绍，不死锁、不无限读；
//! ④ 超限拒绍之后，同一个服务继续跑下一条合法请求。
//!
//! # 为什么必须开线程，以及调用方**不许 panic**
//!
//! 体是 MiB 级的：调用方一侧 `write_all` 会写满内核发送缓冲后阻塞，而 `服务` 又不 `Send`
//! （适配器不是）⇒ 用 `std::thread::scope` 借 `&服务` 起 `跑并发`（与 `并发测试.rs`
//! 同一条路子），调用方另起一条线程。端口仍由 OS 分配，不起第二个监听。
//!
//! 调用方线程一律**返回 `Result` 而不 `panic`**：`跑并发` 只能被 `请求停止` 叫醒，
//! 调用方一 panic，作用域就得等一条永不返回的服务线程 —— 样本在验证前就挂死，
//! 「服务端没回包」这条真信号反而看不到。

use crate::契约级常量::监听地址;
use crate::报文读写::体上限;
use crate::测试夹具::{发请求, 取请求, 第一个能力号, 解析应答, 起服务};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::{Duration, Instant};

/// 造一条**声明**了 `声明长度` 字节体的原始请求；`带体` 决定是否真把体写出去。
///
/// 不给体那种形状不是作弊：`Content-Length` 已经足够让服务端判超限 ——
/// 第 ④ 条就靠它省掉 8 MiB 的搬运。
fn 造超限请求(声明长度: usize, 带体: bool) -> String {
    let 头 = format!(
        "POST /接口/调用 HTTP/1.1\r\nHost: {监听地址}\r\nContent-Type: application/json\r\nContent-Length: {声明长度}\r\n\r\n"
    );
    if !带体 {
        return 头;
    }
    let mut 文本 = String::with_capacity(头.len() + 声明长度);
    文本.push_str(&头);
    文本.push_str(&"x".repeat(声明长度));
    文本
}

/// 调用方：连上 → 写全 → 读到 EOF。**失败给一段说明**（是写被打断还是读被复位）。
fn 取原始应答(监听端口: u16, 请求: &str) -> Result<Vec<u8>, String> {
    let mut 流 =
        TcpStream::connect((监听地址, 监听端口)).map_err(|错误| format!("连不上监听：{错误}"))?;
    流.write_all(请求.as_bytes())
        .map_err(|错误| format!("写请求被打断（连接复位）：{错误}"))?;
    流.flush().map_err(|错误| format!("刷请求失败：{错误}"))?;
    let mut 缓冲 = Vec::new();
    流.read_to_end(&mut 缓冲)
        .map_err(|错误| format!("读应答被复位（拒绍没落到调用方手里）：{错误}"))?;
    if 缓冲.is_empty() {
        return Err("一个应答字节都没收到".to_owned());
    }
    Ok(缓冲)
}

/// 收到的一串字节里是否已有**完整**应答（头体分界 + `Content-Length` 满足）。
fn 应答已完整(字节: &[u8]) -> bool {
    let Some(分界) = 字节.windows(4).position(|窗口| 窗口 == b"\r\n\r\n") else {
        return false;
    };
    let 头部 = String::from_utf8_lossy(&字节[..分界]).to_ascii_lowercase();
    let 长度 = 头部
        .lines()
        .find_map(|源码行| 源码行.strip_prefix("content-length:"))
        .and_then(|值| 值.trim().parse::<usize>().ok());
    match 长度 {
        Some(长度) => 字节.len() >= 分界 + 4 + 长度,
        None => false,
    }
}

/// 起服务 → 跑一次并发 → 发一条原始请求 → 收尾（服务线程一定收干净）。
fn 一条请求与服务(请求文本: String) -> Result<Vec<u8>, String> {
    let 服务实例 = 起服务();
    let 监听端口 = 服务实例.监听端口();
    std::thread::scope(|作用域| {
        let 服务引用 = &服务实例;
        let 服务线程 = 作用域.spawn(move || {
            let _ = 服务引用.跑并发(1);
        });
        let 客户端线程 = 作用域.spawn(move || 取原始应答(监听端口, &请求文本));
        let 客户端结果 = 客户端线程.join().expect("调用方线程不许 panic");
        服务实例.请求停止();
        服务线程.join().expect("服务线程必须被 请求停止 叫醒");
        客户端结果
    })
}

/// ① 真正超限的体（调用方还在上传）⇒ 结构化拒绍，不是连接复位。
#[test]
fn 体上限_超限请求体拿到结构化拒绍() {
    let 起点 = Instant::now();
    let 字节 = 一条请求与服务(造超限请求(体上限 + 1, true))
        .unwrap_or_else(|说明| panic!("超限请求必须拿到结构化拒绍，实际{说明}"));
    let 耗时 = 起点.elapsed();
    let 应答 = 解析应答(&字节);
    assert_eq!(
        应答.状态, 400,
        "超限必须是 400（请求本身不合法）：\n{}",
        应答.报文体
    );
    assert_eq!(
        应答.取文本("种类"),
        "协议",
        "超限属于「请求不合法」，种类必须是协议：\n{}",
        应答.报文体
    );
    let 说明 = 应答.取文本("协议错误");
    assert!(
        说明.contains(&体上限.to_string()),
        "说明里必须带上限字节数（{体上限}），调用方才知道该缩到多少：{说明}"
    );
    assert!(
        耗时 < Duration::from_secs(5),
        "超限拒绍必须有界返回，实际 {耗时:?}"
    );
}

/// ② 刚好等于上限 ⇒ 正常受理。边界是 `>` 不是 `>=`，不许误杀。
#[test]
fn 体上限_刚好等于上限正常受理() {
    // GET 的体与本面无关（不收体的端点不解析体），正好用来看「体照样被读完」。
    let 请求文本 = format!(
        "GET /接口 HTTP/1.1\r\nHost: {监听地址}\r\nContent-Length: {体上限}\r\n\r\n{}",
        "x".repeat(体上限)
    );
    let 字节 = 一条请求与服务(请求文本)
        .unwrap_or_else(|说明| panic!("刚好等于上限必须受理并回包，实际{说明}"));
    let 应答 = 解析应答(&字节);
    assert_eq!(
        应答.状态, 200,
        "刚好 {体上限} 字节必须受理（边界不能误杀）：\n{}",
        应答.报文体
    );
}

/// ③ 远超上限、调用方**边写边收** ⇒ 仍拿拒绍，且服务端不做无界读。
///
/// 这一条同时钉两件事：
///
/// - **不死锁**：读完头就回包，不许等调用方把 32 MiB 发完；
/// - **不无限读**：排空预算有硬顶（`报文读写::排空硬顶`，由 `体上限` 推导，编译期护栏钉住
///   「至少覆盖一次上限以内的超量」与「不超过上限的四倍」）；样本这一侧只认时间上界。
#[test]
fn 体上限_远超上限边写边收不死锁不无限读() {
    let 服务实例 = 起服务();
    let 监听端口 = 服务实例.监听端口();
    let 声明长度 = 体上限 * 4;
    let 起点 = Instant::now();
    let 字节 = std::thread::scope(|作用域| {
        let 服务引用 = &服务实例;
        let 服务线程 = 作用域.spawn(move || {
            let _ = 服务引用.跑并发(1);
        });
        let 客户端线程 = 作用域.spawn(move || 边写边收(监听端口, 声明长度));
        let 客户端结果 = 客户端线程.join().expect("调用方线程不许 panic");
        服务实例.请求停止();
        服务线程.join().expect("服务线程必须被 请求停止 叫醒");
        客户端结果
    })
    .unwrap_or_else(|说明| panic!("调用方还在写的时候就必须先拿到拒绍，实际{说明}"));
    let 耗时 = 起点.elapsed();
    let 应答 = 解析应答(&字节);
    assert_eq!(
        应答.状态, 400,
        "远超上限也是「请求不合法」⇒ 400：\n{}",
        应答.报文体
    );
    assert!(
        应答.取文本("协议错误").contains(&体上限.to_string()),
        "说明里必须带上限字节数：\n{}",
        应答.报文体
    );
    assert!(
        耗时 < Duration::from_secs(5),
        "边写边收必须有界返回（不无限读），实际 {耗时:?}"
    );
}

/// 调用方：声明 `声明长度`，**分块写**，每块之后试读一次 —— 拿到完整应答就停手。
fn 边写边收(监听端口: u16, 声明长度: usize) -> Result<Vec<u8>, String> {
    let mut 流 =
        TcpStream::connect((监听地址, 监听端口)).map_err(|错误| format!("连不上监听：{错误}"))?;
    // 试探用的短读超时：读不到就当「应答还没来」，继续写。
    流.set_read_timeout(Some(Duration::from_millis(20)))
        .map_err(|错误| format!("设置试探读超时失败：{错误}"))?;
    流.write_all(造超限请求(声明长度, false).as_bytes())
        .map_err(|错误| format!("写请求头失败：{错误}"))?;
    let 块 = vec![b'x'; 64 * 1024];
    let mut 已写 = 0usize;
    let mut 收到: Vec<u8> = Vec::new();
    let 截止 = Instant::now() + Duration::from_secs(5);
    while 已写 < 声明长度 && Instant::now() < 截止 && !应答已完整(&收到) {
        match 流.write(&块) {
            Ok(0) => break,
            Ok(写出) => 已写 += 写出,
            Err(错误) => return Err(format!("写到第 {已写} 字节被打断：{错误}")),
        }
        let mut 缓冲 = [0u8; 4096];
        match 流.read(&mut 缓冲) {
            Ok(0) => break,
            Ok(读到) => 收到.extend_from_slice(&缓冲[..读到]),
            // 还没回（试探超时）—— 继续写。
            Err(_) => {}
        }
    }
    // 收尾：把已经开头的那条应答读全（头体分界 + 定长体）。
    while !应答已完整(&收到) {
        let mut 缓冲 = [0u8; 4096];
        match 流.read(&mut 缓冲) {
            Ok(0) | Err(_) => break,
            Ok(读到) => 收到.extend_from_slice(&缓冲[..读到]),
        }
    }
    if 收到.is_empty() {
        return Err(format!("写了 {已写} 字节，一个应答字节都没收到"));
    }
    Ok(收到)
}

/// ④ 一条坏请求不许把服务带走：拒绍之后同一个服务照常处理合法请求。
#[test]
fn 体上限_超限拒绍后同一服务继续服务() {
    let 服务实例 = 起服务();
    let 编号 = 第一个能力号(&服务实例);
    // 只声明不发体：服务端按头就判超限，走完「回包 + 有限排空 + 关闭」整条路。
    let 坏应答 = 发请求(&服务实例, &造超限请求(体上限 + 1, false));
    assert_eq!(
        坏应答.状态, 400,
        "只声明超限长度也必须拒绍：\n{}",
        坏应答.报文体
    );
    let 好应答 = 发请求(&服务实例, &取请求(&format!("/接口/能力/{编号}")));
    assert_eq!(
        好应答.状态, 200,
        "超限拒绍之后同一服务必须继续服务（一条坏请求不许拖垮门）：\n{}",
        好应答.报文体
    );
}
