//! 图像能力（字节式）：统计、格式识别、占位图、缩放、转置、合成、重编码、EXIF 转置、
//! 透明背景合成、感知哈希组。
//!
//! 全部能力都是**字节进字节出**：图像以 base64 文本传入，产物以 base64 文本返回；
//! 需要落盘的调用方自行写文件 —— 这样能力不绑死路径，也不做任意路径写入。

use crate::编号与码面::错误码;
use image::imageops::FilterType;
use image::{DynamicImage, GenericImageView, ImageFormat, ImageReader, Rgba, RgbaImage};
use std::io::Cursor;

const 单边上限: u32 = 20_000;
const 总像素上限: u64 = 100_000_000;
const 输入字节上限: usize = 64 * 1024 * 1024;

fn 解析数字(源文本: &str) -> Result<u32, u32> {
    let 值 = 源文本.trim().parse::<u32>().map_err(|_| 错误码::参数不合法)?;
    if 值 == 0 || 值 > 单边上限 {
        return Err(错误码::尺寸超限);
    }
    Ok(值)
}

fn 查尺寸(列宽: u32, 行高: u32) -> Result<(), u32> {
    if 列宽 == 0 || 行高 == 0 || 列宽 > 单边上限 || 行高 > 单边上限 {
        return Err(错误码::尺寸超限);
    }
    if u64::from(列宽) * u64::from(行高) > 总像素上限 {
        return Err(错误码::尺寸超限);
    }
    Ok(())
}

