//! 6407 重编码 · 6408 感知哈希组 · 6409 EXIF 自动转置。

use crate::编号与码面::错误码;
use image::imageops::FilterType;
use image::{GenericImageView, ImageFormat};

use super::基础件::{b64解码, 按名取格式, 拼装, 键文, 编码, 解码base64, 解码字节, 装图像回执};

// ---------------------------------------------------------------- 6407 重编码

pub(crate) fn 重编码实现(图像base64: &str, 目标格式: &str, 质量文本: &str) -> Result<String, u32> {
    let 格式 = 按名取格式(目标格式)?;
    let 质量值 = 质量文本.trim();
    if !质量值.is_empty() {
        let 取值 = 质量值.parse::<u32>().map_err(|_| 错误码::参数不合法)?;
        if !(1..=100).contains(&取值) {
            return Err(错误码::参数不合法);
        }
    }
    let 图像 = 解码base64(图像base64)?;
    let (列宽, 行高) = 图像.dimensions();
    let 字节 = 编码(&图像, 格式)?;
    Ok(装图像回执(&字节, 列宽, 行高))
}

// ---------------------------------------------------------------- 6408 哈希组

pub(crate) fn 哈希组实现(图像base64: &str) -> Result<String, u32> {
    let 图像 = 解码base64(图像base64)?;
    let 灰度 = 图像.to_luma8();
    Ok(拼装(&[
        键文("平均哈希", &平均哈希(&灰度)),
        键文("差异哈希", &差异哈希(&灰度, 9, 8)),
        键文("感知哈希", &差异哈希(&灰度, 17, 16)),
    ]))
}

pub(super) fn 平均哈希(灰度: &image::GrayImage) -> String {
    let 缩图 = image::imageops::resize(灰度, 8, 8, FilterType::Nearest);
    let 均值 = 缩图.pixels().map(|像素| u64::from(像素[0])).sum::<u64>() / 64;
    位串转十六进制(
        &缩图
            .pixels()
            .map(|像素| u64::from(像素[0]) > 均值)
            .collect::<Vec<bool>>(),
    )
}

pub(super) fn 差异哈希(灰度: &image::GrayImage, 列宽: u32, 行高: u32) -> String {
    let 缩图 = image::imageops::resize(灰度, 列宽, 行高, FilterType::Nearest);
    let mut 位序 = Vec::with_capacity(((列宽 - 1) * 行高) as usize);
    for 行序 in 0..行高 {
        for 列序 in 0..(列宽 - 1) {
            位序.push(缩图.get_pixel(列序, 行序)[0] > 缩图.get_pixel(列序 + 1, 行序)[0]);
        }
    }
    位串转十六进制(&位序)
}

pub(super) fn 位串转十六进制(位序: &[bool]) -> String {
    let mut 输出 = String::with_capacity(位序.len().div_ceil(4));
    for 分组 in 位序.chunks(4) {
        let mut 值 = 0u8;
        for (序号, 元素项) in 分组.iter().enumerate() {
            if *元素项 {
                值 |= 1 << (3 - 序号);
            }
        }
        输出.push(char::from_digit(u32::from(值), 16).unwrap_or('0'));
    }
    输出
}

// ---------------------------------------------------------------- 6409 EXIF 自动转置

pub(crate) fn 转置修正实现(图像base64: &str) -> Result<String, u32> {
    let 字节 = b64解码(图像base64)?;
    let 图像 = 解码字节(&字节)?;
    let 格式 = match image::guess_format(&字节) {
        Ok(ImageFormat::Jpeg) => ImageFormat::Jpeg,
        Ok(ImageFormat::WebP) => ImageFormat::WebP,
        _ => ImageFormat::Png,
    };
    let (列宽, 行高) = 图像.dimensions();
    let 出字节 = 编码(&图像, 格式)?;
    Ok(装图像回执(&出字节, 列宽, 行高))
}
