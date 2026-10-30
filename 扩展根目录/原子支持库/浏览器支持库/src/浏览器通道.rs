//! 浏览器通道：手写最小 HTTP + WebSocket 客户端，直连 Chrome 的 DevTools 协议。
//!
//! 为什么手写：底座扩展要零外部依赖（离线仓没有 websocket 库），而 CDP 只需要
//! 「一次 HTTP GET 拿调试地址 + 一条 WebSocket 收发 JSON」，用系统标准库就够。
//! 只支持 CDP 实际会用到的那一小撮：文本帧、分片重组、ping/pong 应答。

use std::io::{Read, Write};
use std::net::TcpStream;

/// 最小 SHA-1（WebSocket 握手要 Sec-WebSocket-Accept），只算一次不追求速度
fn 取摘要值(输入: &[u8]) -> [u8; 20] {
    let mut 状态: [u32; 5] = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0];
    let 原长 = (输入.len() as u64) * 8;
    let mut 数据 = 输入.to_vec();
    数据.push(0x80);
    while 数据.len() % 64 != 56 {
        数据.push(0);
    }
    数据.extend_from_slice(&原长.to_be_bytes());
    for 块 in 数据.chunks(64) {
        let mut 字 = [0u32; 80];
        for 序 in 0..16 {
            字[序] = u32::from_be_bytes([块[序 * 4], 块[序 * 4 + 1], 块[序 * 4 + 2], 块[序 * 4 + 3]]);
        }
        for 序 in 16..80 {
            字[序] = (字[序 - 3] ^ 字[序 - 8] ^ 字[序 - 14] ^ 字[序 - 16]).rotate_left(1);
        }
        let (mut 甲, mut 乙, mut 丙, mut 丁, mut 戊) = (状态[0], 状态[1], 状态[2], 状态[3], 状态[4]);
        for (序, 当前字) in 字.iter().enumerate() {
            let (函数值, 常量值) = match 序 {
                0..=19 => ((乙 & 丙) | ((!乙) & 丁), 0x5A827999u32),
                20..=39 => (乙 ^ 丙 ^ 丁, 0x6ED9EBA1),
                40..=59 => ((乙 & 丙) | (乙 & 丁) | (丙 & 丁), 0x8F1BBCDC),
                _ => (乙 ^ 丙 ^ 丁, 0xCA62C1D6),
            };
            let 临时 = 甲.rotate_left(5)
                .wrapping_add(函数值)
                .wrapping_add(戊)
                .wrapping_add(常量值)
                .wrapping_add(*当前字);
            戊 = 丁;
            丁 = 丙;
            丙 = 乙.rotate_left(30);
            乙 = 甲;
            甲 = 临时;
        }
        状态[0] = 状态[0].wrapping_add(甲);
        状态[1] = 状态[1].wrapping_add(乙);
        状态[2] = 状态[2].wrapping_add(丙);
        状态[3] = 状态[3].wrapping_add(丁);
        状态[4] = 状态[4].wrapping_add(戊);
    }
    let mut 输出 = [0u8; 20];
    for 序 in 0..5 {
        输出[序 * 4..序 * 4 + 4].copy_from_slice(&状态[序].to_be_bytes());
    }
    输出
}

fn 取编码文本(输入: &[u8]) -> String {
    const 表: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut 结果 = String::new();
    for 组 in 输入.chunks(3) {
        let 甲 = 组[0] as u32;
        let 乙 = *组.get(1).unwrap_or(&0) as u32;
        let 丙 = *组.get(2).unwrap_or(&0) as u32;
        let 合 = (甲 << 16) | (乙 << 8) | 丙;
        结果.push(表[(合 >> 18) as usize & 63] as char);
        结果.push(表[(合 >> 12) as usize & 63] as char);
        结果.push(if 组.len() > 1 { 表[(合 >> 6) as usize & 63] as char } else { '=' });
        结果.push(if 组.len() > 2 { 表[合 as usize & 63] as char } else { '=' });
    }
    结果
}

/// 16 字节随机密钥（时间纳秒 + 地址抖动；本地 CDP 够用，不引随机数库）
fn 取随机密钥() -> String {
    let 纳秒 = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|时长| 时长.subsec_nanos())
        .unwrap_or(0);
    let 种子 = (纳秒 as u64) ^ ((std::process::id() as u64) << 32) ^ (&纳秒 as *const u32 as u64);
    let mut 字节 = [0u8; 16];
    let mut 态 = 种子 | 1;
    for 位 in 字节.iter_mut() {
        态 ^= 态 << 13;
        态 ^= 态 >> 7;
        态 ^= 态 << 17;
        *位 = (态 & 0xFF) as u8;
    }
    取编码文本(&字节)
}