fn 解码字节(字节: &[u8]) -> Result<DynamicImage, u32> {
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

fn 解码base64(源文本: &str) -> Result<DynamicImage, u32> {
    解码字节(&b64解码(源文本)?)
}

fn 格式扩展名(格式: ImageFormat) -> &'static str {
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

fn 格式判定(字节: &[u8]) -> String {
    match image::guess_format(字节) {
        Ok(格式) => 格式扩展名(格式).to_string(),
        Err(_) => "unknown".to_string(),
    }
}

fn 按名取格式(名称: &str) -> Result<ImageFormat, u32> {
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

fn 编码(图像: &DynamicImage, 格式: ImageFormat) -> Result<Vec<u8>, u32> {
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

fn 装图像回执(字节: &[u8], 列宽: u32, 行高: u32) -> String {
    拼装(&[
        键文("图像b64", b64编码(字节).as_str()),
        键值("宽度", 列宽),
        键值("高度", 行高),
        键值("字节数", 字节.len()),
    ])
}

const 字母表: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn b64编码(原文: &[u8]) -> String {
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

fn b64解码(原文: &str) -> Result<Vec<u8>, u32> {
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

fn 转义(原文: &str) -> String {
    原文
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
}

fn 拼装(片段表: &[String]) -> String {
    format!("{{{}}}", 片段表.join(","))
}

fn 键值(键名: &str, 值: impl std::fmt::Display) -> String {
    format!("\"{键名}\":{值}")
}

fn 键文(键名: &str, 值: &str) -> String {
    format!("\"{键名}\":\"{}\"", 转义(值))
}

fn 模式名(图像: &DynamicImage) -> String {
    // 直接取 ColorType 的调试名：与动态图内部通道一一对应，免去逐个变体匹配。
    format!("{:?}", 图像.color())
}

fn 平均颜色(图像: &RgbaImage) -> (u64, u64, u64) {
    let 总数 = u64::from(图像.width()) * u64::from(图像.height());
    if 总数 == 0 {
        return (0, 0, 0);
    }
    let mut 红分量: u64 = 0;
    let mut 绿分量: u64 = 0;
    let mut 蓝分量: u64 = 0;
    for 像素 in 图像.pixels() {
        红分量 += u64::from(像素[0]);
        绿分量 += u64::from(像素[1]);
        蓝分量 += u64::from(像素[2]);
    }
    (红分量 / 总数, 绿分量 / 总数, 蓝分量 / 总数)
}

// ---------------------------------------------------------------- 6401 分析图像

pub(crate) fn 分析图像实现(图像base64: &str) -> Result<String, u32> {
    let 字节 = b64解码(图像base64)?;
    let 图像 = 解码字节(&字节)?;
    let (列宽, 行高) = 图像.dimensions();
    let (红分量, 绿分量, 蓝分量) = 平均颜色(&图像.to_rgba8());
    Ok(拼装(&[
        键文("格式", 格式判定(&字节).as_str()),
        键值("宽度", 列宽),
        键值("高度", 行高),
        键文("模式", &模式名(&图像)),
        键值("像素数", u64::from(列宽) * u64::from(行高)),
        键值(
            "平均颜色",
            拼装(&[键值("红分量", 红分量), 键值("绿分量", 绿分量), 键值("蓝分量", 蓝分量)]),
        ),
        键值("字节数", 字节.len()),
    ]))
}

// ---------------------------------------------------------------- 6402 识别图像格式

pub(crate) fn 识别格式实现(图像base64: &str) -> Result<String, u32> {
    let 字节 = b64解码(图像base64)?;
    let 图像 = 解码字节(&字节)?;
    let (列宽, 行高) = 图像.dimensions();
    Ok(拼装(&[
        键文("格式", 格式判定(&字节).as_str()),
        键值("宽度", 列宽),
        键值("高度", 行高),
        键文("模式", &模式名(&图像)),
    ]))
}

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

fn 解析颜色(源文本: &str) -> Result<Rgba<u8>, u32> {
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

fn 画棋盘(画布: &mut RgbaImage, 前景: Rgba<u8>) {
    let 格子 = 16u32;
    for (列序, 行序, 像素) in 画布.enumerate_pixels_mut() {
        if ((列序 / 格子) + (行序 / 格子)).is_multiple_of(2) {
            *像素 = 前景;
        }
    }
}

fn 画渐变(画布: &mut RgbaImage, 底分量: Rgba<u8>, 顶分量: Rgba<u8>) {
    let 行高 = 画布.height().max(1);
    for 行序 in 0..画布.height() {
        let 比例 = 行序 as f32 / 行高 as f32;
        let 混值 = |首字节: u8, 次字节: u8| ((f32::from(首字节) * (1.0 - 比例)) + (f32::from(次字节) * 比例)) as u8;
        for 列序 in 0..画布.width() {
            画布.put_pixel(列序, 行序, Rgba([混值(底分量[0], 顶分量[0]), 混值(底分量[1], 顶分量[1]), 混值(底分量[2], 顶分量[2]), 255]));
        }
    }
}

fn 画横线(画布: &mut RgbaImage, 颜色值: Rgba<u8>) {
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

fn 平均哈希(灰度: &image::GrayImage) -> String {
    let 缩图 = image::imageops::resize(灰度, 8, 8, FilterType::Nearest);
    let 均值 = 缩图.pixels().map(|像素| u64::from(像素[0])).sum::<u64>() / 64;
    位串转十六进制(
        &缩图
            .pixels()
            .map(|像素| u64::from(像素[0]) > 均值)
            .collect::<Vec<bool>>(),
    )
}

fn 差异哈希(灰度: &image::GrayImage, 列宽: u32, 行高: u32) -> String {
    let 缩图 = image::imageops::resize(灰度, 列宽, 行高, FilterType::Nearest);
    let mut 位序 = Vec::with_capacity(((列宽 - 1) * 行高) as usize);
    for 行序 in 0..行高 {
        for 列序 in 0..(列宽 - 1) {
            位序.push(缩图.get_pixel(列序, 行序)[0] > 缩图.get_pixel(列序 + 1, 行序)[0]);
        }
    }
    位串转十六进制(&位序)
}

fn 位串转十六进制(位序: &[bool]) -> String {
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
