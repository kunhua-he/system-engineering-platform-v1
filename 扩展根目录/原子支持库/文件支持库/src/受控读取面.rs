use crate::错误码;
use std::io::Read;
use std::path::{Component, Path};
use v1_contract::{数据槽, 类型标签};

fn 映射受控读错(读取错误: std::io::Error) -> u32 {
    match 读取错误.kind() {
        std::io::ErrorKind::NotFound => 错误码::文件不存在,
        _ => 错误码::读取被拒,
    }
}

/// 持目录描述符逐层打开；拒上跳、绝对子路径与全部符号链接。
/// 根目录由调用方显式授权，本能力不替代项目用户权限校验。
#[cfg(unix)]
fn 打开受控文件(受控根目录: &str, 相对路径: &str) -> Result<std::fs::File, u32> {
    use std::ffi::CString;
    use std::os::fd::{AsRawFd, FromRawFd};
    use std::os::unix::fs::OpenOptionsExt;
    unsafe extern "C" {
        // Rust 外部变参声明强制 ASCII 名，调用方立即绑定中文名。
        fn openat(目录描述符: i32, 路径指针: *const std::ffi::c_char, 打开标志: i32, ...) -> i32;
    }
    #[cfg(target_os = "macos")]
    const 禁止链接标志: i32 = 0x100;
    #[cfg(target_os = "macos")]
    const 目录打开标志: i32 = 0x100000;
    #[cfg(target_os = "macos")]
    const 关闭继承标志: i32 = 0x1000000;
    #[cfg(target_os = "macos")]
    const 非阻塞标志: i32 = 4;
    #[cfg(not(target_os = "macos"))]
    const 禁止链接标志: i32 = 0x20000;
    #[cfg(not(target_os = "macos"))]
    const 目录打开标志: i32 = 0x10000;
    #[cfg(not(target_os = "macos"))]
    const 关闭继承标志: i32 = 0x80000;
    #[cfg(not(target_os = "macos"))]
    const 非阻塞标志: i32 = 0x800;
    let 外部打开相对 = openat;
    let 根路径 = Path::new(受控根目录);
    if !根路径.is_absolute() { return Err(错误码::路径不是绝对路径); }
    if 受控根目录.len() > 4096 || 相对路径.len() > 4096 || 相对路径.contains('\0') {
        return Err(错误码::参数不合法);
    }
    let 路径分量表 = Path::new(相对路径).components().collect::<Vec<_>>();
    if 路径分量表.is_empty() || 路径分量表.iter().any(|路径分量| !matches!(路径分量, Component::Normal(_))) {
        return Err(错误码::参数不合法);
    }
    let mut 目录文件 = std::fs::OpenOptions::new().read(true)
        .custom_flags(禁止链接标志 | 目录打开标志 | 关闭继承标志).open(根路径).map_err(映射受控读错)?;
    for (分量位置, 路径分量) in 路径分量表.iter().enumerate() {
        let 路径字节串 = CString::new(路径分量.as_os_str().as_encoded_bytes()).map_err(|_| 错误码::参数不合法)?;
        let 是末段 = 分量位置 + 1 == 路径分量表.len();
        let 打开标志 = 禁止链接标志 | 关闭继承标志 | 非阻塞标志 | if 是末段 { 0 } else { 目录打开标志 };
        let 文件描述符 = unsafe { 外部打开相对(目录文件.as_raw_fd(), 路径字节串.as_ptr(), 打开标志) };
        if 文件描述符 < 0 { return Err(映射受控读错(std::io::Error::last_os_error())); }
        let 当前文件 = unsafe { std::fs::File::from_raw_fd(文件描述符) };
        if 是末段 {
            if !当前文件.metadata().map_err(映射受控读错)?.is_file() { return Err(错误码::不是普通文件); }
            return Ok(当前文件);
        }
        目录文件 = 当前文件;
    }
    Err(错误码::参数不合法)
}

