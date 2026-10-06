//! HTTP/1.1 报文读写 —— 手写，零第三方依赖（`网关.rs` 是监听与并发，本件是报文层）。
//!
//! 从 `网关.rs` 拆出来只为「单个源文件 ≤ 400 行」（`开发规范.md` 第六节）：
//! 报文层是纯粹的「字节 ↔ 形状」翻译，与监听/并发无关，单独成件更清楚。
//!
//! # 明确不做（与 `网关.rs` 文件头同）
//!
//! - 不做 `Transfer-Encoding: chunked`：收到即 400（要支持它就得做流式状态机 = 连接管理）。
//! - 不做 `keep-alive` / `pipelining`：一个连接一个请求，读到定长体为止，余料丢弃。

use crate::分发::造应答;
use std::io::{Read, Write};
use std::net::TcpStream;

/// 请求头（含请求行）的字节上限。
pub(crate) const 头区上限: usize = 16 * 1024;
/// 请求体的字节上限。**旁路策略**：不设上限就是让一次请求决定进程的内存。
pub(crate) const 体上限: usize = 1 << 20;

/// 一条已读完的 HTTP 请求。**方法 · 目标 · 体 · 三个边界头**。
///
/// # 为什么留 `主机` / `来源站点` / `内容类型`（审计发现2 · P1）
///
/// 原先本结构只留方法 / 目标 / 体，**丢掉全部请求头**。后果是回环口收「外源形状」的副作用
/// 请求照执行（审计实测：`Host=attacker.example` + `Origin=https://attacker.example` +
/// `Content-Type: text/plain` 的写请求返回 200 并真落了件）—— 不做 CORS 不等于拒绝跨源请求，
/// 浏览器允许访问回环服务时即构成 CSRF 面。这三个头是**边界判定**唯一要的输入（判定在
/// `报文校验.rs`，本件只负责**留值**，不做任何解释）：
///
/// - `主机`（`Host`）—— HTTP/1.1 必带，非本机 ⇒ 拒；
/// - `来源站点`（`Origin`）—— 跨源时浏览器会带，带且非本机 ⇒ 拒；
/// - `内容类型`（`Content-Type`）—— 副作用端点只收 `application/json`。
///
/// 保留头**不是**加鉴权：`接口面形状.md` §一「第一次用不需要读文档就能调对」照旧成立
/// （无 `Origin` 的命令行 / 脚本请求一律放行）—— 校验只挡「浏览器替别的站点发的」那一类。
/// 值一律**原样留、不裁不改**：解释与判定只有一处（`报文校验.rs`），两处解释必然漂。
#[derive(Debug, Clone)]
pub struct 报文 {
    pub 请求方法: String,
    pub 请求目标: String,
    pub 报文体: String,
    /// `Host` 头原值（缺省 = 空串）。
    pub 主机: String,
    /// `Origin` 头原值（缺省 = 空串 ⇒ 同源 / 命令行请求）。
    pub 来源站点: String,
    /// `Content-Type` 头原值（缺省 = 空串）。
    pub 内容类型: String,
}

