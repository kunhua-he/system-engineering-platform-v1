use crate::错误码;
use std::io::Read;
use v1_contract::{数据槽, 类型标签};

fn 映射受控读错(读取错误: std::io::Error) -> u32 {
    match 读取错误.kind() {
        std::io::ErrorKind::NotFound => 错误码::文件不存在,
        _ => 错误码::读取被拒,
    }
}

/// 与写入共用父目录描述符边界，末段读取只收普通文件。
#[cfg(unix)]
fn 打开受控文件(受控根目录: &str, 相对路径: &str) -> Result<std::fs::File, u32> {
    let (父目录, 文件名称) = crate::受控路径面::打开受控父目录(受控根目录, 相对路径, false)?;
    let 已开文件 = crate::受控路径面::相对打开(&父目录, &文件名称, 0).map_err(映射受控读错)?;
    if !已开文件.metadata().map_err(映射受控读错)?.is_file() { return Err(错误码::不是普通文件); }
    Ok(已开文件)
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

pub(crate) unsafe fn 取受控文本(参数槽: &数据槽) -> Result<&str, u32> {
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
