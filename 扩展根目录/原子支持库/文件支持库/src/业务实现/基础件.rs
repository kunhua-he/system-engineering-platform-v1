//! 各组共用的基础件：路径校验收口、读错映射、有界读。

use std::io::Read;

use crate::编号与码面::错误码;


pub(super) fn 查路径(参数字节: &[u8]) -> Result<&std::path::Path, u32> {
    let 路径文本 = std::str::from_utf8(参数字节).map_err(|_| 错误码::参数不合法)?;
    let 文件路径 = std::path::Path::new(路径文本);
    if !文件路径.is_absolute() {
        return Err(错误码::路径不是绝对路径);
    }
    if 路径文本.len() > 4096 || 路径文本.contains('\0') {
        return Err(错误码::参数不合法);
    }
    Ok(文件路径)
}

pub(super) fn 映射读错(失败: std::io::Error) -> u32 {
    match 失败.kind() {
        std::io::ErrorKind::NotFound => 错误码::文件不存在,
        _ => 错误码::读取被拒,
    }
}

pub(super) fn 读有界文件(文件路径: &std::path::Path) -> Result<Vec<u8>, u32> {
    let mut 打开选项 = std::fs::OpenOptions::new();
    打开选项.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        #[cfg(target_os = "macos")]
        打开选项.custom_flags(4);
        #[cfg(target_os = "linux")]
        打开选项.custom_flags(2048);
    }
    let 读取文件 = 打开选项.open(文件路径).map_err(映射读错)?;
    let 文件属性 = 读取文件.metadata().map_err(映射读错)?;
    if !文件属性.is_file() {
        return Err(错误码::不是普通文件);
    }
    if 文件属性.len() > 65536 {
        return Err(错误码::资源受限);
    }
    let mut 文件字节 = Vec::new();
    读取文件
        .take(65537)
        .read_to_end(&mut 文件字节)
        .map_err(映射读错)?;
    if 文件字节.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok(文件字节)
}

