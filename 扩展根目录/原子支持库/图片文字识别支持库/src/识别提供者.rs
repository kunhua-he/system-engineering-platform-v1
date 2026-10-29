//! 系统Vision独立执行体；部署时预编译，不从技能加载实现。
use crate::错误码;
use std::io::Read;
use std::process::{Command,Stdio};
use std::time::{Duration,Instant};
pub fn 识别图片文字(图片路径:&str)->Result<String,u32>{
    if !std::path::Path::new(图片路径).is_absolute() || 图片路径.as_bytes().contains(&0){return Err(错误码::参数不合法);}
    let mut 图片文件=std::fs::File::open(图片路径).map_err(|_|错误码::图片不可读)?;
    let 图片属性=图片文件.metadata().map_err(|_|错误码::图片不可读)?;
    if !图片属性.is_file(){return Err(错误码::图片不可读);}
    if 图片属性.len()>20*1024*1024{return Err(错误码::图片资源超限);}
    let mut 文件头部=[0u8;12];
    let 头部长度=图片文件.read(&mut 文件头部).map_err(|_|错误码::图片不可读)?;
    if !(头部长度>=8 && 文件头部[..8]==[137,80,78,71,13,10,26,10] || 头部长度>=3 && 文件头部[..3]==[255,216,255]){return Err(错误码::图片格式不支持);}
    if !cfg!(all(target_os="macos",target_arch="aarch64")){return Err(错误码::运行平台不支持);}
    let 引擎路径=match std::env::var_os("V1_OCR_ENGINE"){
        Some(配置路径)=>std::path::PathBuf::from(配置路径),
        None=>std::env::current_exe().map_err(|_|错误码::运行平台不支持)?.parent().ok_or(错误码::运行平台不支持)?.join("图片文字识别"),
    };
    if !引擎路径.is_absolute() || !引擎路径.is_file(){return Err(错误码::运行平台不支持);}
    let mut 子进程=Command::new(引擎路径).arg(图片路径).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::null()).spawn().map_err(|_|错误码::运行平台不支持)?;
    let 输出管道=子进程.stdout.take().ok_or(错误码::文字识别失败)?;
    let 输出线程=std::thread::spawn(move||{let mut 输出字节=Vec::new();let 读取状态=输出管道.take(65537).read_to_end(&mut 输出字节);(读取状态,输出字节)});
    let 开始时刻=Instant::now();
    let 进程状态=loop {
        match 子进程.try_wait(){Ok(Some(终态))=>break Ok(终态),Ok(None)=>{},Err(_)=>break Err(错误码::文字识别失败)}
        if 开始时刻.elapsed()>Duration::from_millis(5000){break Err(错误码::识别超时);}
        std::thread::sleep(Duration::from_millis(5));
    };
    if 进程状态.is_err(){let _=子进程.kill();let _=子进程.wait();}
    let (读取状态,输出字节)=输出线程.join().map_err(|_|错误码::文字识别失败)?;
    let 进程状态=进程状态?;
    if 读取状态.is_err(){return Err(错误码::文字识别失败);}
    if 输出字节.len()>65536{return Err(错误码::图片资源超限);}
    if !进程状态.success(){return Err(match 进程状态.code(){Some(3)=>错误码::图片格式不支持,Some(4)=>错误码::图片资源超限,_=>错误码::文字识别失败});}
    String::from_utf8(输出字节).map_err(|_|错误码::文字识别失败)
}
#[cfg(test)]
mod 识别样本{
    #[test] fn 拒绝相对路径(){assert_eq!(super::识别图片文字("相对图片.png"),Err(crate::错误码::参数不合法));}
    #[test] fn 拒绝不存在图片(){assert_eq!(super::识别图片文字("/不存在的OCR图片.png"),Err(crate::错误码::图片不可读));}
}
