//! PDFKit 原生执行体调用；执行体与网关同目录，文件名 `PDF处理`。
use std::io::Read;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use crate::错误码;

const 等待上限毫秒: u64 = 5_000;
const 输出上限字节: usize = 88_000_000;

fn 引擎路径() -> Result<std::path::PathBuf, u32> {
    if !cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        return Err(错误码::运行平台不支持);
    }
    let 路径 = std::env::current_exe()
        .map_err(|_| 错误码::运行平台不支持)?
        .parent()
        .ok_or(错误码::运行平台不支持)?
        .join("PDF处理");
    if !路径.is_absolute() || !路径.is_file() {
        return Err(错误码::运行平台不支持);
    }
    Ok(路径)
}

fn 校验路径(文本值: &str) -> Result<&str, u32> {
    if 文本值.is_empty() || !文本值.starts_with('/') || 文本值.contains('\0') || 文本值.len() > 4096 {
        return Err(错误码::参数不合法);
    }
    if !std::path::Path::new(文本值).is_file() {
        return Err(错误码::文件不可读);
    }
    Ok(文本值)
}

/// 调原生执行体：返回 (退出码, 标准输出字节)
pub(crate) fn 执行(子命令: &str, 参数表: &[&str]) -> Result<String, u32> {
    let 执行体路径 = 引擎路径()?;
    let mut 命令 = Command::new(执行体路径);
    命令.arg(子命令).args(参数表).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::null());
    let mut 子进程 = 命令.spawn().map_err(|_| 错误码::运行平台不支持)?;
    let 管道 = 子进程.stdout.take().ok_or(错误码::处理失败)?;
    let 读取线程 = std::thread::spawn(move || {
        let mut 缓冲 = Vec::new();
        let 状态 = 管道.take(输出上限字节 as u64 + 1).read_to_end(&mut 缓冲);
        (状态, 缓冲)
    });
    let 开始 = Instant::now();
    let 终态 = loop {
        match 子进程.try_wait() {
            Ok(Some(状态)) => break Ok(状态),
            Ok(None) => {}
            Err(_) => break Err(错误码::处理失败),
        }
        if 开始.elapsed() > Duration::from_millis(等待上限毫秒) {
            break Err(错误码::处理超时);
        }
        std::thread::sleep(Duration::from_millis(5));
    };
    if 终态.is_err() {
        let _ = 子进程.kill();
        let _ = 子进程.wait();
    }
    let (读状态, 输出) = 读取线程.join().map_err(|_| 错误码::处理失败)?;
    let 状态 = 终态?;
    if 读状态.is_err() {
        return Err(错误码::处理失败);
    }
    if 输出.len() > 输出上限字节 {
        return Err(错误码::资源超限);
    }
    if !状态.success() {
        return Err(match 状态.code() {
            Some(2) => 错误码::参数不合法,
            Some(3) => 错误码::文件不可读,
            Some(4) => 错误码::资源超限,
            Some(5) => 错误码::页序号越界,
            Some(7) => 错误码::运行平台不支持,
            _ => 错误码::处理失败,
        });
    }
    String::from_utf8(输出).map_err(|_| 错误码::处理失败)
}

pub(crate) fn 检测加密页数(文件路径: &str) -> Result<String, u32> {
    执行("页数", &[校验路径(文件路径)?])
}

pub(crate) fn 渲染页面(文件路径: &str, 页序号: &str, 输出路径: &str, 倍率: &str) -> Result<String, u32> {
    let 源路径 = 校验路径(文件路径)?;
    let 页文本 = 页序号.trim();
    if 页文本.is_empty() || 页文本.parse::<u32>().is_err() {
        return Err(错误码::参数不合法);
    }
    校验路径输出(输出路径)?;
    let 倍率文本 = 倍率.trim();
    if !倍率文本.is_empty() && 倍率文本.parse::<f64>().is_err() {
        return Err(错误码::参数不合法);
    }
    let 倍率值 = if 倍率文本.is_empty() { "2.0" } else { 倍率文本 };
    执行("渲染", &[源路径, 页文本, 输出路径, 倍率值])
}

fn 校验路径输出(文本值: &str) -> Result<(), u32> {
    if 文本值.is_empty() || !文本值.starts_with('/') || 文本值.contains('\0') || 文本值.len() > 4096 {
        return Err(错误码::参数不合法);
    }
    if let Some(父目录) = std::path::Path::new(文本值).parent() {
        std::fs::create_dir_all(父目录).map_err(|_| 错误码::文件不可读)?;
    }
    Ok(())
}

pub(crate) fn 提取内嵌图(文件路径: &str, 页序号: &str) -> Result<String, u32> {
    let 源路径 = 校验路径(文件路径)?;
    let 页文本 = 页序号.trim();
    if 页文本.is_empty() || 页文本.parse::<u32>().is_err() {
        return Err(错误码::参数不合法);
    }
    执行("提取", &[源路径, 页文本])
}

pub(crate) fn 校验文件(文件路径: &str) -> Result<String, u32> {
    执行("校验", &[校验路径(文件路径)?])
}