/// 发一次最小 HTTP 请求，返回响应体（只处理 CDP 用到的 GET / PUT）。
///
/// **不能 read_to_end**：Chrome 的调试口默认 keep-alive，读到 EOF 要等到超时
/// （实测卡满 15 秒还把请求判成连接失败）。按 Content-Length 精确读。
pub(crate) fn 请求调试口(端口: u16, 方法: &str, 路径: &str) -> Result<String, u32> {
    let 地址 = format!("127.0.0.1:{}", 端口);
    let mut 连接 = TcpStream::connect(&地址).map_err(|_| 错误码::连接失败)?;
    连接
        .set_read_timeout(Some(std::time::Duration::from_secs(15)))
        .ok();
    let 报文 = format!(
        "{} {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nAccept: application/json\r\n\r\n",
        方法, 路径, 地址
    );
    连接.write_all(报文.as_bytes()).map_err(|_| 错误码::连接失败)?;
    let mut 头缓冲 = Vec::new();
    let mut 单字节 = [0u8; 1];
    while !头缓冲.ends_with(b"\r\n\r\n") {
        if 连接.read(&mut 单字节).map_err(|_| 错误码::连接失败)? == 0 {
            return Err(错误码::连接失败);
        }
        头缓冲.push(单字节[0]);
        if 头缓冲.len() > 16384 {
            return Err(错误码::协议不符);
        }
    }
    let 头文本 = String::from_utf8_lossy(&头缓冲).into_owned();
    if !头文本.starts_with("HTTP/1.") {
        return Err(错误码::协议不符);
    }
    let mut 长度: Option<usize> = None;
    for 行 in 头文本.lines() {
        if let Some((键, 值)) = 行.split_once(':')
            && 键.trim().eq_ignore_ascii_case("content-length")
        {
            长度 = 值.trim().parse::<usize>().ok();
        }
    }
    let 目标长度 = 长度.ok_or(错误码::协议不符)?;
    if 目标长度 > 8 * 1024 * 1024 {
        return Err(错误码::资源超限);
    }
    let mut 体 = vec![0u8; 目标长度];
    读满(&mut 连接, &mut 体)?;
    Ok(String::from_utf8_lossy(&体).into_owned())
}

/// 一条已握手的 WebSocket 连接（CDP 的指令通道）
pub(crate) struct 调试连接 {
    连接: TcpStream,
}

impl 调试连接 {
    /// 按 ws://host:port/path 建连并完成握手
    pub(crate) fn 建连(端口: u16, 路径: &str) -> Result<Self, u32> {
        let 地址 = format!("127.0.0.1:{}", 端口);
        let mut 连接 = TcpStream::connect(&地址).map_err(|_| 错误码::连接失败)?;
        连接.set_read_timeout(Some(std::time::Duration::from_secs(60))).ok();
        let 密钥 = 取随机密钥();
        let 期望接受 = 取编码文本(&取摘要值(format!("{}258EAFA5-E914-47DA-95CA-C5AB0DC85B11", 密钥).as_bytes()));
        let 报文 = format!(
            "GET {} HTTP/1.1\r\nHost: {}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\
             Sec-WebSocket-Key: {}\r\nSec-WebSocket-Version: 13\r\n\r\n",
            路径, 地址, 密钥
        );
        连接.write_all(报文.as_bytes()).map_err(|_| 错误码::连接失败)?;
        let mut 缓冲 = Vec::new();
        let mut 单字节 = [0u8; 1];
        while !缓冲.ends_with(b"\r\n\r\n") {
            if 连接.read(&mut 单字节).map_err(|_| 错误码::连接失败)? == 0 {
                return Err(错误码::协议不符);
            }
            缓冲.push(单字节[0]);
            if 缓冲.len() > 8192 {
                return Err(错误码::协议不符);
            }
        }
        let 应答 = String::from_utf8_lossy(&缓冲).into_owned();
        if !应答.starts_with("HTTP/1.1 101") && !应答.starts_with("HTTP/1.0 101") {
            return Err(错误码::协议不符);
        }
        // 按 RFC6455 校验 Accept：算错的握手不能当成连上了
        let 接受对得上 = 应答.lines().any(|行| {
            行.to_ascii_lowercase().starts_with("sec-websocket-accept:")
                && 行.split_once(':').map(|(_, 值)| 值.trim() == 期望接受).unwrap_or(false)
        });
        if !接受对得上 {
            return Err(错误码::协议不符);
        }
        Ok(Self { 连接 })
    }

