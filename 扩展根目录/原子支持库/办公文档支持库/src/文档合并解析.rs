use crate::编号与码面::错误码;
use quick_xml::events::Event as 文档事件;
use quick_xml::name::ResolveResult as 命名空间结果;
use quick_xml::reader::NsReader as 文档读取器;
use quick_xml::XmlVersion::Implicit1_0 as 默认XML版本;

const 正文命名空间: &str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

// 段落级常用样式：只收 Word 里最常见、能原样回写的几维，其余维不猜。
#[derive(Default)]
struct 段落样式 {
    加粗: Option<bool>,
    字号半磅: Option<u32>,
    颜色: Option<String>,
    字体: Option<String>,
    对齐: Option<String>,
}

struct 格快照 {
    段落集: Vec<String>,
    横跨: usize,
    纵合并: u8,
}

pub(crate) fn 解析增强正文(文档正文: &str) -> Result<String, u32> {
    let mut 读取器 = 文档读取器::from_str(文档正文);
    读取器.config_mut().expand_empty_elements = true;
    let mut 文档版本 = 默认XML版本;
    let mut 节点深度 = 0usize;
    let mut 正文层级 = 0usize;
    let mut 根节点数 = 0usize;
    let mut 正文数 = 0usize;
    let mut 文本层级 = 0usize;
    let mut 当前段落: Option<(String, String)> = None;
    let mut 当前样式 = 段落样式::default();
    let mut 当前表格: Option<Vec<Vec<String>>> = None;
    let mut 当前行: Option<Vec<String>> = None;
    let mut 当前格: Option<格快照> = None;
    let mut 表格合并表: Vec<serde_json::Value> = Vec::new();
    let mut 纵合并起点: Vec<Option<usize>> = Vec::new();
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
                        表格合并表.clear();
                        纵合并起点.clear();
                    }
                    "tr" => {
                        if 当前表格.is_none() || 当前行.is_some() { return Err(错误码::内容不合法); }
                        当前行 = Some(Vec::new());
                    }
                    "tc" => {
                        if 当前行.is_none() || 当前格.is_some() { return Err(错误码::内容不合法); }
                        当前格 = Some(格快照 { 段落集: Vec::new(), 横跨: 1, 纵合并: 0 });
                    }
                    "gridSpan" => {
                        if let (Some(当前格快照), Some(横跨值)) = (当前格.as_mut(), 取属性值(&标签值, 文档版本, "val")?) {
                            let 横跨数 = 横跨值.parse::<usize>().map_err(|_| 错误码::内容不合法)?;
                            if 横跨数 == 0 || 横跨数 > 64 { return Err(错误码::内容不合法); }
                            当前格快照.横跨 = 横跨数;
                        }
                    }
                    "vMerge" => {
                        if let Some(当前格快照) = 当前格.as_mut() {
                            let 合并值 = 取属性值(&标签值, 文档版本, "val")?;
                            当前格快照.纵合并 = match 合并值.as_deref() {
                                Some("restart") => 1,
                                _ => 2,
                            };
                        }
                    }
                    "p" => {
                        if 当前段落.is_some() || (当前表格.is_some() && 当前格.is_none()) {
                            return Err(错误码::内容不合法);
                        }
                        当前段落 = Some((String::new(), String::new()));
                        当前样式 = 段落样式::default();
                    }
                    "pStyle" => {
                        if let Some((_, 段落式名)) = 当前段落.as_mut() {
                            if let Some(式名值) = 取属性值(&标签值, 文档版本, "val")? {
                                *段落式名 = 式名值;
                            }
                        }
                    }
                    "jc" => {
                        if let Some(对齐值) = 取属性值(&标签值, 文档版本, "val")? {
                            当前样式.对齐 = Some(对齐值);
                        }
                    }
                    "b" => {
                        if 当前段落.is_some() {
                            let 关闭值 = 取属性值(&标签值, 文档版本, "val")?;
                            当前样式.加粗 = Some(!matches!(关闭值.as_deref(), Some("0") | Some("false")));
                        }
                    }
                    "sz" => {
                        if 当前段落.is_some() {
                            if let Some(字号值) = 取属性值(&标签值, 文档版本, "val")? {
                                当前样式.字号半磅 = 字号值.parse::<u32>().ok().filter(|半磅值| *半磅值 > 0 && *半磅值 <= 3276);
                            }
                        }
                    }
                    "color" => {
                        if 当前段落.is_some() {
                            if let Some(颜色值) = 取属性值(&标签值, 文档版本, "val")? {
                                if 颜色值.len() == 6 && 颜色值.bytes().all(|单字节| 单字节.is_ascii_hexdigit()) {
                                    当前样式.颜色 = Some(颜色值);
                                }
                            }
                        }
                    }
                    "rFonts" => {
                        if 当前段落.is_some() {
                            当前样式.字体 = 取属性值(&标签值, 文档版本, "eastAsia")?.or(取属性值(&标签值, 文档版本, "ascii")?);
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
                            if let Some(当前格快照) = 当前格.as_mut() {
                                当前格快照.段落集.push(段落拼文);
                            } else {
                                段落数量 += 1;
                                有序块.push(段落块(段落拼文, 段落式名, 段落数量, &当前样式));
                            }
                        }
                        "tc" => {
                            let 当前格快照 = 当前格.take().ok_or(错误码::内容不合法)?;
                            let 行集 = 当前行.as_mut().ok_or(错误码::内容不合法)?;
                            let 列序位 = 行集.len();
                            let 表格行数 = 当前表格.as_ref().ok_or(错误码::内容不合法)?.len();
                            if 当前格快照.纵合并 == 2 {
                                行集.push(String::new());
                                if let Some(Some(起点位)) = 纵合并起点.get(列序位) {
                                    if let Some(合并项) = 表格合并表.get_mut(*起点位) {
                                        合并项["行跨度"] = serde_json::json!(
                                            合并项["行跨度"].as_u64().unwrap_or(1) + 1
                                        );
                                    }
                                }
                            } else {
                                行集.push(当前格快照.段落集.join("\n"));
                                for _ in 1..当前格快照.横跨 { 行集.push(String::new()); }
                                if 当前格快照.横跨 > 1 || 当前格快照.纵合并 == 1 {
                                    表格合并表.push(serde_json::json!({
                                        "起始行": 表格行数,
                                        "起始列": 列序位,
                                        "行跨度": 1,
                                        "列跨度": 当前格快照.横跨,
                                    }));
                                    if 当前格快照.纵合并 == 1 {
                                        while 纵合并起点.len() <= 列序位 { 纵合并起点.push(None); }
                                        纵合并起点[列序位] = Some(表格合并表.len() - 1);
                                    }
                                }
                            }
                        }
                        "tr" => {
                            let 单行格集 = 当前行.take().ok_or(错误码::内容不合法)?;
                            当前表格.as_mut().ok_or(错误码::内容不合法)?.push(单行格集);
                        }
                        "tbl" => {
                            let 表格行集 = 当前表格.take().ok_or(错误码::内容不合法)?;
                            let 合并条目: Vec<serde_json::Value> = 表格合并表
                                .iter()
                                .filter(|合并项| {
                                    合并项["行跨度"].as_u64() > Some(1)
                                        || 合并项["列跨度"].as_u64() > Some(1)
                                })
                                .cloned()
                                .collect();
                            表格数量 += 1;
                            有序块.push(serde_json::json!({
                                "类型":"表格",
                                "文本":"",
                                "表格数据":表格行集,
                                "合并列表":合并条目,
                                "来源位置":{"表格序号":表格数量},
                            }));
                            表格合并表.clear();
                            纵合并起点.clear();
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

fn 取属性值(标签值: &quick_xml::events::BytesStart, 文档版本: quick_xml::XmlVersion, 属性名: &str) -> Result<Option<String>, u32> {
    for 属性结果 in 标签值.attributes() {
        let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
        if 属性项.key.local_name().as_ref() == 属性名 {
            return Ok(Some(属性项.normalized_value(文档版本).map_err(|_| 错误码::内容不合法)?.into_owned()));
        }
    }
    Ok(None)
}

fn 段落块(段落拼文: String, 段落式名: String, 段落数量: usize, 段样式: &段落样式) -> serde_json::Value {
    let 标题层级 = 段落式名.to_ascii_lowercase().strip_prefix("heading")
        .and_then(|层级文本| 层级文本.parse::<u32>().ok()).filter(|层级值| (1..=9).contains(层级值));
    let mut 块节点 = serde_json::json!({"类型":"段落","文本":段落拼文,"来源位置":{"段落序号":段落数量}});
    if !段落式名.is_empty() { 块节点["样式"] = 段落式名.clone().into(); }
    if let Some(层级值) = 标题层级 {
        块节点["类型"] = "标题".into();
        块节点["来源位置"]["附加"] = serde_json::json!({"level":层级值});
    }
    let mut 样式节点 = serde_json::Map::new();
    if let Some(加粗值) = 段样式.加粗 { 样式节点.insert("加粗".into(), 加粗值.into()); }
    if let Some(半磅值) = 段样式.字号半磅 { 样式节点.insert("字号".into(), serde_json::json!(半磅值 as f64 / 2.0)); }
    if let Some(颜色值) = &段样式.颜色 { 样式节点.insert("颜色".into(), 颜色值.clone().into()); }
    if let Some(字体值) = &段样式.字体 { 样式节点.insert("字体".into(), 字体值.clone().into()); }
    if let Some(对齐值) = &段样式.对齐 { 样式节点.insert("对齐".into(), 对齐值.clone().into()); }
    if !样式节点.is_empty() { 块节点["段落样式"] = serde_json::Value::Object(样式节点); }
    块节点
}
