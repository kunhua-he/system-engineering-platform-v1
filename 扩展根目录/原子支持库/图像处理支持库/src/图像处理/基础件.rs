//! 图像能力基础件：尺寸与字节上限校验 · base64 编解码 · 解码与编码 · 回执拼装 · 颜色解析。
//!
//! 上层各能力件（分析 / 占位图 / 变换 / 编码与哈希 / 判定）共用本件；本件不反向依赖任何能力件。

use crate::编号与码面::错误码;
use image::{DynamicImage, ImageFormat, ImageReader, Rgba};
use std::io::Cursor;

const 单边上限: u32 = 20_000;
const 总像素上限: u64 = 100_000_000;
const 输入字节上限: usize = 64 * 1024 * 1024;

pub(super) fn 解析数字(源文本: &str) -> Result<u32, u32> {
    let 值 = 源文本.trim().parse::<u32>().map_err(|_| 错误码::参数不合法)?;
    if 值 == 0 || 值 > 单边上限 {
        return Err(错误码::尺寸超限);
    }
    Ok(值)
}

pub(super) fn 查尺寸(列宽: u32, 行高: u32) -> Result<(), u32> {
    if 列宽 == 0 || 行高 == 0 || 列宽 > 单边上限 || 行高 > 单边上限 {
        return Err(错误码::尺寸超限);
    }
    if u64::from(列宽) * u64::from(行高) > 总像素上限 {
        return Err(错误码::尺寸超限);
    }
    Ok(())
}

pub(super) fn 解码字节(字节: &[u8]) -> Result<DynamicImage, u32> {
    if 字节.is_empty() || 字节.len() > 输入字节上限 {
        return Err(错误码::参数不合法);
    }
    let 读取器 = ImageReader::new(Cursor::new(字节))
        .with_guessed_format()
        .map_err(|_| 错误码::解码失败)?;
    let 图像 = 读取器.decode().map_err(|_| 错误码::解码失败)?;
    查尺寸(图像.width(), 图像.height())?;
    Ok(图像)
}

pub(super) fn 解码base64(源文本: &str) -> Result<DynamicImage, u32> {
    解码字节(&b64解码(源文本)?)
}

pub(super) fn 格式扩展名(格式: ImageFormat) -> &'static str {
    match 格式 {
        ImageFormat::Png => "png",
        ImageFormat::Jpeg => "jpeg",
        ImageFormat::Gif => "gif",
        ImageFormat::WebP => "webp",
        ImageFormat::Bmp => "bmp",
        ImageFormat::Tiff => "tiff",
        _ => "unknown",
    }
}

pub(super) fn 格式判定(字节: &[u8]) -> String {
    match image::guess_format(字节) {
        Ok(格式) => 格式扩展名(格式).to_string(),
        Err(_) => "unknown".to_string(),
    }
}

pub(super) fn 按名取格式(名称: &str) -> Result<ImageFormat, u32> {
    match 名称.trim().to_ascii_lowercase().as_str() {
        "png" => Ok(ImageFormat::Png),
        "jpg" | "jpeg" => Ok(ImageFormat::Jpeg),
        "gif" => Ok(ImageFormat::Gif),
        "webp" => Ok(ImageFormat::WebP),
        "bmp" => Ok(ImageFormat::Bmp),
        "tiff" | "tif" => Ok(ImageFormat::Tiff),
        _ => Err(错误码::格式不支持),
    }
}

pub(super) fn 编码(图像: &DynamicImage, 格式: ImageFormat) -> Result<Vec<u8>, u32> {
    查尺寸(图像.width(), 图像.height())?;
    let mut 缓冲 = Vec::new();
    图像
        .write_to(&mut Cursor::new(&mut 缓冲), 格式)
        .map_err(|_| 错误码::写出失败)?;
    if 缓冲.is_empty() {
        return Err(错误码::写出失败);
    }
    Ok(缓冲)
}

pub(super) fn 装图像回执(字节: &[u8], 列宽: u32, 行高: u32) -> String {
    拼装(&[
        键文("图像b64", b64编码(字节).as_str()),
        键值("宽度", 列宽),
        键值("高度", 行高),
        键值("字节数", 字节.len()),
    ])
}

const 字母表: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

pub(super) fn b64编码(原文: &[u8]) -> String {
    let mut 输出 = String::with_capacity(原文.len().div_ceil(3) * 4);
    for 字节组 in 原文.chunks(3) {
        let 首字节 = 字节组[0];
        let 次字节 = *字节组.get(1).unwrap_or(&0);
        let 末字节 = *字节组.get(2).unwrap_or(&0);
        输出.push(字母表[(首字节 >> 2) as usize] as char);
        输出.push(字母表[(((首字节 & 0b11) << 4) | (次字节 >> 4)) as usize] as char);
        输出.push(if 字节组.len() > 1 {
            字母表[(((次字节 & 0b1111) << 2) | (末字节 >> 6)) as usize] as char
        } else {
            '='
        });
        输出.push(if 字节组.len() > 2 {
            字母表[(末字节 & 0b111111) as usize] as char
        } else {
            '='
        });
    }
    输出
}

pub(super) fn b64解码(原文: &str) -> Result<Vec<u8>, u32> {
    let 净文本: Vec<u8> = 原文
        .bytes()
        .filter(|字节| !字节.is_ascii_whitespace())
        .collect();
    let 填充 = 净文本.iter().rev().take_while(|字节| **字节 == b'=').count();
    let 净内容 = &净文本[..净文本.len().saturating_sub(填充)];
    let mut 输出 = Vec::with_capacity(净内容.len() / 4 * 3);
    let mut 缓冲: u32 = 0;
    let mut 位数 = 0;
    for 字节 in 净内容 {
        let 值 = match 字节 {
            b'A'..=b'Z' => 字节 - b'A',
            b'a'..=b'z' => 字节 - b'a' + 26,
            b'0'..=b'9' => 字节 - b'0' + 52,
            b'+' => 62,
            b'/' => 63,
            _ => return Err(错误码::参数不合法),
        };
        缓冲 = (缓冲 << 6) | u32::from(值);
        位数 += 6;
        if 位数 >= 8 {
            位数 -= 8;
            输出.push((缓冲 >> 位数) as u8);
        }
    }
    if 输出.is_empty() {
        return Err(错误码::参数不合法);
    }
    Ok(输出)
}

pub(super) fn 转义(原文: &str) -> String {
    原文
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
}

pub(super) fn 拼装(片段表: &[String]) -> String {
    format!("{{{}}}", 片段表.join(","))
}

pub(super) fn 键值(键名: &str, 值: impl std::fmt::Display) -> String {
    format!("\"{键名}\":{值}")
}

pub(super) fn 键文(键名: &str, 值: &str) -> String {
    format!("\"{键名}\":\"{}\"", 转义(值))
}

pub(super) fn 解析颜色(源文本: &str) -> Result<Rgba<u8>, u32> {
    let 净文本 = 源文本.trim().trim_start_matches('#');
    let 取值 = u32::from_str_radix(净文本, 16).map_err(|_| 错误码::参数不合法)?;
    match 净文本.len() {
        6 => Ok(Rgba([
            ((取值 >> 16) & 0xFF) as u8,
            ((取值 >> 8) & 0xFF) as u8,
            (取值 & 0xFF) as u8,
            255,
        ])),
        8 => Ok(Rgba([
            ((取值 >> 24) & 0xFF) as u8,
            ((取值 >> 16) & 0xFF) as u8,
            ((取值 >> 8) & 0xFF) as u8,
            (取值 & 0xFF) as u8,
        ])),
        _ => Err(错误码::参数不合法),
    }
}
