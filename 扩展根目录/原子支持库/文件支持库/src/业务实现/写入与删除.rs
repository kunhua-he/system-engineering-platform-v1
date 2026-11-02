//! 新建 · 复制 · 创建目录 · 删除（3104 · 3105 · 3106 · 3108 · 3109 · 3110）。

use std::io::Write;

use crate::编号与码面::{能力号, 错误码};

use super::基础件::{查路径, 读有界文件, 映射读错};

fn 已存在或写入失败(失败: std::io::Error) -> u32 {
    if 失败.kind() == std::io::ErrorKind::AlreadyExists {
        错误码::文件已存在
    } else {
        错误码::写入失败
    }
}

pub(super) fn 新建或复制作业(
    编号: u32,
    文件路径: &std::path::Path,
    内容参数: &[u8],
) -> Result<(u32, Vec<u8>), u32> {
    let 复制字节;
    let (目标路径, 内容字节) = if 编号 == 能力号::复制文件 {
        复制字节 = 读有界文件(文件路径)?;
        (查路径(内容参数)?, 复制字节.as_slice())
    } else {
        (文件路径, 内容参数)
    };
    let mut 目标文件 = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(目标路径)
        .map_err(已存在或写入失败)?;
    if 目标文件
        .write_all(内容字节)
        .and_then(|_| 目标文件.sync_all())
        .is_err()
    {
        drop(目标文件);
        let _ = std::fs::remove_file(目标路径);
        return Err(错误码::写入失败);
    }
    Ok((4, 目标路径.as_os_str().as_encoded_bytes().to_vec()))
}

pub(super) fn 目录与删除作业(编号: u32, 文件路径: &std::path::Path) -> Result<(), u32> {
    match 编号 {
        能力号::创建目录 => {
            std::fs::create_dir(文件路径).map_err(已存在或写入失败)?;
        }
        能力号::删除文件 => {
            let 文件属性 = std::fs::symlink_metadata(文件路径).map_err(映射读错)?;
            if !文件属性.is_file() {
                return Err(错误码::不是普通文件);
            }
            std::fs::remove_file(文件路径).map_err(|_| 错误码::写入失败)?;
        }
        能力号::删除空目录 => {
            std::fs::remove_dir(文件路径).map_err(|_| 错误码::写入失败)?;
        }
        _ => return Err(错误码::参数不合法),
    }
    Ok(())
}
