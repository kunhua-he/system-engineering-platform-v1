//! 有界读取与单层列目录（3102 · 3103 · 3107）。

use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合元素, 复合值, 编码复合值载荷};

use super::基础件::{读有界文件, 映射读错};

pub(super) fn 读取能力行(
    编号: u32,
    文件路径: &std::path::Path,
) -> Result<(u32, Vec<u8>), u32> {
    let 文件字节 = 读有界文件(文件路径)?;
    if 编号 == 能力号::读取文本 {
        std::str::from_utf8(&文件字节).map_err(|_| 错误码::内容不合法)?;
    }
    Ok((if 编号 == 能力号::读取文本 { 4 } else { 5 }, 文件字节))
}

pub(super) fn 列出目录行(文件路径: &std::path::Path) -> Result<(u32, Vec<u8>), u32> {
    let mut 名称表 = Vec::new();
    for 目录项 in std::fs::read_dir(文件路径).map_err(映射读错)? {
        if 名称表.len() >= 1000 {
            return Err(错误码::资源受限);
        }
        let 目录项 = 目录项.map_err(映射读错)?;
        名称表.push(目录项.file_name().into_string().map_err(|_| 错误码::内容不合法)?);
    }
    名称表.sort();
    let 元素表 = 名称表
        .into_iter()
        .map(|名称| 复合元素 {
            名称: String::new(),
            值: 复合值::文本载荷(名称),
        })
        .collect::<Vec<_>>();
    Ok((
        100,
        编码复合值载荷(100, &元素表).map_err(|_| 错误码::内容不合法)?,
    ))
}
