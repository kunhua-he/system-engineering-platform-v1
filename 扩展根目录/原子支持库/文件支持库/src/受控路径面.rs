//! 受控路径唯一打开口：父目录描述符固定，不按完整路径重开。
use crate::错误码;
use std::ffi::CString;
use std::fs::File;
use std::io;
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Component, Path};
#[cfg(target_os = "macos")]
const 禁止链接标志: i32 = 0x100;
#[cfg(not(target_os = "macos"))]
const 禁止链接标志: i32 = 0x20000;
#[cfg(target_os = "macos")]
const 目录打开标志: i32 = 0x100000;
#[cfg(not(target_os = "macos"))]
const 目录打开标志: i32 = 0x10000;
#[cfg(target_os = "macos")]
const 关闭继承标志: i32 = 0x1000000;
#[cfg(not(target_os = "macos"))]
const 关闭继承标志: i32 = 0x80000;
#[cfg(target_os = "macos")]
const 非阻塞标志: i32 = 4;
#[cfg(not(target_os = "macos"))]
const 非阻塞标志: i32 = 0x800;
#[cfg(target_os = "macos")]
pub(crate) const 独占写入标志: i32 = 1 | 0x200 | 0x800;
#[cfg(not(target_os = "macos"))]
pub(crate) const 独占写入标志: i32 = 1 | 0x40 | 0x80;
#[cfg(target_os = "macos")]
type 创建权限 = u16;
#[cfg(not(target_os = "macos"))]
type 创建权限 = u32;
// 平台C符号必须保留原名；Rust侧只通过中文包装调用。
unsafe extern "C" {
    fn openat(
        目录描述符: i32, 路径指针: *const std::ffi::c_char, 打开标志: i32, ...
    ) -> i32;
    fn mkdirat(
        目录描述符: i32, 路径指针: *const std::ffi::c_char, 权限: 创建权限
    ) -> i32;
    fn renameat(
        旧目录: i32,
        旧名称: *const std::ffi::c_char,
        新目录: i32,
        新名称: *const std::ffi::c_char,
    ) -> i32;
    fn unlinkat(
        目录描述符: i32, 路径指针: *const std::ffi::c_char, 打开模式: i32
    ) -> i32;
}
pub(crate) fn 相对打开(
    父目录文件: &File, 名称: &CString, 打开模式: i32
) -> io::Result<File> {
    let 描述符 = unsafe {
        openat(
            父目录文件.as_raw_fd(),
            名称.as_ptr(),
            打开模式 | 禁止链接标志 | 关闭继承标志 | 非阻塞标志,
            0o600_u32,
        )
    };
    if 描述符 < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(unsafe { File::from_raw_fd(描述符) })
    }
}
pub(crate) fn 相对替换(
    父目录文件: &File,
    旧名称: &CString,
    新名称: &CString,
) -> io::Result<()> {
    let 返回码 = unsafe {
        renameat(
            父目录文件.as_raw_fd(),
            旧名称.as_ptr(),
            父目录文件.as_raw_fd(),
            新名称.as_ptr(),
        )
    };
    if 返回码 < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}
pub(crate) fn 相对删除(父目录文件: &File, 名称: &CString) {
    unsafe {
        unlinkat(父目录文件.as_raw_fd(), 名称.as_ptr(), 0);
    }
}
pub(crate) fn 映射路径错误(路径错误: io::Error) -> u32 {
    if 路径错误.kind() == io::ErrorKind::NotFound {
        错误码::文件不存在
    } else {
        错误码::读取被拒
    }
}
pub(crate) fn 打开受控父目录(
    受控根目录: &str,
    相对路径: &str,
    创建父目录: bool,
) -> Result<(File, CString), u32> {
    if !Path::new(受控根目录).is_absolute() {
        return Err(错误码::路径不是绝对路径);
    }
    if 受控根目录.len() > 4096 || 相对路径.len() > 4096 || 相对路径.contains('\0') {
        return Err(错误码::参数不合法);
    }
    let mut 分量表 = Path::new(相对路径).components().collect::<Vec<_>>();
    if 分量表.is_empty()
        || 分量表
            .iter()
            .any(|分量| !matches!(分量, Component::Normal(_)))
    {
        return Err(错误码::参数不合法);
    }
    let 末段 = 分量表.pop().ok_or(错误码::参数不合法)?;
    let 文件名称 = CString::new(末段.as_os_str().as_encoded_bytes())
        .map_err(|_| 错误码::参数不合法)?;
    let mut 目录文件 = std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(禁止链接标志 | 目录打开标志 | 关闭继承标志)
        .open(受控根目录)
        .map_err(映射路径错误)?;
    for 分量 in 分量表 {
        let 目录名称 = CString::new(分量.as_os_str().as_encoded_bytes())
            .map_err(|_| 错误码::参数不合法)?;
        let mut 打开结果 = 相对打开(&目录文件, &目录名称, 目录打开标志);
        if 创建父目录
            && 打开结果
                .as_ref()
                .is_err_and(|错误| 错误.kind() == io::ErrorKind::NotFound)
        {
            let 返回码 = unsafe { mkdirat(目录文件.as_raw_fd(), 目录名称.as_ptr(), 0o700) };
            if 返回码 < 0 && io::Error::last_os_error().kind() != io::ErrorKind::AlreadyExists {
                return Err(错误码::写入失败);
            }
            打开结果 = 相对打开(&目录文件, &目录名称, 目录打开标志);
        }
        目录文件 = 打开结果.map_err(映射路径错误)?;
    }
    Ok((目录文件, 文件名称))
}
