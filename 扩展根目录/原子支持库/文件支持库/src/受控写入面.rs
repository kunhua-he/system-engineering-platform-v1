//! 同目录原子替换：失败前不截断原件，不跟随链接，不自动重放。
use crate::错误码;
use v1_contract::{数据槽, 类型标签};
#[cfg(unix)]
pub(crate) fn 原子写入文本(受控根目录: &str, 相对路径: &str, 文本内容: &str) -> Result<i64, u32> {
    use crate::受控路径面::{打开受控父目录, 相对打开, 相对替换, 相对删除, 独占写入标志};
    use std::io::{ErrorKind, Write};
    use std::sync::atomic::{AtomicU64, Ordering};
    static 暂存序号: AtomicU64 = AtomicU64::new(0);
    if 文本内容.len() > 131072 { return Err(错误码::资源受限); }
    let (父目录, 目标名称) = 打开受控父目录(受控根目录, 相对路径, true)?;
    let 目标权限 = match 相对打开(&父目录, &目标名称, 0) {
        Ok(现有文件) => {
            let 元信息 = 现有文件.metadata().map_err(|_| 错误码::写入失败)?;
            if !元信息.is_file() { return Err(错误码::不是普通文件); }
            Some(元信息.permissions())
        }
        Err(错误) if 错误.kind() == ErrorKind::NotFound => None,
        Err(_) => return Err(错误码::读取被拒),
    };
    for _ in 0..16 {
        let 暂存名称 = std::ffi::CString::new(format!(".原子写入-{}-{}", std::process::id(), 暂存序号.fetch_add(1, Ordering::Relaxed))).map_err(|_| 错误码::参数不合法)?;
        let mut 暂存文件 = match 相对打开(&父目录, &暂存名称, 独占写入标志) {
            Ok(新开文件) => 新开文件,
            Err(错误) if 错误.kind() == ErrorKind::AlreadyExists => continue,
            Err(_) => return Err(错误码::写入失败),
        };
        let 写入结果 = (|| {
            暂存文件.write_all(文本内容.as_bytes()).map_err(|_| 错误码::写入失败)?;
            if let Some(权限) = &目标权限 { 暂存文件.set_permissions(权限.clone()).map_err(|_| 错误码::写入失败)?; }
            暂存文件.sync_all().map_err(|_| 错误码::写入失败)?;
            相对替换(&父目录, &暂存名称, &目标名称).map_err(|_| 错误码::写入失败)?;
            Ok(文本内容.len() as i64)
        })();
        if 写入结果.is_err() { 相对删除(&父目录, &暂存名称); }
        return 写入结果;
    }
    Err(错误码::写入失败)
}
#[cfg(not(unix))]
pub(crate) fn 原子写入文本(_: &str, _: &str, _: &str) -> Result<i64, u32> { Err(错误码::写入失败) }

unsafe fn 执行写入(参数个数: u32, 参数表: *const 数据槽) -> Result<数据槽, u32> {
    if 参数个数 != 3 || 参数表.is_null() { return Err(错误码::参数不合法); }
    let 参数槽表 = unsafe { std::slice::from_raw_parts(参数表, 3) };
    let 根目录 = unsafe { crate::受控读取面::取受控文本(&参数槽表[0])? };
    let 相对路径 = unsafe { crate::受控读取面::取受控文本(&参数槽表[1])? };
    let 内容槽 = &参数槽表[2];
    if 内容槽.类型标签.取号值() != 4 || !内容槽.是否引用()
        || (内容槽.槽值 == 0 && 内容槽.槽字节长度 != 0) { return Err(错误码::参数不合法); }
    if 内容槽.槽字节长度 > 131072 { return Err(错误码::资源受限); }
    let 内容字节 = if 内容槽.槽字节长度 == 0 { &[][..] } else {
        unsafe { std::slice::from_raw_parts(内容槽.槽值 as *const u8, 内容槽.槽字节长度 as usize) }
    };
    let 文本内容 = std::str::from_utf8(内容字节).map_err(|_| 错误码::内容不合法)?;
    let 写入字节数 = 原子写入文本(根目录, 相对路径, 文本内容)?;
    Ok(数据槽::内联槽(类型标签::构造(1), 写入字节数 as u64, 8))
}
pub(crate) unsafe extern "C-unwind" fn 原子写入入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 返回槽.is_null() { return; }
    unsafe { *返回槽 = 执行写入(参数个数, 参数表).unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)); }
}
