//! 路径与参数解析 —— 工作区内的安全相对路径解析 · JSON 字符串数组参数解析。
//!
//! 两道闸都在这一件：相对路径拒上跳/绝对/符号链接且父目录必须落在根内；
//! 参数数组只认 JSON 字符串数组字面量，不做命令拼接（`git status` 一律拒）。

use std::fs;
use std::path::{Component, Path, PathBuf};

use crate::错误码;

pub(crate) fn 路径内文件(根: &Path, 相对: &str) -> Result<PathBuf, u32> {
    let 候选 = Path::new(相对);
    if 候选.is_absolute()
        || 候选.components().any(|片段| {
            matches!(
                片段,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        })
    {
        return Err(错误码::受控边界不合法);
    }
    let 根 = fs::canonicalize(根).map_err(|_| 错误码::文件不存在)?;
    let 完整 = 根.join(候选);
    let 父 = 完整.parent().ok_or(错误码::受控边界不合法)?;
    let 规范父 = fs::canonicalize(父).map_err(|_| 错误码::文件不存在)?;
    if !规范父.starts_with(&根)
        || fs::symlink_metadata(&完整)
            .map(|元| 元.file_type().is_symlink())
            .unwrap_or(false)
    {
        return Err(错误码::受控边界不合法);
    }
    let 元 = 完整.metadata().map_err(|_| 错误码::文件不存在)?;
    if !元.is_file() {
        return Err(错误码::不是普通文件);
    }
    Ok(完整)
}

pub(crate) fn 解析参数数组(文本: &str) -> Result<Vec<String>, u32> {
    let 字节 = 文本.as_bytes();
    let mut 位置 = 0;
    fn 空白(字节: &[u8], 位置: &mut usize) {
        while *位置 < 字节.len() && 字节[*位置].is_ascii_whitespace() {
            *位置 += 1
        }
    }
    空白(字节, &mut 位置);
    if 字节.get(位置) != Some(&b'[') {
        return Err(错误码::参数不合法);
    }
    位置 += 1;
    let mut 结果 = Vec::new();
    loop {
        空白(字节, &mut 位置);
        if 字节.get(位置) == Some(&b']') {
            位置 += 1;
            break;
        }
        if 字节.get(位置) != Some(&b'"') {
            return Err(错误码::参数不合法);
        }
        位置 += 1;
        let mut 当前 = String::new();
        let mut 完成 = false;
        while 位置 < 字节.len() {
            let 字 = 字节[位置];
            位置 += 1;
            match 字 {
                b'"' => {
                    完成 = true;
                    break;
                }
                b'\\' => {
                    let 转义 = *字节.get(位置).ok_or(错误码::参数不合法)?;
                    位置 += 1;
                    match 转义 {
                        b'"' => 当前.push('"'),
                        b'\\' => 当前.push('\\'),
                        b'n' => 当前.push('\n'),
                        b'r' => 当前.push('\r'),
                        b't' => 当前.push('\t'),
                        _ => return Err(错误码::参数不合法),
                    }
                }
                值 if 值 < 0x20 => return Err(错误码::参数不合法),
                值 if 值 >= 0x80 => {
                    let 起点 = 位置 - 1;
                    let 剩余文本 = std::str::from_utf8(&字节[起点..])
                        .map_err(|_| 错误码::参数不合法)?;
                    let 待解析字符 = 剩余文本.chars().next().ok_or(错误码::参数不合法)?;
                    当前.push(待解析字符);
                    位置 = 起点 + 待解析字符.len_utf8();
                }
                值 => 当前.push(值 as char),
            }
        }
        if !完成 {
            return Err(错误码::参数不合法);
        }
        结果.push(当前);
        空白(字节, &mut 位置);
        match 字节.get(位置) {
            Some(b',') => 位置 += 1,
            Some(b']') => {}
            _ => return Err(错误码::参数不合法),
        }
        if 字节.get(位置) == Some(&b']') {
            continue;
        }
    }
    空白(字节, &mut 位置);
    if 位置 != 字节.len()
        || 结果.is_empty()
        || 结果.len() > 128
        || 结果.iter().any(|项| 项.len() > 4096)
    {
        return Err(错误码::参数不合法);
    }
    Ok(结果)
}