    /// 发一条文本帧（客户端必须加掩码）
    pub(crate) fn 发文本(&mut self, 载荷: &str) -> Result<(), u32> {
        let 数据 = 载荷.as_bytes();
        let mut 帧 = Vec::with_capacity(数据.len() + 14);
        帧.push(0x81);
        if 数据.len() < 126 {
            帧.push(0x80 | 数据.len() as u8);
        } else if 数据.len() <= u16::MAX as usize {
            帧.push(0x80 | 126);
            帧.extend_from_slice(&(数据.len() as u16).to_be_bytes());
        } else {
            帧.push(0x80 | 127);
            帧.extend_from_slice(&(数据.len() as u64).to_be_bytes());
        }
        let 掩码 = [0x37u8, 0x11, 0x5Au8, 0x2B];
        帧.extend_from_slice(&掩码);
        for (序, 字节) in 数据.iter().enumerate() {
            帧.push(字节 ^ 掩码[序 % 4]);
        }
        连接写(&mut self.连接, &帧)
    }

    /// 收一条完整文本消息：自动拼分片、回 ping
    pub(crate) fn 收文本(&mut self) -> Result<String, u32> {
        let mut 完整 = Vec::new();
        loop {
            let (操作码, 分段, 收尾) = 读一帧(&mut self.连接)?;
            match 操作码 {
                0x1 | 0x0 => 完整.extend_from_slice(&分段),
                0x9 => {
                    let mut 帧 = vec![0x8A, 0x80, 0, 0, 0, 0];
                    帧.extend_from_slice(&分段);
                    连接写(&mut self.连接, &帧)?;
                }
                0x8 => return Err(错误码::连接失败),
                _ => {}
            }
            if 收尾 {
                return Ok(String::from_utf8_lossy(&完整).into_owned());
            }
        }
    }
}

fn 连接写(连接: &mut TcpStream, 数据: &[u8]) -> Result<(), u32> {
    连接.write_all(数据).map_err(|_| 错误码::连接失败)
}

fn 读满(连接: &mut TcpStream, 目标: &mut [u8]) -> Result<(), u32> {
    let mut 已读 = 0;
    while 已读 < 目标.len() {
        let 本次 = 连接.read(&mut 目标[已读..]).map_err(|_| 错误码::连接失败)?;
        if 本次 == 0 {
            return Err(错误码::连接失败);
        }
        已读 += 本次;
    }
    Ok(())
}

/// 读一帧，返回 (操作码, 载荷, 是否末帧)
fn 读一帧(连接: &mut TcpStream) -> Result<(u8, Vec<u8>, bool), u32> {
    let mut 头 = [0u8; 2];
    读满(连接, &mut 头)?;
    let 收尾 = 头[0] & 0x80 != 0;
    let 操作码 = 头[0] & 0x0F;
    let 有掩码 = 头[1] & 0x80 != 0;
    let mut 长度 = (头[1] & 0x7F) as u64;
    if 长度 == 126 {
        let mut 扩展 = [0u8; 2];
        读满(连接, &mut 扩展)?;
        长度 = u16::from_be_bytes(扩展) as u64;
    } else if 长度 == 127 {
        let mut 扩展 = [0u8; 8];
        读满(连接, &mut 扩展)?;
        长度 = u64::from_be_bytes(扩展);
    }
    if 长度 > 80 * 1024 * 1024 {
        return Err(错误码::资源超限);
    }
    let mut 掩码 = [0u8; 4];
    if 有掩码 {
        读满(连接, &mut 掩码)?;
    }
    let mut 载荷 = vec![0u8; 长度 as usize];
    读满(连接, &mut 载荷)?;
    if 有掩码 {
        for (序, 字节) in 载荷.iter_mut().enumerate() {
            *字节 ^= 掩码[序 % 4];
        }
    }
    Ok((操作码, 载荷, 收尾))
}

use crate::编号与码面::错误码;
