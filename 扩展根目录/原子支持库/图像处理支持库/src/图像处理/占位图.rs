//! 6403 生成占位图：纯色 / 棋盘 / 渐变底 + 中线，出 PNG。

use crate::编号与码面::错误码;
use image::{DynamicImage, ImageFormat, Rgba, RgbaImage};

use super::基础件::{b64编码, 查尺寸, 拼装, 键值, 键文, 编码, 解析颜色, 解析数字};

// ---------------------------------------------------------------- 6403 生成占位图

pub(crate) fn 生成占位图实现(
    宽文本: &str,
    高文本: &str,
    类型: &str,
    背景色: &str,
    前景色: &str,
    源文本: &str,
) -> Result<String, u32> {
    let 列宽 = 解析数字(宽文本)?;
    let 行高 = 解析数字(高文本)?;
    查尺寸(列宽, 行高)?;
    let 底色 = 解析颜色(背景色)?;
    let 前景 = 解析颜色(前景色)?;
    let mut 画布 = RgbaImage::from_pixel(列宽, 行高, 底色);
    match 类型.trim().to_ascii_lowercase().as_str() {
        "" | "solid" | "纯色" => {}
        "checker" | "棋盘" => 画棋盘(&mut 画布, 前景),
        "gradient" | "渐变" => 画渐变(&mut 画布, 底色, 前景),
        _ => return Err(错误码::参数不合法),
    }
    if !源文本.trim().is_empty() {
        画横线(&mut 画布, 前景);
    }
    let 图像 = DynamicImage::from(画布);
    let 字节 = 编码(&图像, ImageFormat::Png)?;
    Ok(拼装(&[
        键文("图像b64", b64编码(&字节).as_str()),
        键文("格式", "png"),
        键值("宽度", 列宽),
        键值("高度", 行高),
        键值("字节数", 字节.len()),
    ]))
}

pub(super) fn 画棋盘(画布: &mut RgbaImage, 前景: Rgba<u8>) {
    let 格子 = 16u32;
    for (列序, 行序, 像素) in 画布.enumerate_pixels_mut() {
        if ((列序 / 格子) + (行序 / 格子)).is_multiple_of(2) {
            *像素 = 前景;
        }
    }
}

pub(super) fn 画渐变(画布: &mut RgbaImage, 底分量: Rgba<u8>, 顶分量: Rgba<u8>) {
    let 行高 = 画布.height().max(1);
    for 行序 in 0..画布.height() {
        let 比例 = 行序 as f32 / 行高 as f32;
        let 混值 = |首字节: u8, 次字节: u8| ((f32::from(首字节) * (1.0 - 比例)) + (f32::from(次字节) * 比例)) as u8;
        for 列序 in 0..画布.width() {
            画布.put_pixel(列序, 行序, Rgba([混值(底分量[0], 顶分量[0]), 混值(底分量[1], 顶分量[1]), 混值(底分量[2], 顶分量[2]), 255]));
        }
    }
}

pub(super) fn 画横线(画布: &mut RgbaImage, 颜色值: Rgba<u8>) {
    let 行高 = 画布.height();
    let 列宽 = 画布.width();
    let 中线 = 行高 / 2;
    let 厚度 = (行高 / 40).max(1);
    for 行序 in 中线.saturating_sub(厚度)..=(中线 + 厚度).min(行高.saturating_sub(1)) {
        for 列序 in (列宽 / 10)..(列宽 - 列宽 / 10) {
            画布.put_pixel(列序, 行序, 颜色值);
        }
    }
}
