//! 外部转换器：LibreOffice（办公文件）和 textutil（文本类文件）。
//!
//! 只做「探测 + 跑子进程 + 收产物」：独占槽位用进程内锁，超时到点杀进程，
//! 产物按字节上限验收；不安装、不改系统配置、不留常驻进程。

use crate::编号与码面::错误码;
use std::path::{Path, PathBuf};
// 包2：外部格式转换（LibreOffice / textutil）在扩展内以子进程完成。
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

static 转换锁: Mutex<()> = Mutex::new(());
const 输出字节上限: u64 = 67_108_864;
const 默认超时秒: u64 = 5;

fn 找转换器(候选表: &[&str]) -> Option<PathBuf> {
    for 候选路径 in 候选表 {
        let 路径 = Path::new(候选路径);
        if 路径.is_file() {
            return Some(路径.to_path_buf());
        }
    }
    None
}

fn 办公转换器() -> Option<PathBuf> {
    if let Ok(指定) = std::env::var("LIBREOFFICE_BIN")
        && !指定.trim().is_empty()
        && Path::new(指定.trim()).is_file()
    {
        return Some(PathBuf::from(指定.trim()));
    }
    找转换器(&[
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/opt/homebrew/bin/soffice",
        "/usr/local/bin/soffice",
        "/usr/bin/soffice",
    ])
}

fn 文本转换器() -> Option<PathBuf> {
    找转换器(&["/usr/bin/textutil", "/usr/local/bin/textutil"])
}

fn 版本首行(程序: &Path) -> String {
    let 命令行输出 = Command::new(程序).arg("--version").stdout(Stdio::piped()).stderr(Stdio::null()).output();
    match 命令行输出 {
        Ok(命令行输出值) => {
             let 全文 = String::from_utf8_lossy(&命令行输出值.stdout).to_string();
            全文.lines().next().unwrap_or("").trim().to_string()
        }
        Err(_) => String::new(),
    }
}

pub(crate) fn 检查提供者实现(提供者名: &str) -> Result<String, u32> {
    let 目标 = 提供者名.trim().to_ascii_lowercase();
    // 平台不支持空串实参（空串槽值 0 被判非引用），全部探测统一用 all。
    if !目标.is_empty() && 目标 != "all" && 目标 != "textutil" && 目标 != "libreoffice" {
        return Err(错误码::参数不合法);
    }
    let 要文本 = 目标.is_empty() || 目标 == "all" || 目标 == "textutil";
    let 要办公 = 目标.is_empty() || 目标 == "all" || 目标 == "libreoffice";
    let mut 片段表: Vec<String> = Vec::new();
    if 要文本 {
        let 状态 = match 文本转换器() {
            Some(程序) => {
                let 版本 = 版本首行(&程序);
                if 版本.is_empty() { format!("可用（{}）", 程序.display()) } else { 版本 }
            }
            None => String::from("不可用"),
        };
        片段表.push(format!("\"textutil\":\"{}\"", 转义JSON字符串(&状态)));
    }
    if 要办公 {
        let 状态 = match 办公转换器() {
            Some(程序) => {
                let 版本 = 版本首行(&程序);
                if 版本.is_empty() { format!("可用（{}）", 程序.display()) } else { 版本 }
            }
            None => String::from("不可用"),
        };
        片段表.push(format!("\"libreoffice\":\"{}\"", 转义JSON字符串(&状态)));
    }
    Ok(format!("{{{}}}", 片段表.join(",")))
}

fn 解析超时(超时秒: &str) -> Result<u64, u32> {
    let 超时文本 = 超时秒.trim();
    // 空串平台传不进来，契约用 0 表示「取默认」；两者都落到默认值。
    if 超时文本.is_empty() || 超时文本 == "0" {
        return Ok(默认超时秒);
    }
    let 超时值 = 超时文本.parse::<u64>().map_err(|_| 错误码::参数不合法)?;
    if !(1..=默认超时秒).contains(&超时值) {
        return Err(错误码::参数不合法);
    }
    Ok(超时值)
}

fn 校验路径(原文本: &str) -> Result<PathBuf, u32> {
    if 原文本.contains('\0') || 原文本.len() > 4096 {
        return Err(错误码::参数不合法);
    }
    let 目标路径 = PathBuf::from(原文本);
    if !目标路径.is_absolute() {
        return Err(错误码::参数不合法);
    }
    Ok(目标路径)
}

