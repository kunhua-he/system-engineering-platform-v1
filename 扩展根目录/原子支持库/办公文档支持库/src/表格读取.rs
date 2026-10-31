use std::collections::HashMap;
use std::io::Read as 读取接口;

use calamine::{Data as 单元值, Reader as 工作簿读取接口, Xlsx as 工作簿读取器};
use quick_xml::events::{BytesStart as 起始标签, Event as 文档事件};
use quick_xml::reader::NsReader as 文档读取器;
use quick_xml::XmlVersion::Implicit1_0 as 默认XML版本;
use serde_json::{Value as 数据值, json as 构造数据};

use crate::办公资源;
use crate::编号与码面::错误码;
use crate::表格边界::{
    读取表格文件, 核矩形预算, 最大工作表数, 最大回读字节, 最大矩形格数, 最大表格列数, 最大表格行数,
};

const 合并条目上限: usize = 4096;
const XML嵌套深度上限: usize = 64;
const 部件读取字节上限: usize = 96 * 1024 * 1024;
const 工作表部件目录: &str = "xl/worksheets/";
const 数字格式条目上限: usize = 512;
const 字体条目上限: usize = 1024;
const 填充条目上限: usize = 1024;
const 单元格格式条目上限: usize = 4096;
const 关系条目上限: usize = 512;

#[derive(Clone, Copy, PartialEq, Eq)]
enum 样式区段 {
    其他区,
    字体区,
    填充区,
    数字格式区,
    单元格式区,
}

struct 字体样式 {
    是否加粗: bool,
    字号磅值: Option<f64>,
    字体名称: String,
    字体颜色: Option<String>,
}

struct 单元格式 {
    字体序位: usize,
    填充序位: usize,
    数字格式文本: Option<String>,
    水平对齐: Option<&'static str>,
    垂直对齐: Option<&'static str>,
    是否换行: bool,
}

struct 样式目录 {
    字体表: Vec<字体样式>,
    填充表: Vec<Option<String>>,
    数字格式表: HashMap<u32, String>,
    单元格式表: Vec<单元格式>,
}

struct 工作簿部件 {
    样式表: 样式目录,
    表名到路径: HashMap<String, String>,
    路径到文本: HashMap<String, String>,
}

impl 字体样式 {
    fn 缺省字体样式() -> 字体样式 {
        字体样式 {
            是否加粗: false,
            字号磅值: None,
            字体名称: String::new(),
            字体颜色: None,
        }
    }
}

impl 单元格式 {
    fn 缺省单元格式() -> 单元格式 {
        单元格式 {
            字体序位: 0,
            填充序位: 0,
            数字格式文本: None,
            水平对齐: None,
            垂直对齐: None,
            是否换行: false,
        }
    }
}

impl 样式目录 {
    fn 空白目录() -> 样式目录 {
        样式目录 {
            字体表: Vec::new(),
            填充表: Vec::new(),
            数字格式表: HashMap::new(),
            单元格式表: Vec::new(),
        }
    }
}

