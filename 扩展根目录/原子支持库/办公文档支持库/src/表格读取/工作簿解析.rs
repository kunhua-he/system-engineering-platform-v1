//! 工作簿容器解析：从 zip 归档里只取四类部件（styles / workbook / rels / worksheets），
//! 再由 workbook.xml ↔ workbook.xml.rels 得到 表名→部件路径 映射。

use std::collections::HashMap;
use std::io::Read as 读取接口;

use quick_xml::events::Event as 文档事件;
use quick_xml::reader::NsReader as 文档读取器;

use crate::编号与码面::错误码;
use crate::办公资源;
use crate::表格边界::最大工作表数;

use super::基础件::{取属性文本, XML嵌套深度上限};
use super::样式解析::{解析样式表, 样式目录};

const 部件读取字节上限: usize = 96 * 1024 * 1024;
const 工作表部件目录: &str = "xl/worksheets/";
const 关系条目上限: usize = 512;

pub(super) struct 工作簿部件 {
    pub(super) 样式表: 样式目录,
    pub(super) 表名到路径: HashMap<String, String>,
    路径到文本: HashMap<String, String>,
}

// 归档里只需四类部件：样式、书页、书页关系、各工作表正文；其余条目一律不读。
pub(super) fn 读取工作簿部件(文件字节: &[u8]) -> Result<工作簿部件, u32> {
    let mut 归档句柄 = zip::ZipArchive::new(std::io::Cursor::new(文件字节)).map_err(|_| 错误码::内容不合法)?;
    if 归档句柄.len() > 办公资源::归档条目上限 { return Err(错误码::内容超限); }
    let mut 路径到文本: HashMap<String, String> = HashMap::new();
    let mut 累计字节 = 0usize;
    for 条目序位 in 0..归档句柄.len() {
        let 条目句柄 = 归档句柄.by_index(条目序位).map_err(|_| 错误码::内容不合法)?;
        if 条目句柄.is_dir() { continue; }
        let 条目名称 = 条目句柄.name().map_err(|_| 错误码::内容不合法)?.into_owned();
        let 小写名称 = 条目名称.to_ascii_lowercase();
        let 需要读取 = 小写名称 == "xl/styles.xml"
            || 小写名称 == "xl/workbook.xml"
            || 小写名称 == "xl/_rels/workbook.xml.rels"
            || 小写名称.starts_with(工作表部件目录);
        if !需要读取 { continue; }
        let 条目大小 = 条目句柄.size() as usize;
        累计字节 = 累计字节.checked_add(条目大小).ok_or(错误码::内容超限)?;
        if 累计字节 > 部件读取字节上限 { return Err(错误码::内容超限); }
        let mut 原始字节 = Vec::new();
        条目句柄
            .take(条目大小 as u64 + 1)
            .read_to_end(&mut 原始字节)
            .map_err(|_| 错误码::内容不合法)?;
        if 原始字节.len() > 条目大小 { return Err(错误码::内容不合法); }
        let 文本值 = String::from_utf8(原始字节).map_err(|_| 错误码::内容不合法)?;
        路径到文本.insert(小写名称, 文本值);
    }
    let 样式表 = match 路径到文本.get("xl/styles.xml") {
        Some(样式文本) => 解析样式表(样式文本)?,
        None => 样式目录::空白目录(),
    };
    let 表名到路径 = match (路径到文本.get("xl/workbook.xml"), 路径到文本.get("xl/_rels/workbook.xml.rels")) {
        (Some(工作簿文本), Some(关系文本)) => 解析工作簿映射(工作簿文本, 关系文本)?,
        _ => HashMap::new(),
    };
    Ok(工作簿部件 { 样式表, 表名到路径, 路径到文本 })
}

pub(super) fn 取部件文本<'a>(工作簿部件: &'a 工作簿部件, 部件路径: &str) -> Option<&'a str> {
    工作簿部件.路径到文本.get(&部件路径.to_ascii_lowercase()).map(|文本值| 文本值.as_str())
}

fn 解析工作簿映射(工作簿文本: &str, 关系文本: &str) -> Result<HashMap<String, String>, u32> {
    let mut 关系目标表: HashMap<String, String> = HashMap::new();
    let mut 读取器 = 文档读取器::from_str(关系文本);
    读取器.config_mut().expand_empty_elements = true;
    let mut 嵌套深度 = 0usize;
    loop {
        let 事件值 = 读取器.read_event().map_err(|_| 错误码::内容不合法)?;
        match 事件值 {
            文档事件::Start(标签值) | 文档事件::Empty(标签值) => {
                嵌套深度 += 1;
                if 嵌套深度 > XML嵌套深度上限 { return Err(错误码::内容不合法); }
                let 标签名称 = 标签值.local_name();
                if 标签名称.as_ref() == "Relationship" {
                    let 外部标记 = 取属性文本(&标签值, "TargetMode")
                        .map(|模式文本| 模式文本.eq_ignore_ascii_case("External"))
                        .unwrap_or(false);
                    if let (Some(关系号), Some(目标文本)) = (取属性文本(&标签值, "Id"), 取属性文本(&标签值, "Target")) {
                        if !外部标记 {
                            if 关系目标表.len() >= 关系条目上限 { return Err(错误码::内容超限); }
                            关系目标表.insert(关系号, 目标文本);
                        }
                    }
                }
            }
            文档事件::End(_) => { 嵌套深度 = 嵌套深度.checked_sub(1).ok_or(错误码::内容不合法)?; }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    let mut 表名到路径 = HashMap::new();
    let mut 书页读取器 = 文档读取器::from_str(工作簿文本);
    书页读取器.config_mut().expand_empty_elements = true;
    let mut 书页深度 = 0usize;
    loop {
        let 事件值 = 书页读取器.read_event().map_err(|_| 错误码::内容不合法)?;
        match 事件值 {
            文档事件::Start(标签值) | 文档事件::Empty(标签值) => {
                书页深度 += 1;
                if 书页深度 > XML嵌套深度上限 { return Err(错误码::内容不合法); }
                let 标签名称 = 标签值.local_name();
                if 标签名称.as_ref() == "sheet" {
                    if let (Some(表名文本), Some(关系号)) = (取属性文本(&标签值, "name"), 取属性文本(&标签值, "id")) {
                        if let Some(目标文本) = 关系目标表.get(&关系号) {
                            if 表名到路径.len() >= 最大工作表数 { return Err(错误码::内容超限); }
                            表名到路径.insert(表名文本, 规范化部件路径(目标文本)?);
                        }
                    }
                }
            }
            文档事件::End(_) => { 书页深度 = 书页深度.checked_sub(1).ok_or(错误码::内容不合法)?; }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    Ok(表名到路径)
}

fn 规范化部件路径(目标文本: &str) -> Result<String, u32> {
    let 修剪文本 = 目标文本.trim().trim_start_matches('/');
    if 修剪文本.is_empty() || 修剪文本.contains("..") { return Err(错误码::内容不合法); }
    if 修剪文本.starts_with("xl/") { Ok(修剪文本.to_string()) } else { Ok(format!("xl/{修剪文本}")) }
}