#[cfg(not(unix))]
fn 打开受控文件(_: &str, _: &str) -> Result<std::fs::File, u32> { Err(错误码::读取被拒) }

/// 头部是截取语义，完整文件再大也只取所需头部。
pub(crate) fn 读取受控头部(受控根目录: &str, 相对路径: &str, 字节数: i64) -> Result<Vec<u8>, u32> {
    if !(0..=1048576).contains(&字节数) { return Err(错误码::资源受限); }
    let 已开文件 = 打开受控文件(受控根目录, 相对路径)?;
    let mut 返回字节 = Vec::new();
    已开文件.take(字节数 as u64).read_to_end(&mut 返回字节).map_err(映射受控读错)?;
    Ok(返回字节)
}

/// 整件读取不得以截断成功替代超限失败；读同一描述符，最多多探一个字节。
pub(crate) fn 读取受控全件(受控根目录: &str, 相对路径: &str, 最大字节数: i64) -> Result<Vec<u8>, u32> {
    if !(0..=52428800).contains(&最大字节数) { return Err(错误码::资源受限); }
    let 已开文件 = 打开受控文件(受控根目录, 相对路径)?;
    let 读取上界 = 最大字节数 as u64;
    if 已开文件.metadata().map_err(映射受控读错)?.len() > 读取上界 { return Err(错误码::资源受限); }
    let mut 返回字节 = Vec::new();
    已开文件.take(读取上界 + 1).read_to_end(&mut 返回字节).map_err(映射受控读错)?;
    if 返回字节.len() as u64 > 读取上界 { return Err(错误码::资源受限); }
    Ok(返回字节)
}

unsafe fn 取受控文本(参数槽: &数据槽) -> Result<&str, u32> {
    if 参数槽.类型标签.取号值() != 4 || !参数槽.是否引用() || 参数槽.槽字节长度 > 4096
        || (参数槽.槽值 == 0 && 参数槽.槽字节长度 != 0) { return Err(错误码::参数不合法); }
    let 文本字节 = if 参数槽.槽字节长度 == 0 { &[][..] } else {
        unsafe { std::slice::from_raw_parts(参数槽.槽值 as *const u8, 参数槽.槽字节长度 as usize) }
    };
    std::str::from_utf8(文本字节).map_err(|_| 错误码::参数不合法)
}

unsafe fn 执行受控读取(参数个数: u32, 参数表: *const 数据槽, 整件读取: bool) -> Result<数据槽,u32> {
    if 参数个数 != 3 || 参数表.is_null() { return Err(错误码::参数不合法); }
    let 参数槽表 = unsafe { std::slice::from_raw_parts(参数表,3) };
    let 受控根目录 = unsafe { 取受控文本(&参数槽表[0])? };
    let 相对路径 = unsafe { 取受控文本(&参数槽表[1])? };
    if 参数槽表[2].类型标签.取号值() != 1 || 参数槽表[2].是否引用() { return Err(错误码::参数不合法); }
    let 头部字节 = if 整件读取 {
        读取受控全件(受控根目录, 相对路径, 参数槽表[2].槽值 as i64)?
    } else {
        读取受控头部(受控根目录, 相对路径, 参数槽表[2].槽值 as i64)?
    };
    let 返回长度 = 头部字节.len() as u64;
    let 返回指针 = Box::into_raw(头部字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(类型标签::构造(5),返回指针 as u64,返回长度,true))
}

pub(crate) unsafe extern "C-unwind" fn 受控头部入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 返回槽.is_null() { return; }
    unsafe { *返回槽 = 执行受控读取(参数个数,参数表,false).unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX),失败码 as u64,4)); }
}


pub(crate) unsafe extern "C-unwind" fn 受控整读入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 返回槽.is_null() { return; }
    unsafe { *返回槽 = 执行受控读取(参数个数,参数表,true).unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX),失败码 as u64,4)); }
}