pub fn 解析表格(文件路径: &str) -> Result<String, u32> {
    let 文件字节 = 读取表格文件(文件路径)?;
    let 工作簿部件 = 读取工作簿部件(&文件字节)?;
    let 图片清单 = 办公资源::枚举图片资源(文件路径, "xl/media/")?;
    let 资源节点 = 办公资源::组装资源JSON(&图片清单);
    let mut 读取器 = 工作簿读取器::new(std::io::Cursor::new(文件字节)).map_err(|_| 错误码::内容不合法)?;
    let 表名清单 = 读取器.sheet_names().to_vec();
    if 表名清单.is_empty() || 表名清单.len() > 最大工作表数 { return Err(错误码::内容不合法); }
    let mut 块列表 = Vec::new();
    let mut 累计格数 = 0usize;
    let mut 累计文本字节 = 0usize;
    for (表序位, 表名文本) in 表名清单.into_iter().enumerate() {
        let 数据区域 = 读取器.worksheet_range(&表名文本).map_err(|_| 错误码::内容不合法)?;
        let 公式区域 = 读取器.worksheet_formula(&表名文本).map_err(|_| 错误码::内容不合法)?;
        let 末格位序 = match (数据区域.end(), 公式区域.end()) {
            (Some(数据末格), Some(公式末格)) => Some((数据末格.0.max(公式末格.0), 数据末格.1.max(公式末格.1))),
            (数据末格, 公式末格) => 数据末格.or(公式末格),
        };
        let mut 表格数据 = Vec::new();
        if let Some((末行位序, 末列位序)) = 末格位序 {
            核矩形预算(末行位序 as usize + 1, 末列位序 as usize + 1, &mut 累计格数, 错误码::内容不合法)?;
            for 行位序 in 0..=末行位序 {
                let mut 单行数据 = Vec::new();
                for 列位序 in 0..=末列位序 {
                    let 单元数据 = if let Some(公式文本) = 公式区域.get_value((行位序, 列位序)).filter(|公式文本| !公式文本.is_empty()) {
                        数据值::String(format!("={公式文本}"))
                    } else {
                        转换单元值(数据区域.get_value((行位序, 列位序)).unwrap_or(&单元值::Empty))?
                    };
                    if let Some(单元文本) = 单元数据.as_str() {
                        累计文本字节 = 累计文本字节.checked_add(单元文本.len()).ok_or(错误码::内容不合法)?;
                        if 累计文本字节 > 最大回读字节 { return Err(错误码::内容不合法); }
                    }
                    单行数据.push(单元数据);
                }
                表格数据.push(单行数据);
            }
        }
        let 部件路径 = 工作簿部件.表名到路径.get(&表名文本).cloned()
            .unwrap_or_else(|| format!("xl/worksheets/sheet{}.xml", 表序位 + 1));
        let (合并列表, 样式网格) = match 取部件文本(&工作簿部件, &部件路径) {
            Some(工作表文本) => 解析工作表附加(工作表文本, &工作簿部件.样式表)?,
            None => (Vec::new(), Vec::new()),
        };
        块列表.push(构造数据!({
            "类型":"工作表",
            "文本":"",
            "表格数据":表格数据,
            "来源位置":{"工作表":表名文本},
            "合并列表":合并列表,
            "样式网格":样式网格
        }));
    }
    let 返回文本 = 构造数据!({"工作表数":块列表.len(),"块列表":块列表,"资源列表":资源节点}).to_string();
    if 返回文本.len() > 最大回读字节 { return Err(错误码::内容不合法); }
    Ok(返回文本)
}

fn 转换单元值(单元数据: &单元值) -> Result<数据值, u32> {
    Ok(match 单元数据 {
        单元值::Empty => 数据值::Null,
        单元值::String(单元文本) | 单元值::DateTimeIso(单元文本) | 单元值::DurationIso(单元文本) => 数据值::String(单元文本.clone()),
        单元值::Int(整数值) => 构造数据!(整数值),
        单元值::Float(浮点值) if 浮点值.is_finite() => 构造数据!(浮点值),
        单元值::Bool(逻辑值) => 构造数据!(逻辑值),
        单元值::Error(单元错误) => 数据值::String(单元错误.to_string()),
        单元值::DateTime(日期值) => 数据值::String(日期值.as_datetime().map(|日期值|日期值.to_string().replacen(' ', "T", 1)).unwrap_or_else(||日期值.to_string())),
        _ => return Err(错误码::内容不合法),
    })
}

// 归档里只需四类部件：样式、书页、书页关系、各工作表正文；其余条目一律不读。
fn 读取工作簿部件(文件字节: &[u8]) -> Result<工作簿部件, u32> {
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

fn 取部件文本<'a>(工作簿部件: &'a 工作簿部件, 部件路径: &str) -> Option<&'a str> {
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

fn 取属性文本(标签值: &起始标签<'_>, 键名: &str) -> Option<String> {
    for 属性结果 in 标签值.attributes() {
        let 属性项 = 属性结果.ok()?;
        if 属性项.key.local_name().as_ref() == 键名 {
            return 属性项.normalized_value(默认XML版本).ok().map(|文本值| 文本值.into_owned());
        }
    }
    None
}

fn 取开关属性(标签值: &起始标签<'_>) -> Result<bool, u32> {
    match 取属性文本(标签值, "val") {
        None => Ok(true),
        Some(取值文本) => Ok(!(取值文本 == "0" || 取值文本.eq_ignore_ascii_case("false"))),
    }
}

