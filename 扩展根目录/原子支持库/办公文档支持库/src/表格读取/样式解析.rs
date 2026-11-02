//! 样式表解析：styles.xml → 字体 / 填充 / 数字格式 / 单元格格式四张表，
//! 并把颜色文本、对齐取值、内置数字格式归一到本库口径。

use std::collections::HashMap;

use quick_xml::events::Event as 文档事件;
use quick_xml::reader::NsReader as 文档读取器;

use crate::编号与码面::错误码;

use super::基础件::{取属性文本, 取开关属性, XML嵌套深度上限};

const 数字格式条目上限: usize = 512;
const 字体条目上限: usize = 1024;
const 填充条目上限: usize = 1024;
const 单元格格式条目上限: usize = 4096;

#[derive(Clone, Copy, PartialEq, Eq)]
enum 样式区段 {
    其他区,
    字体区,
    填充区,
    数字格式区,
    单元格式区,
}

pub(super) struct 字体样式 {
    pub(super) 是否加粗: bool,
    pub(super) 字号磅值: Option<f64>,
    pub(super) 字体名称: String,
    pub(super) 字体颜色: Option<String>,
}

pub(super) struct 单元格式 {
    pub(super) 字体序位: usize,
    pub(super) 填充序位: usize,
    pub(super) 数字格式文本: Option<String>,
    pub(super) 水平对齐: Option<&'static str>,
    pub(super) 垂直对齐: Option<&'static str>,
    pub(super) 是否换行: bool,
}

pub(super) struct 样式目录 {
    pub(super) 字体表: Vec<字体样式>,
    pub(super) 填充表: Vec<Option<String>>,
    数字格式表: HashMap<u32, String>,
    pub(super) 单元格式表: Vec<单元格式>,
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
    pub(super) fn 空白目录() -> 样式目录 {
        样式目录 {
            字体表: Vec::new(),
            填充表: Vec::new(),
            数字格式表: HashMap::new(),
            单元格式表: Vec::new(),
        }
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

pub(super) fn 解析样式表(样式文本: &str) -> Result<样式目录, u32> {
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
