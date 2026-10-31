use std::io::{Read, Write};

use crate::编号与码面::错误码;

// 图片抽取与原子落盘：只读 ZIP 容器里的媒体条目，不解码、不执行。
pub const 单图内嵌字节上限: usize = 262144;
pub const 图片内嵌总字节上限: usize = 1048576;
pub const 归档条目上限: usize = 4096;

pub struct 图片资源 {
    pub 条目路径: String,
    pub 媒体类型: &'static str,
    pub 字节: Vec<u8>,
}

pub struct 图片清单 {
    pub 图片: Vec<图片资源>,
    pub 图片数: usize,
    pub 内嵌总字节: usize,
    pub 超限条目: Vec<String>,
}

pub fn 取图片媒体类型(条目名称: &str) -> Option<&'static str> {
    let 小写名称 = 条目名称.to_ascii_lowercase();
    let 媒体类型 = if 小写名称.ends_with(".png") {
        "image/png"
    } else if 小写名称.ends_with(".jpg") || 小写名称.ends_with(".jpeg") {
        "image/jpeg"
    } else if 小写名称.ends_with(".gif") {
        "image/gif"
    } else if 小写名称.ends_with(".bmp") {
        "image/bmp"
    } else if 小写名称.ends_with(".webp") {
        "image/webp"
    } else if 小写名称.ends_with(".svg") {
        "image/svg+xml"
    } else if 小写名称.ends_with(".tif") || 小写名称.ends_with(".tiff") {
        "image/tiff"
    } else if 小写名称.ends_with(".emf") {
        "image/emf"
    } else if 小写名称.ends_with(".wmf") {
        "image/wmf"
    } else {
        return None;
    };
    Some(媒体类型)
}

pub fn 枚举图片资源(文件路径: &str, 目录前缀: &str) -> Result<图片清单, u32> {
    let 源文件 = std::fs::File::open(文件路径).map_err(|_| 错误码::内容不合法)?;
    let mut 归档句柄 = zip::ZipArchive::new(源文件).map_err(|_| 错误码::内容不合法)?;
    if 归档句柄.len() > 归档条目上限 {
        return Err(错误码::内容不合法);
    }
    let mut 资源清单 = 图片清单 {
        图片: Vec::new(),
        图片数: 0,
        内嵌总字节: 0,
        超限条目: Vec::new(),
    };
    for 条目序位 in 0..归档句柄.len() {
        let 条目句柄 = 归档句柄.by_index(条目序位).map_err(|_| 错误码::内容不合法)?;
        if 条目句柄.is_dir() {
            continue;
        }
        let 条目名称 = 条目句柄.name().map_err(|_| 错误码::内容不合法)?.to_string();
        if !条目名称.starts_with(目录前缀) {
            continue;
        }
        let 媒体类型 = match 取图片媒体类型(&条目名称) {
            Some(类型名) => 类型名,
            None => continue,
        };
        let 条目大小 = 条目句柄.size() as usize;
        if 条目大小 > 单图内嵌字节上限
            || 资源清单.内嵌总字节.saturating_add(条目大小) > 图片内嵌总字节上限
        {
            资源清单.超限条目.push(条目名称);
            continue;
        }
        let mut 图片字节 = Vec::with_capacity(条目大小);
        条目句柄
            .take(单图内嵌字节上限 as u64 + 1)
            .read_to_end(&mut 图片字节)
            .map_err(|_| 错误码::内容不合法)?;
        if 图片字节.len() > 单图内嵌字节上限 {
            资源清单.超限条目.push(条目名称);
            continue;
        }
        资源清单.内嵌总字节 = 资源清单.内嵌总字节.saturating_add(图片字节.len());
        资源清单.图片数 += 1;
        资源清单.图片.push(图片资源 {
            条目路径: 条目名称,
            媒体类型,
            字节: 图片字节,
        });
    }
    Ok(资源清单)
}

pub fn 组装资源JSON(资源清单: &图片清单) -> serde_json::Value {
    let mut 图片节点表 = Vec::with_capacity(资源清单.图片.len());
    for 单个图片 in &资源清单.图片 {
        let 短名称 = 单个图片
            .条目路径
            .rsplit('/')
            .next()
            .unwrap_or(&单个图片.条目路径)
            .to_string();
        图片节点表.push(serde_json::json!({
            "名称": 短名称,
            "条目路径": 单个图片.条目路径,
            "媒体类型": 单个图片.媒体类型,
            "字节数": 单个图片.字节.len(),
            "内容BASE64": 编码BASE64(&单个图片.字节),
        }));
    }
    let mut 未内嵌表 = Vec::with_capacity(资源清单.超限条目.len());
    for 超限名称 in &资源清单.超限条目 {
        未内嵌表.push(serde_json::json!({
            "条目路径": 超限名称,
            "原因": "超过单图 256KiB 或总量 1MiB 内嵌上限，未内嵌",
        }));
    }
    serde_json::json!({
        "图片数": 资源清单.图片数,
        "内嵌字节数": 资源清单.内嵌总字节,
        "图片": 图片节点表,
        "未内嵌": 未内嵌表,
        "单图上限": 单图内嵌字节上限,
        "总量上限": 图片内嵌总字节上限,
    })
}

pub fn 编码BASE64(原始字节: &[u8]) -> String {
    const 编码表: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut 输出文本 = String::with_capacity(原始字节.len().div_ceil(3) * 4);
    for 三字节组 in 原始字节.chunks(3) {
        let 首字节 = 三字节组[0] as u32;
        let 次字节 = *三字节组.get(1).unwrap_or(&0) as u32;
        let 末字节 = *三字节组.get(2).unwrap_or(&0) as u32;
        let 拼合值 = (首字节 << 16) | (次字节 << 8) | 末字节;
        输出文本.push(编码表[(拼合值 >> 18) as usize & 63] as char);
        输出文本.push(编码表[(拼合值 >> 12) as usize & 63] as char);
        输出文本.push(if 三字节组.len() > 1 {
            编码表[(拼合值 >> 6) as usize & 63] as char
        } else {
            '='
        });
        输出文本.push(if 三字节组.len() > 2 {
            编码表[拼合值 as usize & 63] as char
        } else {
            '='
        });
    }
    输出文本
}

// 先写同目录临时件、sync 后 rename：失败不留半截目标文件。
pub fn 原子写出(输出路径: &str, 待写字节: &[u8]) -> Result<(), u32> {
    let 目标路径 = std::path::Path::new(输出路径);
    let 父目录 = 目标路径
        .parent()
        .filter(|目录路径| !目录路径.as_os_str().is_empty())
        .ok_or(错误码::写出失败)?;
    let 文件名 = 目标路径
        .file_name()
        .map(|名字值| 名字值.to_string_lossy().into_owned())
        .ok_or(错误码::写出失败)?;
    if !父目录.is_dir() {
        return Err(错误码::写出失败);
    }
    let 临时路径 = 父目录.join(format!(".{文件名}.{}.tmp", std::process::id()));
    let 写出结果 = (|| -> std::io::Result<()> {
        let mut 临时文件 = std::fs::File::create(&临时路径)?;
        临时文件.write_all(待写字节)?;
        临时文件.sync_all()?;
        Ok(())
    })();
    if 写出结果.is_err() {
        let _ = std::fs::remove_file(&临时路径);
        return Err(错误码::写出失败);
    }
    if let Err(重命名错误) = std::fs::rename(&临时路径, 目标路径) {
        let _ = std::fs::remove_file(&临时路径);
        let _ = 重命名错误;
        return Err(错误码::写出失败);
    }
    Ok(())
}