fn 转换颜色文本(颜色文本: &str) -> Option<String> {
    let 大写文本 = 颜色文本.trim().trim_start_matches('#').to_ascii_uppercase();
    let 十六进制位 = if 大写文本.len() == 8 {
        &大写文本[2..]
    } else if 大写文本.len() == 6 {
        大写文本.as_str()
    } else {
        return None;
    };
    if !十六进制位.bytes().all(|单字节| 单字节.is_ascii_hexdigit()) { return None; }
    Some(format!("#{十六进制位}"))
}

fn 转换水平对齐(对齐文本: &str) -> Option<&'static str> {
    match 对齐文本.trim() {
        "left" => Some("左"),
        "center" => Some("中"),
        "right" => Some("右"),
        "justify" => Some("两端"),
        "distributed" => Some("分散"),
        "fill" => Some("填充"),
        "centerContinuous" => Some("跨列居中"),
        _ => None,
    }
}

fn 转换垂直对齐(对齐文本: &str) -> Option<&'static str> {
    match 对齐文本.trim() {
        "top" => Some("上"),
        "center" => Some("中"),
        "bottom" => Some("下"),
        "justify" => Some("两端"),
        "distributed" => Some("分散"),
        _ => None,
    }
}

fn 转换内置数字格式(格式号: u32) -> Option<&'static str> {
    Some(match 格式号 {
        1 => "0",
        2 => "0.00",
        3 => "#,##0",
        4 => "#,##0.00",
        9 => "0%",
        10 => "0.00%",
        11 => "0.00E+00",
        12 => "# ?/?",
        13 => "# ??/??",
        14 => "yyyy-mm-dd",
        15 => "d-mmm-yy",
        16 => "d-mmm",
        17 => "mmm-yy",
        18 => "h:mm AM/PM",
        19 => "h:mm:ss AM/PM",
        20 => "h:mm",
        21 => "h:mm:ss",
        22 => "yyyy-mm-dd h:mm",
        37 => "#,##0 ;(#,##0)",
        38 => "#,##0 ;[Red](#,##0)",
        39 => "#,##0.00;(#,##0.00)",
        40 => "#,##0.00;[Red](#,##0.00)",
        45 => "mm:ss",
        46 => "[h]:mm:ss",
        47 => "mm:ss.0",
        48 => "##0.0E+0",
        49 => "@",
        _ => return None,
    })
}

fn 解析单元坐标(引用文本: &str) -> Result<(usize, usize), u32> {
    let 首段文本 = 引用文本.split(':').next().unwrap_or(引用文本);
    let mut 列号值 = 0usize;
    let mut 行号拼文 = String::new();
    for 单字节 in 首段文本.bytes() {
        if 单字节 == b'$' {
            continue;
        } else if 单字节.is_ascii_uppercase() && 行号拼文.is_empty() {
            列号值 = 列号值
                .checked_mul(26)
                .and_then(|列号值| 列号值.checked_add((单字节 - b'A' + 1) as usize))
                .ok_or(错误码::内容不合法)?;
        } else if 单字节.is_ascii_digit() {
            行号拼文.push(单字节 as char);
        } else {
            return Err(错误码::内容不合法);
        }
    }
    let 行号值 = 行号拼文.parse::<usize>().map_err(|_| 错误码::内容不合法)?;
    if 列号值 == 0 || 行号值 == 0 { return Err(错误码::内容不合法); }
    Ok((行号值 - 1, 列号值 - 1))
}

