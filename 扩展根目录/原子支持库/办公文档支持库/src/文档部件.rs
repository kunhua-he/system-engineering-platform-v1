use quick_xml::escape::escape as 转义XML;

use crate::编号与码面::错误码;

fn 取样式项(容器值: &serde_json::Value) -> serde_json::Value {
    let mut 样式集合 = match 容器值.get("样式").and_then(|值项| 值项.as_object()) {
        Some(样式对象) => 样式对象.clone(),
        None => serde_json::Map::new(),
    };
    for 键名 in ["加粗", "字号", "颜色", "字体", "对齐", "垂直对齐", "底色"] {
        if let Some(键值项) = 容器值.get(键名) {
            样式集合.insert(键名.to_string(), 键值项.clone());
        }
    }
    serde_json::Value::Object(样式集合)
}

fn 是十六进制颜色(颜色文本: &str) -> bool {
    let 去前缀 = 颜色文本.trim().trim_start_matches('#');
    去前缀.len() == 6 && 去前缀.bytes().all(|单字节| 单字节.is_ascii_hexdigit())
}

fn 段落XML(段落拼文: &str, 段落式名: &str, 段落样式项: &serde_json::Value) -> String {
    let mut 段属性拼文 = String::new();
    if !段落式名.is_empty() {
        段属性拼文.push_str(&format!("<w:pStyle w:val=\"{}\"/>", 转义XML(段落式名)));
    }
    if let Some(对齐值) = 段落样式项.get("对齐").and_then(|值项| 值项.as_str()) {
        let 对齐码 = match 对齐值 {
            "左" | "left" => Some("left"),
            "居中" | "center" => Some("center"),
            "右" | "right" => Some("right"),
            "两端" | "both" | "justify" => Some("both"),
            _ => None,
        };
        if let Some(码值) = 对齐码 {
            段属性拼文.push_str(&format!("<w:jc w:val=\"{}\"/>", 码值));
        }
    }
    let 段属性片段 = if 段属性拼文.is_empty() {
        String::new()
    } else {
        format!("<w:pPr>{}</w:pPr>", 段属性拼文)
    };
    let mut 字属性拼文 = String::new();
    if 段落样式项.get("加粗").and_then(|值项| 值项.as_bool()).unwrap_or(false) {
        字属性拼文.push_str("<w:b/><w:bCs/>");
    }
    if let Some(字号磅值) = 段落样式项.get("字号").and_then(|值项| 值项.as_f64()) {
        let 半磅值 = (字号磅值 * 2.0).round().clamp(2.0, 3276.0) as u32;
        字属性拼文.push_str(&format!("<w:sz w:val=\"{}\"/><w:szCs w:val=\"{}\"/>", 半磅值, 半磅值));
    }
    if let Some(颜色值) = 段落样式项.get("颜色").and_then(|值项| 值项.as_str()) {
        if 是十六进制颜色(颜色值) {
            字属性拼文.push_str(&format!("<w:color w:val=\"{}\"/>", 颜色值.trim_start_matches('#')));
        }
    }
    if let Some(字体值) = 段落样式项.get("字体").and_then(|值项| 值项.as_str()) {
        let 字体转义 = 转义XML(字体值);
        字属性拼文.push_str(&format!(
            "<w:rFonts w:ascii=\"{}\" w:eastAsia=\"{}\" w:hAnsi=\"{}\"/>",
            字体转义, 字体转义, 字体转义
        ));
    }
    let 字属性片段 = if 字属性拼文.is_empty() {
        String::new()
    } else {
        format!("<w:rPr>{}</w:rPr>", 字属性拼文)
    };
    format!(
        "<w:p>{}<w:r>{}<w:t xml:space=\"preserve\">{}</w:t></w:r></w:p>",
        段属性片段,
        字属性片段,
        转义XML(段落拼文)
    )
}

struct 单元格外形 {
    格内文本: String,
    横跨列数: usize,
    纵跨行数: usize,
    样式项: serde_json::Value,
}