fn 校验格式(目标格式: &str) -> Result<String, u32> {
    let 格式名 = 目标格式.trim().trim_start_matches('.').to_ascii_lowercase();
    if 格式名.is_empty()
        || 格式名.len() > 16
        || !格式名.chars().all(|单字| 单字.is_ascii_alphanumeric())
    {
        return Err(错误码::参数不合法);
    }
    Ok(格式名)
}

fn 等待子进程(子进程: &mut std::process::Child, 超时值: u64) -> Result<std::process::ExitStatus, u32> {
    let 开始时刻 = Instant::now();
    loop {
        match 子进程.try_wait() {
            Ok(Some(退出状态)) => return Ok(退出状态),
            Ok(None) => {}
            Err(_) => return Err(错误码::转换失败),
        }
        if 开始时刻.elapsed() >= Duration::from_secs(超时值) {
            let _ = 子进程.kill();
            let _ = 子进程.wait();
            return Err(错误码::转换失败);
        }
        std::thread::sleep(Duration::from_millis(50));
    }
}

fn 收产物(目标文件: &Path, 格式名: &str) -> Result<String, u32> {
    let 元信息 = std::fs::metadata(目标文件).map_err(|_| 错误码::转换失败)?;
    if !元信息.is_file() {
        return Err(错误码::转换失败);
    }
    let 字节数 = 元信息.len();
    if 字节数 == 0 {
        return Err(错误码::转换失败);
    }
    if 字节数 > 输出字节上限 {
        return Err(错误码::内容不合法);
    }
    Ok(format!(
        "{{\"输出路径\":\"{}\",\"字节数\":{},\"格式\":\"{}\"}}",
        转义JSON字符串(&目标文件.to_string_lossy()),
        字节数,
        转义JSON字符串(格式名)
    ))
}

fn 跑转换(程序: &Path, 参数表: &[String], 超时值: u64) -> Result<(), u32> {
    let mut 命令对象 = Command::new(程序);
    for 单参 in 参数表 {
        命令对象.arg(单参);
    }
    let mut 子进程 = 命令对象
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| 错误码::转换器不可用)?;
    let 退出状态 = 等待子进程(&mut 子进程, 超时值)?;
    if 退出状态.success() {
        Ok(())
    } else {
        Err(错误码::转换失败)
    }
}

pub(crate) fn 转换办公实现(
    输入路径: &str,
    目标格式: &str,
    超时秒: &str,
    输出目录: &str,
) -> Result<String, u32> {
    let 源路径 = 校验路径(输入路径)?;
    if !源路径.is_file() {
        return Err(错误码::参数不合法);
    }
    let 格式名 = 校验格式(目标格式)?;
    let 输出目录路径 = 校验路径(输出目录)?;
    let 超时值 = 解析超时(超时秒)?;
    let 程序 = 办公转换器().ok_or(错误码::转换器不可用)?;
    std::fs::create_dir_all(&输出目录路径).map_err(|_| 错误码::写出失败)?;
    let _转换闸 = 转换锁.lock().map_err(|_| 错误码::转换失败)?;
    static 转换序号: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    let 用户配置目录 = format!(
        "-env:UserInstallation=file:///tmp/v1-soffice-{}-{}",
        std::process::id(),
        转换序号.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    );
    let 参数表 = vec![
        String::from("--headless"),
        String::from("--norestore"),
        String::from("--invisible"),
        用户配置目录,
        String::from("--convert-to"),
        格式名.clone(),
        String::from("--outdir"),
        输出目录路径.to_string_lossy().to_string(),
        源路径.to_string_lossy().to_string(),
    ];
    跑转换(&程序, &参数表, 超时值)?;
    let 输出主名 = 源路径
        .file_stem()
        .map(|主名| 主名.to_string_lossy().to_string())
        .ok_or(错误码::参数不合法)?;
    let 目标文件 = 输出目录路径.join(format!("{输出主名}.{格式名}"));
    收产物(&目标文件, &格式名)
}

