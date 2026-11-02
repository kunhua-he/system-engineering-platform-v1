//! 文档解析与生成：DOCX / PPTX 的 zip 容器读写与部件 XML 组装。

use std::io::{Read, Write};

use crate::编号与码面::错误码;

use super::基础件::转义文本;

const 文档条目标识: &str = "word/document.xml";

const 最大文档尺寸: u64 = 32 * 1024 * 1024;

fn 解压文档正文(文件路径: &str) -> Result<String, u32> {
    let 源文件 = std::fs::File::open(文件路径).map_err(|_| 错误码::内容不合法)?;
    if 源文件.metadata().map_err(|_| 错误码::内容不合法)?.len() > 最大文档尺寸 {
        return Err(错误码::内容不合法);
    }
    let mut 压缩包 = zip::ZipArchive::new(源文件).map_err(|_| 错误码::内容不合法)?;
    let 条目值 = 压缩包.by_name(文档条目标识).map_err(|_| 错误码::内容不合法)?;
    if 条目值.size() > 最大文档尺寸 { return Err(错误码::内容不合法); }
    let mut 文档正文 = String::new();
    条目值.take(最大文档尺寸 + 1).read_to_string(&mut 文档正文).map_err(|_| 错误码::内容不合法)?;
    if 文档正文.len() as u64 > 最大文档尺寸 { return Err(错误码::内容不合法); }
    Ok(文档正文)
}

pub(super) fn 生成PPTX文档(演示内容: &str, 输出路径: &str) -> Result<String, u32> {
    if 演示内容.len() > 4 * 1024 * 1024 {
        return Err(错误码::内容超限);
    }
    let 内容值: serde_json::Value =
        serde_json::from_str(演示内容).map_err(|_| 错误码::参数不合法)?;
    let 页值表 = 内容值.get("幻灯片").and_then(|值项| 值项.as_array()).ok_or(错误码::参数不合法)?;
    let 页宽磅 = 内容值.get("页宽磅").and_then(|值项| 值项.as_f64());
    let 页高磅 = 内容值.get("页高磅").and_then(|值项| 值项.as_f64());
    let mut 页表 = Vec::with_capacity(页值表.len());
    for 页值 in 页值表 {
        let 标题 = 页值.get("标题").and_then(|值项| 值项.as_str()).unwrap_or("").to_string();
        let mut 文本块 = Vec::new();
        if let Some(块值表) = 页值.get("文本块").and_then(|值项| 值项.as_array()) {
            for 块值 in 块值表 {
                let 文本 = 块值.as_str().ok_or(错误码::参数不合法)?.to_string();
                文本块.push(文本);
            }
        }
        页表.push(crate::演示文稿生成::幻灯片输入 { 标题, 文本块 });
    }
    let 字节数 = crate::演示文稿生成::生成演示文稿(页宽磅, 页高磅, &页表, 输出路径)?;
    Ok(format!(
        "{{\"输出路径\":\"{}\",\"字节数\":{},\"幻灯片数\":{}}}",
        转义文本(输出路径), 字节数, 页表.len()
    ))
}

pub(super) fn 解析PPTX文档(文件路径: &str) -> Result<String, u32> {
    if !文件路径.starts_with('/') {
        return Err(错误码::参数不合法);
    }
    let 元数据项 = std::fs::metadata(文件路径).map_err(|_| 错误码::参数不合法)?;
    if !元数据项.is_file() {
        return Err(错误码::参数不合法);
    }
    if 元数据项.len() > 64 * 1024 * 1024 {
        return Err(错误码::内容超限);
    }
    let 字节 = std::fs::read(文件路径).map_err(|_| 错误码::内容不合法)?;
    let 文稿 = crate::演示文稿解析::解析演示文稿(&字节)?;
    // EMU → 磅：1 磅 = 12700 EMU（WPS/PowerPoint 页尺寸都按这个换算）
    let 页宽磅 = (文稿.页宽 as f64 / 12700.0 * 100.0).round() / 100.0;
    let 页高磅 = (文稿.页高 as f64 / 12700.0 * 100.0).round() / 100.0;
    let mut 页表 = Vec::with_capacity(文稿.幻灯片.len());
    for 页 in &文稿.幻灯片 {
        let 块JSON: Vec<String> = 页.文本块.iter()
            .map(|块| format!("{{\"文本\":\"{}\",\"类型\":\"{}\",\"字号\":{}}}",
                              转义文本(&块.文本), 转义文本(&块.类型), 块.字号))
            .collect();
        页表.push(format!(
            "{{\"序号\":{},\"标题\":\"{}\",\"文本块\":[{}],\"块数\":{}}}",
            页.序号, 转义文本(&页.标题), 块JSON.join(","), 页.文本块.len()
        ));
    }
    Ok(format!(
        "{{\"幻灯片数\":{},\"页宽EMU\":{},\"页高EMU\":{},\"页宽磅\":{},\"页高磅\":{},\"幻灯片\":[{}]}}",
        文稿.幻灯片数, 文稿.页宽, 文稿.页高, 页宽磅, 页高磅, 页表.join(",")
    ))
}

pub(super) fn 解析DOCX文档(文件路径: &str) -> Result<String, u32> {
    let 正文JSON = crate::文档合并解析::解析增强正文(&解压文档正文(文件路径)?)?;
    let mut 解析结果: serde_json::Value = serde_json::from_str(&正文JSON).map_err(|_| 错误码::内容不合法)?;
    let 图片清单 = crate::办公资源::枚举图片资源(文件路径, "word/media/")?;
    解析结果["资源列表"] = crate::办公资源::组装资源JSON(&图片清单);
    Ok(解析结果.to_string())
}

pub(super) fn 生成DOCX文档(内容文本: &str, 输出路径: &str) -> Result<String, u32> {
    let 内容值: serde_json::Value =
        serde_json::from_str(内容文本).map_err(|_| 错误码::参数不合法)?;
    let 正文片段 = crate::文档部件::构造正文XML(&内容值)?;
    let 文档XML = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>{}<w:sectPr/></w:body></w:document>",
        正文片段
    );
    let 类型XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/><Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/></Types>";
    let 关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>";
    let 文档关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>";
    let 样式XML = crate::文档部件::构造样式XML();
    let mut 缓冲流 = std::io::Cursor::new(Vec::new());
    {
        let mut 压缩包 = zip::ZipWriter::new(&mut 缓冲流);
        let 打包参数 = zip::write::SimpleFileOptions::default();
        for (条目名, 条目内容) in [
            ("[Content_Types].xml", 类型XML),
            ("_rels/.rels", 关系XML),
            ("word/_rels/document.xml.rels", 文档关系XML),
            ("word/styles.xml", 样式XML.as_str()),
            (文档条目标识, 文档XML.as_str()),
        ] {
            压缩包.start_file(条目名, 打包参数).map_err(|_| 错误码::写出失败)?;
            压缩包.write_all(条目内容.as_bytes()).map_err(|_| 错误码::写出失败)?;
        }
        压缩包.finish().map_err(|_| 错误码::写出失败)?;
    }
    let 打包字节 = 缓冲流.into_inner();
    crate::办公资源::原子写出(输出路径, &打包字节)?;
    let 字节数 = 打包字节.len();
    Ok(format!("{{\"输出路径\":\"{}\",\"字节数\":{}}}", 转义文本(输出路径), 字节数))
}