fn 读取单元格(单格值: &serde_json::Value) -> Result<单元格外形, u32> {
    if let Some(格文本) = 单格值.as_str() {
        return Ok(单元格外形 {
            格内文本: 格文本.to_string(),
            横跨列数: 1,
            纵跨行数: 1,
            样式项: serde_json::json!({}),
        });
    }
    if !单格值.is_object() {
        return Err(错误码::参数不合法);
    }
    let 格内文本 = 单格值.get("文本").and_then(|值项| 值项.as_str()).unwrap_or("").to_string();
    let 横跨数 = 单格值.get("横跨").and_then(|值项| 值项.as_u64()).unwrap_or(1);
    let 纵跨数 = 单格值.get("纵跨").and_then(|值项| 值项.as_u64()).unwrap_or(1);
    if 横跨数 == 0 || 纵跨数 == 0 || 横跨数 > 64 || 纵跨数 > 256 {
        return Err(错误码::参数不合法);
    }
    Ok(单元格外形 {
        格内文本,
        横跨列数: 横跨数 as usize,
        纵跨行数: 纵跨数 as usize,
        样式项: 取样式项(单格值),
    })
}

fn 空单元格外形() -> 单元格外形 {
    单元格外形 {
        格内文本: String::new(),
        横跨列数: 1,
        纵跨行数: 1,
        样式项: serde_json::json!({}),
    }
}

fn 单元格XML(格外形: &单元格外形, 实横跨数: usize, 是否纵向延续: bool) -> String {
    let mut 格属性拼文 = String::new();
    if 是否纵向延续 {
        格属性拼文.push_str("<w:vMerge/>");
    } else {
        if 实横跨数 > 1 {
            格属性拼文.push_str(&format!("<w:gridSpan w:val=\"{}\"/>", 实横跨数));
        }
        if 格外形.纵跨行数 > 1 {
            格属性拼文.push_str("<w:vMerge w:val=\"restart\"/>");
        }
    }
    if let Some(底色值) = 格外形.样式项.get("底色").and_then(|值项| 值项.as_str()) {
        if 是十六进制颜色(底色值) {
            格属性拼文.push_str(&format!(
                "<w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"{}\"/>",
                底色值.trim_start_matches('#')
            ));
        }
    }
    if let Some(垂直值) = 格外形.样式项.get("垂直对齐").and_then(|值项| 值项.as_str()) {
        let 垂直码 = match 垂直值 {
            "上" | "top" => Some("top"),
            "中" | "center" => Some("center"),
            "下" | "bottom" => Some("bottom"),
            _ => None,
        };
        if let Some(码值) = 垂直码 {
            格属性拼文.push_str(&format!("<w:vAlign w:val=\"{}\"/>", 码值));
        }
    }
    let 格属性片段 = if 格属性拼文.is_empty() {
        String::new()
    } else {
        format!("<w:tcPr>{}</w:tcPr>", 格属性拼文)
    };
    let 段落段 = 段落XML(&格外形.格内文本, "Normal", &格外形.样式项);
    format!("<w:tc>{}{}</w:tc>", 格属性片段, 段落段)
}