fn 解析样式表(样式文本: &str) -> Result<样式目录, u32> {
    let mut 目录值 = 样式目录::空白目录();
    let mut 读取器 = 文档读取器::from_str(样式文本);
    读取器.config_mut().expand_empty_elements = true;
    let mut 嵌套深度 = 0usize;
    let mut 根节点数 = 0usize;
    let mut 区段 = 样式区段::其他区;
    let mut 字体节点内 = false;
    let mut 待定字体 = 字体样式::缺省字体样式();
    let mut 填充节点内 = false;
    let mut 待定填充色: Option<String> = None;
    let mut 格式节点内 = false;
    let mut 待定格式 = 单元格式::缺省单元格式();
    let mut 待定数字格式号 = 0u32;
    loop {
        let 事件值 = 读取器.read_event().map_err(|_| 错误码::内容不合法)?;
        match 事件值 {
            文档事件::Start(标签值) | 文档事件::Empty(标签值) => {
                嵌套深度 += 1;
                if 嵌套深度 > XML嵌套深度上限 { return Err(错误码::内容不合法); }
                let 标签名称 = 标签值.local_name();
                let 节点名称 = 标签名称.as_ref();
                if 嵌套深度 == 1 {
                    根节点数 += 1;
                    if 根节点数 != 1 || 节点名称 != "styleSheet" { return Err(错误码::内容不合法); }
                    continue;
                }
                if 嵌套深度 == 2 {
                    区段 = match 节点名称 {
                        "fonts" => 样式区段::字体区,
                        "fills" => 样式区段::填充区,
                        "numFmts" => 样式区段::数字格式区,
                        "cellXfs" => 样式区段::单元格式区,
                        _ => 样式区段::其他区,
                    };
                    continue;
                }
                match 区段 {
                    样式区段::字体区 => {
                        if 节点名称 == "font" {
                            待定字体 = 字体样式::缺省字体样式();
                            字体节点内 = true;
                        } else if 字体节点内 {
                            match 节点名称 {
                                "b" => 待定字体.是否加粗 = 取开关属性(&标签值)?,
                                "sz" => {
                                    待定字体.字号磅值 = 取属性文本(&标签值, "val")
                                        .and_then(|文本值| 文本值.trim().parse::<f64>().ok())
                                        .filter(|字号值| 字号值.is_finite() && *字号值 > 0.0);
                                }
                                "name" => 待定字体.字体名称 = 取属性文本(&标签值, "val").unwrap_or_default(),
                                "color" => {
                                    待定字体.字体颜色 = 取属性文本(&标签值, "rgb")
                                        .and_then(|颜色文本| 转换颜色文本(&颜色文本));
                                }
                                _ => {}
                            }
                        }
                    }
                    样式区段::填充区 => {
                        if 节点名称 == "fill" {
                            待定填充色 = None;
                            填充节点内 = true;
                        } else if 填充节点内 && 节点名称 == "fgColor" {
                            待定填充色 = 取属性文本(&标签值, "rgb").and_then(|颜色文本| 转换颜色文本(&颜色文本));
                        }
                    }
                    样式区段::数字格式区 => {
                        if 节点名称 == "numFmt" {
                            let 格式号文本 = 取属性文本(&标签值, "numFmtId").ok_or(错误码::内容不合法)?;
                            let 格式号 = 格式号文本.trim().parse::<u32>().map_err(|_| 错误码::内容不合法)?;
                            let 格式码 = 取属性文本(&标签值, "formatCode").unwrap_or_default();
                            if 格式码.chars().count() > 256 { return Err(错误码::内容超限); }
                            if 目录值.数字格式表.len() >= 数字格式条目上限 { return Err(错误码::内容超限); }
                            目录值.数字格式表.insert(格式号, 格式码);
                        }
                    }
                    样式区段::单元格式区 => {
                        if 节点名称 == "xf" {
                            待定格式 = 单元格式::缺省单元格式();
                            待定数字格式号 = 取属性文本(&标签值, "numFmtId")
                                .and_then(|文本值| 文本值.trim().parse::<u32>().ok())
                                .unwrap_or(0);
                            待定格式.字体序位 = 取属性文本(&标签值, "fontId")
                                .and_then(|文本值| 文本值.trim().parse::<usize>().ok())
                                .unwrap_or(0);
                            待定格式.填充序位 = 取属性文本(&标签值, "fillId")
                                .and_then(|文本值| 文本值.trim().parse::<usize>().ok())
                                .unwrap_or(0);
                            格式节点内 = true;
                        } else if 格式节点内 && 节点名称 == "alignment" {
                            if let Some(对齐文本) = 取属性文本(&标签值, "horizontal") {
                                待定格式.水平对齐 = 转换水平对齐(&对齐文本);
                            }
                            if let Some(对齐文本) = 取属性文本(&标签值, "vertical") {
                                待定格式.垂直对齐 = 转换垂直对齐(&对齐文本);
                            }
                            if let Some(开关文本) = 取属性文本(&标签值, "wrapText") {
                                待定格式.是否换行 = 开关文本 == "1" || 开关文本.eq_ignore_ascii_case("true");
                            }
                        }
                    }
                    样式区段::其他区 => {}
                }
            }
            文档事件::End(标签值) => {
                let 标签名称 = 标签值.local_name();
                let 节点名称 = 标签名称.as_ref();
                if 嵌套深度 == 3 {
                    if 区段 == 样式区段::字体区 && 节点名称 == "font" && 字体节点内 {
                        if 目录值.字体表.len() >= 字体条目上限 { return Err(错误码::内容超限); }
                        目录值.字体表.push(std::mem::replace(&mut 待定字体, 字体样式::缺省字体样式()));
                        字体节点内 = false;
                    } else if 区段 == 样式区段::填充区 && 节点名称 == "fill" && 填充节点内 {
                        if 目录值.填充表.len() >= 填充条目上限 { return Err(错误码::内容超限); }
                        目录值.填充表.push(待定填充色.take());
                        填充节点内 = false;
                    } else if 区段 == 样式区段::单元格式区 && 节点名称 == "xf" && 格式节点内 {
                        if 目录值.单元格式表.len() >= 单元格格式条目上限 { return Err(错误码::内容超限); }
                        待定格式.数字格式文本 = if 待定数字格式号 == 0 {
                            None
                        } else {
                            目录值.数字格式表.get(&待定数字格式号).cloned().or_else(|| {
                                转换内置数字格式(待定数字格式号).map(|文本值| 文本值.to_string())
                            })
                        };
                        目录值.单元格式表.push(std::mem::replace(&mut 待定格式, 单元格式::缺省单元格式()));
                        格式节点内 = false;
                    }
                }
                嵌套深度 = 嵌套深度.checked_sub(1).ok_or(错误码::内容不合法)?;
            }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    if 嵌套深度 != 0 || 根节点数 != 1 { return Err(错误码::内容不合法); }
    Ok(目录值)
}

fn 解析工作表附加(工作表文本: &str, 样式表: &样式目录) -> Result<(Vec<数据值>, Vec<数据值>), u32> {
    let mut 读取器 = 文档读取器::from_str(工作表文本);
    读取器.config_mut().expand_empty_elements = true;
    let mut 嵌套深度 = 0usize;
    let mut 根节点数 = 0usize;
    let mut 合并列表: Vec<数据值> = Vec::new();
    let mut 样式网格: Vec<数据值> = Vec::new();
    loop {
        let 事件值 = 读取器.read_event().map_err(|_| 错误码::内容不合法)?;
        match 事件值 {
            文档事件::Start(标签值) | 文档事件::Empty(标签值) => {
                嵌套深度 += 1;
                if 嵌套深度 > XML嵌套深度上限 { return Err(错误码::内容不合法); }
                let 标签名称 = 标签值.local_name();
                let 节点名称 = 标签名称.as_ref();
                if 嵌套深度 == 1 {
                    根节点数 += 1;
                    if 根节点数 != 1 || 节点名称 != "worksheet" { return Err(错误码::内容不合法); }
                    continue;
                }
                if 节点名称 == "c" {
                    let 格位文本 = 取属性文本(&标签值, "r");
                    let 格式序文本 = 取属性文本(&标签值, "s");
                    if let (Some(格位文本), Some(格式序文本)) = (格位文本, 格式序文本) {
                        if let Ok(格式序位) = 格式序文本.trim().parse::<usize>() {
                            if 格式序位 > 0 {
                                let (行序位, 列序位) = 解析单元坐标(&格位文本)?;
                                if 行序位 < 最大表格行数 && 列序位 < 最大表格列数 {
                                    if let Some(样式项) = 组装样式格(行序位, 列序位, 格式序位, 样式表) {
                                        if 样式网格.len() >= 最大矩形格数 { return Err(错误码::内容超限); }
                                        样式网格.push(样式项);
                                    }
                                }
                            }
                        }
                    }
                } else if 节点名称 == "mergeCell" {
                    if let Some(区域文本) = 取属性文本(&标签值, "ref") {
                        if 合并列表.len() >= 合并条目上限 { return Err(错误码::内容超限); }
                        合并列表.push(组装合并项(&区域文本)?);
                    }
                }
            }
            文档事件::End(_) => { 嵌套深度 = 嵌套深度.checked_sub(1).ok_or(错误码::内容不合法)?; }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    if 嵌套深度 != 0 || 根节点数 != 1 { return Err(错误码::内容不合法); }
    Ok((合并列表, 样式网格))
}

fn 组装合并项(区域文本: &str) -> Result<数据值, u32> {
    let mut 分段遍历 = 区域文本.splitn(2, ':');
    let 首段文本 = 分段遍历.next().ok_or(错误码::内容不合法)?;
    let 末段文本 = 分段遍历.next().ok_or(错误码::内容不合法)?;
    let (首行位序, 首列位序) = 解析单元坐标(首段文本)?;
    let (末行位序, 末列位序) = 解析单元坐标(末段文本)?;
    if 末行位序 < 首行位序 || 末列位序 < 首列位序 { return Err(错误码::内容不合法); }
    Ok(构造数据!({
        "区域":区域文本,
        "起始行":首行位序,
        "起始列":首列位序,
        "行跨度":末行位序 - 首行位序 + 1,
        "列跨度":末列位序 - 首列位序 + 1
    }))
}

fn 组装样式格(行序位: usize, 列序位: usize, 格式序位: usize, 样式表: &样式目录) -> Option<数据值> {
    if 格式序位 == 0 { return None; }
    let 格式项 = 样式表.单元格式表.get(格式序位)?;
    let 字体项 = 样式表.字体表.get(格式项.字体序位);
    let 基准字体 = 样式表.字体表.first();
    let 是否加粗 = 字体项.map(|字体项| 字体项.是否加粗).unwrap_or(false);
    let 字号磅值 = 字体项.and_then(|字体项| 字体项.字号磅值);
    let 字体名称 = 字体项.map(|字体项| 字体项.字体名称.clone()).unwrap_or_default();
    let 字体颜色 = 字体项.and_then(|字体项| 字体项.字体颜色.clone());
    let 填充色 = 样式表.填充表.get(格式项.填充序位).and_then(|填充项| 填充项.clone());
    let 基准字号 = 基准字体.and_then(|字体项| 字体项.字号磅值);
    let 基准字体名 = 基准字体.map(|字体项| 字体项.字体名称.as_str()).unwrap_or("");
    let 字体名可见 = !字体名称.is_empty() && 字体名称 != 基准字体名;
    let 字号可见 = match (字号磅值, 基准字号) {
        (Some(字号值), Some(基准值)) => (字号值 - 基准值).abs() > 0.001,
        (Some(_), None) => true,
        _ => false,
    };
    let 数字格式文本 = 格式项
        .数字格式文本
        .as_deref()
        .filter(|格式文本| !格式文本.is_empty() && *格式文本 != "General" && *格式文本 != "常规")
        .map(|格式文本| 格式文本.to_string());
    let 可见样式 = 是否加粗
        || 字体名可见
        || 字号可见
        || 字体颜色.is_some()
        || 填充色.is_some()
        || 格式项.水平对齐.is_some()
        || 格式项.垂直对齐.is_some()
        || 格式项.是否换行
        || 数字格式文本.is_some();
    if !可见样式 { return None; }
    let mut 样式节点 = 构造数据!({"行":行序位,"列":列序位,"加粗":是否加粗,"自动换行":格式项.是否换行});
    if let Some(字号值) = 字号磅值 { 样式节点["字号"] = 构造数据!(字号值); }
    if !字体名称.is_empty() { 样式节点["字体"] = 数据值::String(字体名称); }
    if let Some(颜色文本) = 字体颜色 { 样式节点["字体颜色"] = 数据值::String(颜色文本); }
    if let Some(颜色文本) = 填充色 { 样式节点["填充色"] = 数据值::String(颜色文本); }
    if let Some(对齐文本) = 格式项.水平对齐 { 样式节点["水平对齐"] = 数据值::String(对齐文本.to_string()); }
    if let Some(对齐文本) = 格式项.垂直对齐 { 样式节点["垂直对齐"] = 数据值::String(对齐文本.to_string()); }
    if let Some(格式文本) = 数字格式文本 { 样式节点["数字格式"] = 数据值::String(格式文本); }
    Some(样式节点)
}