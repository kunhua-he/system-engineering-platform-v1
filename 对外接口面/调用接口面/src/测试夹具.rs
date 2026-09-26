//! 测试夹具 —— **真起服务、真发原始请求**要用的最小客户端。
//!
//! 用 `std::net::TcpStream` 手写请求，不引任何 HTTP 客户端库（本仓硬规矩：零第三方依赖）。
//! 为什么不用一个现成的客户端：那样测的就是「客户端库 + 我的服务」，而不是**我的服务的
//! 协议层**——请求行怎么写、头怎么给、体长度怎么算，正是本面要负责的事。
//!
//! # 为什么不必开线程
//!
//! `TcpStream::connect` 只要监听套接字已经 `bind`+`listen` 就会成功（内核的 accept 队列
//! 接住它），**不需要服务端已经 `accept`**。所以测试可以：先连上、先写请求，
//! 再调 `服务::处理一个连接()`，最后读应答 —— 全在一个线程里。
//! 这样也就不需要把 `服务` 搬进线程（它搬不进去：适配器不是 `Send`，见 `网关.rs` 文件头）。

use crate::协议值::协议值;
use crate::常量::监听地址;
use crate::网关::服务;
use std::io::{Read, Write};
use std::net::TcpStream;

/// 错误体必须齐的六项（`接口面形状.md` §三 冻结）。
pub const 六项: [&str; 6] = ["码", "段位", "名称", "可重试", "可自愈", "需人工"];

/// 收到的一条应答：状态码 + 头 + 体。
pub struct 收到 {
    pub 状态: u16,
    pub 头: String,
    pub 体: String,
}

impl 收到 {
    /// 体解析成 JSON。**应答体必须是合法 JSON** —— 不是就当场挂（那是本面的缺陷）。
    pub fn 取协议值(&self) -> 协议值 {
        crate::协议解析::解析(&self.体).unwrap_or_else(|错| {
            panic!(
                "应答体必须是合法 JSON，却在第 {} 字节报「{}」：\n{}",
                错.位置, 错.说明, self.体
            )
        })
    }

    /// 取一个顶层键；**没有就挂**（要判「没有」请用 `找`）。
    pub fn 取(&self, 键: &str) -> 协议值 {
        self.找(键)
            .unwrap_or_else(|| panic!("应答里没有「{键}」：\n{}", self.体))
    }

    /// 找一个顶层键；没有给 `None`。
    pub fn 找(&self, 键: &str) -> Option<协议值> {
        self.取协议值().取(键).cloned()
    }

    /// 取顶层的一个布尔键。
    pub fn 取布尔(&self, 键: &str) -> bool {
        match self.取(键) {
            协议值::真 => true,
            协议值::假 => false,
            其它 => panic!("「{键}」应当是布尔，实际 {其它:?}：\n{}", self.体),
        }
    }

    /// 取顶层的一个文本键。
    pub fn 取文本(&self, 键: &str) -> String {
        self.取(键)
            .取文本()
            .map(str::to_owned)
            .unwrap_or_else(|| panic!("「{键}」应当是文本：\n{}", self.体))
    }

    /// 取顶层的一个数组键。
    pub fn 取数组(&self, 键: &str) -> Vec<协议值> {
        self.取(键)
            .取数组()
            .map(<[协议值]>::to_vec)
            .unwrap_or_else(|| panic!("「{键}」应当是数组：\n{}", self.体))
    }
}

/// 取一个布尔成员。**不是布尔就挂**：形状不对当场暴露，不静默当 `false`。
pub fn 布尔(值: &协议值, 键: &str) -> bool {
    match 值.取(键) {
        Some(协议值::真) => true,
        Some(协议值::假) => false,
        其它 => panic!("「{键}」应当是布尔，实际 {其它:?}"),
    }
}

/// 取一个非负整数成员。
pub fn 无符号(值: &协议值, 键: &str) -> u64 {
    值.取(键)
        .and_then(协议值::取无符号)
        .unwrap_or_else(|| panic!("「{键}」应当是非负整数，实际 {:?}", 值.取(键)))
}

/// 取一个文本成员。
pub fn 文本(值: &协议值, 键: &str) -> String {
    值.取(键)
        .and_then(协议值::取文本)
        .map(str::to_owned)
        .unwrap_or_else(|| panic!("「{键}」应当是文本，实际 {:?}", 值.取(键)))
}

/// 取一个数组成员。
pub fn 数组(值: &协议值, 键: &str) -> Vec<协议值> {
    值.取(键)
        .and_then(协议值::取数组)
        .map(<[协议值]>::to_vec)
        .unwrap_or_else(|| panic!("「{键}」应当是数组，实际 {:?}", 值.取(键)))
}

/// 起一个服务：声明根只有底座自己那一份，端口让 OS 分配（避免测试互相撞）。
pub fn 起服务() -> 服务 {
    服务::绑定(&[v1_loader::底座声明()], 0).expect("底座自己的声明必须载得进来")
}

/// 唯一腿上的第一个能力号（**不写死 0**：编号是适配器报出来的，测试跟着它走）。
pub fn 第一个能力号(服务: &服务) -> u32 {
    服务.适配器().能力清单()[0].编号
}

/// 一条 GET 请求（原始文本）。
pub fn 取请求(路径: &str) -> String {
    format!("GET {路径} HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: application/json\r\n\r\n")
}

/// 一条 POST 请求（原始文本）。`Content-Length` 按**字节数**算，与冻结件一致。
pub fn 交请求(路径: &str, 体: &str) -> String {
    format!(
        "POST {路径} HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\n\r\n{体}",
        体.len()
    )
}

/// 发一条原始请求并收回应答。
///
/// 顺序固定：连上 → 写请求 → **服务处理一次** → 读应答。见文件头「为什么不必开线程」。
pub fn 发(服务: &服务, 请求: &str) -> 收到 {
    let mut 流 = TcpStream::connect((监听地址, 服务.端口())).expect("必须连得上（监听已 bind）");
    流.write_all(请求.as_bytes()).expect("写请求");
    流.flush().expect("刷请求");
    服务.处理一个连接().expect("服务必须处理一次");
    let mut 缓冲 = Vec::new();
    流.read_to_end(&mut 缓冲).expect("读应答");
    解析应答(&缓冲)
}

/// 解析原始应答文本。
fn 解析应答(字节: &[u8]) -> 收到 {
    let 文 = String::from_utf8(字节.to_vec()).expect("应答必须是 UTF-8");
    let (头, 体) = 文
        .split_once("\r\n\r\n")
        .unwrap_or_else(|| panic!("应答必须有头体分界：\n{文}"));
    let 状态 = 头
        .lines()
        .next()
        .and_then(|行| 行.split(' ').nth(1))
        .and_then(|码| 码.parse::<u16>().ok())
        .unwrap_or_else(|| panic!("应答首行必须是「HTTP/1.1 码 短语」：\n{文}"));
    收到 {
        状态,
        头: 头.to_owned(),
        体: 体.to_owned(),
    }
}