pub(crate) fn 构造正文XML(内容值: &serde_json::Value) -> Result<String, u32> {
    if 内容值.get("段落").is_some() || 内容值.get("表格").is_some() { return Err(错误码::参数不合法); }
    let 块表值 = 内容值.get("块列表").and_then(|条目值| 条目值.as_array()).ok_or(错误码::参数不合法)?;
    let mut 正文片段 = String::new();
    for 单个块 in 块表值 {
        let 块类型 = 单个块.get("类型").and_then(|条目值| 条目值.as_str()).ok_or(错误码::参数不合法)?;
        match 块类型 {
            "段落" | "标题" => {
                let 段落拼文 = 单个块.get("文本").and_then(|条目值| 条目值.as_str()).ok_or(错误码::参数不合法)?;
                let 段落样式项 = 取样式项(单个块);
                let 段落式名 = if 块类型 == "标题" {
                    let 层级值 = match 单个块.get("层级") {
                        Some(条目值) => 条目值.as_u64().ok_or(错误码::参数不合法)?,
                        None => 1,
                    };
                    if !(1..=6).contains(&层级值) { return Err(错误码::参数不合法); }
                    format!("Heading{}", 层级值)
                } else {
                    "Normal".to_string()
                };
                正文片段.push_str(&段落XML(段落拼文, &段落式名, &段落样式项));
            }
            "表格" => {
                let 行表值 = 单个块.get("表格数据").and_then(|条目值| 条目值.as_array()).ok_or(错误码::参数不合法)?;
                if 行表值.is_empty() { return Err(错误码::参数不合法); }
                let 最大列数 = 行表值
                    .iter()
                    .filter_map(|单行| 单行.as_array())
                    .map(|格表值| 格表值.len())
                    .max()
                    .unwrap_or(0);
                if 最大列数 == 0 || 最大列数 > 64 { return Err(错误码::参数不合法); }
                正文片段.push_str("<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/></w:tblPr><w:tblGrid>");
                for _ in 0..最大列数 { 正文片段.push_str("<w:gridCol w:w=\"2400\"/>"); }
                正文片段.push_str("</w:tblGrid>");
                let mut 纵跨余量表: std::collections::HashMap<usize, usize> = std::collections::HashMap::new();
                for 单行 in 行表值 {
                    let 格表值 = 单行.as_array().ok_or(错误码::参数不合法)?;
                    if 格表值.is_empty() { return Err(错误码::参数不合法); }
                    正文片段.push_str("<w:tr>");
                    let mut 列序位 = 0usize;
                    for 单格 in 格表值 {
                        if 列序位 >= 最大列数 { return Err(错误码::参数不合法); }
                        let 剩余纵跨 = 纵跨余量表.get(&列序位).copied().unwrap_or(0);
                        if 剩余纵跨 > 0 {
                            if 剩余纵跨 > 1 {
                                纵跨余量表.insert(列序位, 剩余纵跨 - 1);
                            } else {
                                纵跨余量表.remove(&列序位);
                            }
                            let 延续格 = 空单元格外形();
                            正文片段.push_str(&单元格XML(&延续格, 1, true));
                            列序位 += 1;
                            continue;
                        }
                        let 格外形 = 读取单元格(单格)?;
                        let 实横跨 = 格外形.横跨列数.min(最大列数 - 列序位);
                        if 格外形.纵跨行数 > 1 {
                            纵跨余量表.insert(列序位, 格外形.纵跨行数 - 1);
                        }
                        正文片段.push_str(&单元格XML(&格外形, 实横跨, false));
                        列序位 += 实横跨;
                    }
                    while 列序位 < 最大列数 {
                        let 剩余纵跨 = 纵跨余量表.get(&列序位).copied().unwrap_or(0);
                        let 空外形 = 空单元格外形();
                        if 剩余纵跨 > 0 {
                            if 剩余纵跨 > 1 {
                                纵跨余量表.insert(列序位, 剩余纵跨 - 1);
                            } else {
                                纵跨余量表.remove(&列序位);
                            }
                            正文片段.push_str(&单元格XML(&空外形, 1, true));
                        } else {
                            正文片段.push_str(&单元格XML(&空外形, 1, false));
                        }
                        列序位 += 1;
                    }
                    正文片段.push_str("</w:tr>");
                }
                正文片段.push_str("</w:tbl>");
            }
            _ => return Err(错误码::参数不合法),
        }
    }
    Ok(正文片段)
}

pub(crate) fn 构造样式XML() -> String {
    let mut 样式正文 = String::from(r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体" w:hAnsi="Times New Roman"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>"#);
    for (层级位置, 字号值) in [36, 32, 28, 26, 24, 22].iter().enumerate() {
        样式正文.push_str(&format!(r#"<w:style w:type="paragraph" w:styleId="Heading{}"><w:name w:val="heading {}"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:outlineLvl w:val="{}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{}"/><w:szCs w:val="{}"/></w:rPr></w:style>"#, 层级位置 + 1, 层级位置 + 1, 层级位置, 字号值, 字号值));
    }
    样式正文.push_str("</w:styles>");
    样式正文
}