pub(crate) fn 转换文本实现(
    输入路径: &str,
    目标格式: &str,
    超时秒: &str,
    输出目录: &str,
) -> Result<String, u32> {
    let 源路径 = 校验路径(输入路径)?;
    if !源路径.is_file() {
        return Err(错误码::参数不合法);
    }
    let 格式名 = 校验格式(目标格式)?;
    let 输出目录路径 = 校验路径(输出目录)?;
    let 超时值 = 解析超时(超时秒)?;
    let 程序 = 文本转换器().ok_or(错误码::转换器不可用)?;
    std::fs::create_dir_all(&输出目录路径).map_err(|_| 错误码::写出失败)?;
    let 输出主名 = 源路径
        .file_stem()
        .map(|主名| 主名.to_string_lossy().to_string())
        .ok_or(错误码::参数不合法)?;
    let 目标文件 = 输出目录路径.join(format!("{输出主名}.{格式名}"));
    let 参数表 = vec![
        String::from("-convert"),
        格式名.clone(),
        String::from("-output"),
        目标文件.to_string_lossy().to_string(),
        源路径.to_string_lossy().to_string(),
    ];
    跑转换(&程序, &参数表, 超时值)?;
    收产物(&目标文件, &格式名)
}

fn 转义JSON字符串(原文本: &str) -> String {
    原文本.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', "\\n")
}
#[cfg(test)]
mod 格式转换验证样本 {
    use super::*;

    #[test]
    fn 超时零取默认() {
        assert_eq!(解析超时("0").unwrap(), 默认超时秒);
        assert_eq!(解析超时("4").unwrap(), 4);
        assert!(解析超时("6").is_err());
        assert_eq!(解析超时("5").unwrap(), 5);
    }

    #[test]
    fn 检查提供者含两键() {
        let 结果文本 = 检查提供者实现("").unwrap();
        assert!(结果文本.contains("\"textutil\""), "{结果文本}");
        assert!(结果文本.contains("\"libreoffice\""), "{结果文本}");
        let 单查 = 检查提供者实现("textutil").unwrap();
        assert!(单查.contains("\"textutil\"") && !单查.contains("libreoffice"));
    }

    #[test]
    fn 检查提供者非法名被拒() {
        assert_eq!(检查提供者实现("pandoc").unwrap_err(), 错误码::参数不合法);
    }

    #[test]
    fn 转换相对路径被拒() {
        assert_eq!(转换文本实现("相对/样本.txt", "txt", "", "/tmp").unwrap_err(), 错误码::参数不合法);
        assert_eq!(转换办公实现("相对/样本.docx", "pdf", "", "/tmp").unwrap_err(), 错误码::参数不合法);
    }

    #[test]
    fn 转换非法格式被拒() {
        let 样本根 = std::env::temp_dir().join(format!("v1转换样本-格式-{}", std::process::id()));
        std::fs::create_dir_all(&样本根).unwrap();
        let 源文件 = 样本根.join("样本.txt");
        std::fs::write(&源文件, "内容").unwrap();
        let 源文本 = 源文件.to_string_lossy().to_string();
        assert_eq!(转换文本实现(&源文本, "", "", &样本根.to_string_lossy()).unwrap_err(), 错误码::参数不合法);
        assert_eq!(转换文本实现(&源文本, "p df", "", &样本根.to_string_lossy()).unwrap_err(), 错误码::参数不合法);
        let _ = std::fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 转换超时越界被拒() {
        let 样本根 = std::env::temp_dir().join(format!("v1转换样本-超时-{}", std::process::id()));
        std::fs::create_dir_all(&样本根).unwrap();
        let 源文件 = 样本根.join("样本.txt");
        std::fs::write(&源文件, "内容").unwrap();
        let 源文本 = 源文件.to_string_lossy().to_string();
        let 目录文本 = 样本根.to_string_lossy().to_string();
        assert_eq!(转换文本实现(&源文本, "txt", "6", &目录文本).unwrap_err(), 错误码::参数不合法);
        assert_eq!(转换文本实现(&源文本, "txt", "601", &目录文本).unwrap_err(), 错误码::参数不合法);
        assert_eq!(转换文本实现(&源文本, "txt", "很久", &目录文本).unwrap_err(), 错误码::参数不合法);
        let _ = std::fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 转换源不存在被拒() {
        let 样本根 = std::env::temp_dir().join(format!("v1转换样本-缺源-{}", std::process::id()));
        std::fs::create_dir_all(&样本根).unwrap();
        let 目录文本 = 样本根.to_string_lossy().to_string();
        let 缺源文本 = 样本根.join("没有这个.txt").to_string_lossy().to_string();
        assert_eq!(转换文本实现(&缺源文本, "txt", "", &目录文本).unwrap_err(), 错误码::参数不合法);
        let _ = std::fs::remove_dir_all(&样本根);
    }
}

