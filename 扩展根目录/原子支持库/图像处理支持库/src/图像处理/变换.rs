//! 6404 缩放 · 6405 转置 · 6406 合成 · 6410 透明背景合成：几何变换与逐像素叠加。

use crate::编号与码面::错误码;
use image::imageops::FilterType;
use image::{DynamicImage, GenericImageView, ImageFormat, Rgba, RgbaImage};

use super::基础件::{查尺寸, 编码, 解码base64, 装图像回执, 解析颜色, 解析数字};

// ---------------------------------------------------------------- 6404 缩放

pub(crate) fn 缩放实现(图像base64: &str, 宽文本: &str, 高文本: &str) -> Result<String, u32> {
    let 列宽 = 解析数字(宽文本)?;
    let 行高 = 解析数字(高文本)?;
    查尺寸(列宽, 行高)?;
    let 图像 = 解码base64(图像base64)?;
    let 缩放后 = 图像.resize_exact(列宽, 行高, FilterType::CatmullRom);
    let 字节 = 编码(&缩放后, ImageFormat::Png)?;
    Ok(装图像回执(&字节, 列宽, 行高))
}

// ---------------------------------------------------------------- 6405 转置

pub(crate) fn 转置实现(图像base64: &str, 方式: &str) -> Result<String, u32> {
    let 图像 = 解码base64(图像base64)?;
    let 产物 = match 方式.trim().to_ascii_lowercase().as_str() {
        "fliph" | "水平翻转" => 图像.fliph(),
        "flipv" | "垂直翻转" => 图像.flipv(),
        "rotate90" | "顺时针90" => 图像.rotate90(),
        "rotate180" | "旋转180" => 图像.rotate180(),
        "rotate270" | "逆时针90" => 图像.rotate270(),
        _ => return Err(错误码::参数不合法),
    };
    let (列宽, 行高) = 产物.dimensions();
    let 字节 = 编码(&产物, ImageFormat::Png)?;
    Ok(装图像回执(&字节, 列宽, 行高))
}

// ---------------------------------------------------------------- 6406 合成

pub(crate) fn 合成实现(
    底分量base64: &str,
    叠图base64: &str,
    偏移x源文本: &str,
    偏移y源文本: &str,
) -> Result<String, u32> {
    let 偏移x = 偏移x源文本.trim().parse::<i64>().map_err(|_| 错误码::参数不合法)?;
    let 偏移y = 偏移y源文本.trim().parse::<i64>().map_err(|_| 错误码::参数不合法)?;
    let mut 底分量 = 解码base64(底分量base64)?.to_rgba8();
    let 叠图 = 解码base64(叠图base64)?.to_rgba8();
    for (列序, 行序, 像素) in 叠图.enumerate_pixels() {
        let 目标x = i64::from(列序) + 偏移x;
        let 目标y = i64::from(行序) + 偏移y;
        if 目标x < 0 || 目标y < 0 {
            continue;
        }
        let (目标x, 目标y) = (目标x as u32, 目标y as u32);
        if 目标x >= 底分量.width() || 目标y >= 底分量.height() {
            continue;
        }
        let 端像素 = 底分量.get_pixel(目标x, 目标y);
        let 源像素 = 像素;
        if 源像素[3] == 255 {
            底分量.put_pixel(目标x, 目标y, *源像素);
        } else if 源像素[3] > 0 {
            let 系数 = u16::from(源像素[3]);
            let 混值 = |前分量: u8, 后分量: u8| {
                (((u16::from(前分量) * 系数) + (u16::from(后分量) * (255 - 系数))) / 255) as u8
            };
            底分量.put_pixel(
                目标x,
                目标y,
                Rgba([
                    混值(源像素[0], 端像素[0]),
                    混值(源像素[1], 端像素[1]),
                    混值(源像素[2], 端像素[2]),
                    端像素[3].max(源像素[3]),
                ]),
            );
        }
    }
    let 图像 = DynamicImage::from(底分量);
    let (列宽, 行高) = 图像.dimensions();
    let 字节 = 编码(&图像, ImageFormat::Png)?;
    Ok(装图像回执(&字节, 列宽, 行高))
}

// ---------------------------------------------------------------- 6410 透明背景合成

pub(crate) fn 透明背景合成实现(图像base64: &str, 背景色: &str) -> Result<String, u32> {
    let 背景 = 解析颜色(背景色)?;
    let 图像 = 解码base64(图像base64)?.to_rgba8();
    let (列宽, 行高) = (图像.width(), 图像.height());
    let mut 画布 = RgbaImage::from_pixel(列宽, 行高, 背景);
    for (列序, 行序, 像素) in 图像.enumerate_pixels() {
        let 源像素 = 像素;
        let 端像素 = 画布.get_pixel(列序, 行序);
        if 源像素[3] == 0 {
            continue;
        }
        if 源像素[3] == 255 {
            画布.put_pixel(列序, 行序, *源像素);
            continue;
        }
        let 系数 = u16::from(源像素[3]);
        let 混值 = |前分量: u8, 后分量: u8| {
            (((u16::from(前分量) * 系数) + (u16::from(后分量) * (255 - 系数))) / 255) as u8
        };
        画布.put_pixel(
            列序,
            行序,
            Rgba([混值(源像素[0], 端像素[0]), 混值(源像素[1], 端像素[1]), 混值(源像素[2], 端像素[2]), 255]),
        );
    }
    let 图像 = DynamicImage::from(画布);
    let 字节 = 编码(&图像, ImageFormat::Png)?;
    Ok(装图像回执(&字节, 列宽, 行高))
}