/// 读一条请求。错误是**一句可读说明**（⇒ 400）。
pub(crate) fn 读报文(输出流: &mut TcpStream) -> Result<报文, String> {
    let mut 缓冲: Vec<u8> = Vec::with_capacity(1024);
    let mut 读缓冲 = [0u8; 4096];
    let 头尾 = loop {
        if let Some(字节位置) = 找头体分界(&缓冲) {
            break 字节位置;
        }
        if 缓冲.len() > 头区上限 {
            return Err(format!("请求头超过 {头区上限} 字节"));
        }
        let 读到 = 输出流.read(&mut 读缓冲).map_err(|错误| format!("读请求失败：{错误}"))?;
        if 读到 == 0 {
            return Err("连接在请求写完之前就断了".to_owned());
        }
        缓冲.extend_from_slice(&读缓冲[..读到]);
    };

    let 头部 = core::str::from_utf8(&缓冲[..头尾])
        .map_err(|_| "请求头不是合法 UTF-8".to_owned())?
        .to_owned();
    let 体起 = 头尾 + 4;
    let 余料 = 缓冲.get(体起..).unwrap_or(&[]).to_vec();

    let mut 行迭代器 = 头部.split("\r\n");
    let 首行 = 行迭代器.next().unwrap_or("");
    let 部件: Vec<&str> = 首行.split(' ').filter(|号段| !号段.is_empty()).collect();
    if 部件.len() != 3 {
        return Err("请求行必须是「方法 目标 版本」三段".to_owned());
    }
    let (请求方法, 请求目标) = (部件[0].to_owned(), 部件[1].to_owned());

    let mut 内容长度 = 0usize;
    // 边界判定要的三个头（审计发现2）：**原样留值**，判定全在 `报文校验.rs`。
    let mut 主机 = String::new();
    let mut 来源站点 = String::new();
    let mut 内容类型 = String::new();
    for 文本行 in 行迭代器 {
        let Some((名字, 值)) = 文本行.split_once(':') else {
            continue;
        };
        let 名称 = 名字.trim().to_ascii_lowercase();
        let 待处理值 = 值.trim();
        match 名称.as_str() {
            "host" => 主机 = 待处理值.to_owned(),
            "origin" => 来源站点 = 待处理值.to_owned(),
            "content-type" => 内容类型 = 待处理值.to_owned(),
            _ => {}
        }
        if 名称 == "content-length" {
            内容长度 = 待处理值
                .parse::<usize>()
                .map_err(|_| "Content-Length 不是非负整数".to_owned())?;
        }
        if 名称 == "transfer-encoding" && !待处理值.eq_ignore_ascii_case("identity") {
            // 分块传输要做流式状态机 = 连接管理，本面明确不做（文件头）。
            return Err("本面不支持 Transfer-Encoding：请用 Content-Length".to_owned());
        }
    }
    if 内容长度 > 体上限 {
        return Err(format!("请求体超过 {体上限} 字节"));
    }

    let mut 体字节 = 余料;
    // 余料可能已经多于 Content-Length（pipelining）：多的部分**丢弃**，本面不做流水线。
    体字节.truncate(内容长度);
    while 体字节.len() < 内容长度 {
        let 还差 = (内容长度 - 体字节.len()).min(读缓冲.len());
        let 读到 = 输出流
            .read(&mut 读缓冲[..还差])
            .map_err(|错误| format!("读请求体失败：{错误}"))?;
        if 读到 == 0 {
            return Err("请求体没读完连接就断了".to_owned());
        }
        体字节.extend_from_slice(&读缓冲[..读到]);
    }
    let 请求体 = String::from_utf8(体字节).map_err(|_| "请求体不是合法 UTF-8".to_owned())?;
    Ok(报文 { 请求方法, 请求目标, 报文体: 请求体, 主机, 来源站点, 内容类型 })
}

/// 找 `\r\n\r\n` 的起始偏移（请求头与体的分界）。
fn 找头体分界(缓冲: &[u8]) -> Option<usize> {
    缓冲
        .windows(4)
        .position(|字节窗口| 字节窗口 == b"\r\n\r\n")
}

/// 写一条应答。**恒带 `Connection: close`**（不做连接管理）。
///
/// 内容类型**随应答走**（`造应答.内容类型`）：§三 的四个端点是 JSON，§五 的静态托管是
/// `text/html` / `text/css` / `text/javascript` —— 在这里假定 JSON 就会让前端整页挂掉
/// （浏览器按 JSON 解 HTML 只得到一个下载或一段乱码）。
pub(crate) fn 写响应(输出流: &mut TcpStream, 造应答: &造应答) -> std::io::Result<()> {
    let 头部 = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        造应答.状态,
        原因短语(造应答.状态),
        造应答.内容类型,
        造应答.报文体.len()
    );
    输出流.write_all(头部.as_bytes())?;
    输出流.write_all(&造应答.报文体)?;
    输出流.flush()
}

fn 原因短语(状态: u16) -> &'static str {
    match 状态 {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        _ => "Unknown",
    }
}
