use crate::编号与码面::错误码;
use quick_xml::events::Event as 文档事件;
use quick_xml::name::ResolveResult as 命名空间结果;
use quick_xml::reader::NsReader as 文档读取器;
use quick_xml::XmlVersion::Implicit1_0 as 默认XML版本;

const 正文命名空间: &str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

pub(crate) fn 解析正文(文档正文: &str) -> Result<String, u32> {
    let mut 读取器 = 文档读取器::from_str(文档正文);
    读取器.config_mut().expand_empty_elements = true;
    let mut 文档版本 = 默认XML版本;
    let mut 节点深度 = 0usize;
    let mut 正文层级 = 0usize;
    let mut 根节点数 = 0usize;
    let mut 正文数 = 0usize;
    let mut 文本层级 = 0usize;
    let mut 当前段落: Option<(String, String)> = None;
    let mut 当前表格: Option<Vec<Vec<String>>> = None;
    let mut 当前行: Option<Vec<String>> = None;
    let mut 当前单元格: Option<Vec<String>> = None;
    let mut 有序块 = Vec::new();
    let mut 段落数量 = 0usize;
    let mut 表格数量 = 0usize;
    loop {
        let (空间值, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        let 是正文节点 = matches!(空间值, 命名空间结果::Bound(空间名称) if 空间名称.as_ref() == 正文命名空间);
        match 事件值 {
            文档事件::Start(标签值) => {
                节点深度 += 1;
                if 节点深度 > 128 { return Err(错误码::内容不合法); }
                let 名称字节 = 标签值.local_name();
                let 节点名称 = 名称字节.as_ref();
                if 节点深度 == 1 {
                    根节点数 += 1;
                    if 根节点数 != 1 || !是正文节点 || 节点名称 != "document" {
                        return Err(错误码::内容不合法);
                    }
                }
                if 是正文节点 && 节点名称 == "body" {
                    正文数 += 1;
                    if 节点深度 != 2 || 正文数 != 1 { return Err(错误码::内容不合法); }
                    正文层级 = 节点深度;
                    continue;
                }
                if !是正文节点 || 正文层级 == 0 { continue; }
                match 节点名称 {
                    "tbl" => {
                        if 当前表格.is_some() || 当前段落.is_some() { return Err(错误码::内容不合法); }
                        当前表格 = Some(Vec::new());
                    }
                    "tr" => {
                        if 当前表格.is_none() || 当前行.is_some() { return Err(错误码::内容不合法); }
                        当前行 = Some(Vec::new());
                    }
                    "tc" => {
                        if 当前行.is_none() || 当前单元格.is_some() { return Err(错误码::内容不合法); }
                        当前单元格 = Some(Vec::new());
                    }
                    "p" => {
                        if 当前段落.is_some() || (当前表格.is_some() && 当前单元格.is_none()) {
                            return Err(错误码::内容不合法);
                        }
                        当前段落 = Some((String::new(), String::new()));
                    }
                    "pStyle" => {
                        if let Some((_, 段落式名)) = 当前段落.as_mut() {
                            for 属性结果 in 标签值.attributes() {
                                let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                                if 属性项.key.local_name().as_ref() == "val" {
                                    *段落式名 = 属性项.normalized_value(文档版本)
                                        .map_err(|_| 错误码::内容不合法)?.into_owned();
                                }
                            }
                        }
                    }
                    "t" if 当前段落.is_some() => { 文本层级 = 节点深度; }
                    "tab" | "br" | "cr" => {
                        if let Some((段落拼文, _)) = 当前段落.as_mut() {
                            段落拼文.push(if 节点名称 == "tab" { '\t' } else { '\n' });
                        }
                    }
                    _ => {}
                }
            }
            文档事件::End(标签值) => {
                if 是正文节点 && 正文层级 != 0 {
                    match 标签值.local_name().as_ref() {
                        "t" => { 文本层级 = 0; }
                        "p" => {
                            let (段落拼文, 段落式名) = 当前段落.take().ok_or(错误码::内容不合法)?;
                            if let Some(单元格段集) = 当前单元格.as_mut() {
                                单元格段集.push(段落拼文);
                            } else {
                                段落数量 += 1;
                                有序块.push(段落块(段落拼文, 段落式名, 段落数量));
                            }
                        }
                        "tc" => {
                            let 单元格拼文 = 当前单元格.take().ok_or(错误码::内容不合法)?.join("\n");
                            当前行.as_mut().ok_or(错误码::内容不合法)?.push(单元格拼文);
                        }
                        "tr" => {
                            let 单行格集 = 当前行.take().ok_or(错误码::内容不合法)?;
                            当前表格.as_mut().ok_or(错误码::内容不合法)?.push(单行格集);
                        }
                        "tbl" => {
                            let 表格行集 = 当前表格.take().ok_or(错误码::内容不合法)?;
                            表格数量 += 1;
                            有序块.push(serde_json::json!({"类型":"表格","文本":"","表格数据":表格行集}));
                        }
                        "body" => {
                            if 当前段落.is_some() || 当前表格.is_some() { return Err(错误码::内容不合法); }
                            正文层级 = 0;
                        }
                        _ => {}
                    }
                }
                节点深度 = 节点深度.checked_sub(1).ok_or(错误码::内容不合法)?;
            }
            文档事件::Text(文本节点) => {
                let 正文片段 = 文本节点.xml_content(文档版本);
                if 节点深度 == 0 && !正文片段.trim().is_empty() { return Err(错误码::内容不合法); }
                if 文本层级 != 0 {
                    当前段落.as_mut().ok_or(错误码::内容不合法)?.0.push_str(&正文片段);
                }
            }
            文档事件::CData(文本节点) if 文本层级 != 0 => {
                当前段落.as_mut().ok_or(错误码::内容不合法)?.0.push_str(&文本节点.xml_content(文档版本));
            }
            文档事件::GeneralRef(实体节点) if 文本层级 != 0 => {
                let 实体字元 = match 实体节点.resolve_char_ref().map_err(|_| 错误码::内容不合法)? {
                    Some(单字元) => 单字元,
                    None => match 实体节点.as_ref() {
                        "amp" => '&', "lt" => '<', "gt" => '>', "apos" => '\'', "quot" => '"',
                        _ => return Err(错误码::内容不合法),
                    },
                };
                当前段落.as_mut().ok_or(错误码::内容不合法)?.0.push(实体字元);
            }
            文档事件::Decl(声明值) => {
                文档版本 = 声明值.xml_version().map_err(|_| 错误码::内容不合法)?;
            }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    if 节点深度 != 0 || 根节点数 != 1 || 正文数 != 1 || 正文层级 != 0 {
        return Err(错误码::内容不合法);
    }
    Ok(serde_json::json!({"块列表":有序块,"资源列表":[],"段数":段落数量,"表数":表格数量}).to_string())
}

fn 段落块(段落拼文: String, 段落式名: String, 段落数量: usize) -> serde_json::Value {
    let 标题层级 = 段落式名.to_ascii_lowercase().strip_prefix("heading")
        .and_then(|层级文本| 层级文本.parse::<u32>().ok()).filter(|层级值| (1..=9).contains(层级值));
    let mut 块节点 = serde_json::json!({"类型":"段落","文本":段落拼文,"来源位置":{"段落序号":段落数量}});
    if !段落式名.is_empty() { 块节点["样式"] = 段落式名.into(); }
    if let Some(层级值) = 标题层级 {
        块节点["类型"] = "标题".into();
        块节点["来源位置"]["附加"] = serde_json::json!({"level":层级值});
    }
    块节点
}
