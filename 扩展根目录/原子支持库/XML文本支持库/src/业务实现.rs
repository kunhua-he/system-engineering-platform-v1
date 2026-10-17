use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    use quick_xml::XmlVersion::Implicit1_0 as XML默认版本;
    use quick_xml::events::Event;
    let mut XML文档版本 = XML默认版本;
    let mut 读取器 = quick_xml::reader::Reader::from_str(取文本(0)?);
    let mut 根名 = String::new();
    let mut 拼接正文 = String::new();
    let mut 根数 = 0usize;
    let mut 深度 = 0usize;
    let mut 最大深度 = 0usize;
    let mut 事件数 = 0usize;
    loop {
        let 事件 = 读取器.read_event().map_err(|_| 错误码::内容不合法)?;
        if matches!(&事件, Event::Eof) {
            break;
        }
        let 是开始 = matches!(&事件, Event::Start(_));
        let 是结束 = matches!(&事件, Event::End(_));
        let 是空标签 = matches!(&事件, Event::Empty(_));
        事件数 += 1;
        if 事件数 > 2000 {
            return Err(错误码::资源受限);
        }
        match 事件 {
            Event::Start(标签) | Event::Empty(标签) => {
                if 深度 == 0 {
                    根数 += 1;
                    if 根数 != 1 {
                        return Err(错误码::内容不合法);
                    }
                    根名 = 标签.name().as_ref().to_owned();
                }
                for 属性结果 in 标签.attributes() {
                    let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                    属性项
                        .normalized_value(XML文档版本)
                        .map_err(|_| 错误码::内容不合法)?;
                }
            }
            Event::Text(XML节点) => {
                let 节点正文 = XML节点.xml_content(XML文档版本);
                if 深度 == 0 && !节点正文.trim().is_empty() {
                    return Err(错误码::内容不合法);
                }
                if 深度 > 0 {
                    拼接正文.push_str(&节点正文);
                }
            }
            Event::CData(XML节点) => {
                if 深度 == 0 {
                    return Err(错误码::内容不合法);
                }
                拼接正文.push_str(&XML节点.xml_content(XML文档版本));
            }
            Event::Decl(XML声明) => {
                if 事件数 != 1 {
                    return Err(错误码::内容不合法);
                }
                XML文档版本 = XML声明.xml_version().map_err(|_| 错误码::内容不合法)?;
                if let Some(编码结果) = XML声明.encoding() {
                    let 编码名称 = 编码结果.map_err(|_| 错误码::内容不合法)?;
                    if !编码名称.eq_ignore_ascii_case("UTF-8") {
                        return Err(错误码::内容不合法);
                    }
                }
            }
            Event::GeneralRef(引用) => {
                if 深度 == 0 {
                    return Err(错误码::内容不合法);
                }
                if let Some(实体字符) =
                    引用.resolve_char_ref().map_err(|_| 错误码::内容不合法)?
                {
                    拼接正文.push(实体字符);
                } else {
                    拼接正文.push_str(match 引用.as_ref() {
                        "amp" => "&",
                        "lt" => "<",
                        "gt" => ">",
                        "apos" => "'",
                        "quot" => "\"",
                        _ => return Err(错误码::内容不合法),
                    });
                }
            }
            Event::DocType(_) => return Err(错误码::内容不合法),
            _ => {}
        }
        if 是开始 {
            深度 += 1;
            最大深度 = 最大深度.max(深度);
        }
        if 是空标签 {
            最大深度 = 最大深度.max(深度 + 1);
        }
        if 是结束 {
            深度 = 深度.checked_sub(1).ok_or(错误码::内容不合法)?;
        }
        if 最大深度 > 64 || 拼接正文.len() > 65536 {
            return Err(错误码::资源受限);
        }
    }
    if 根数 != 1 || 深度 != 0 {
        return Err(错误码::内容不合法);
    }
    let 输出文本 = match 操作号 {
        能力号::取根名称 => 根名,
        能力号::提取文本 => 拼接正文,
        能力号::取结构摘要JSON => {
            serde_json::json!({"根名称":根名,"事件数量":事件数,"最大深度":最大深度,"正文":拼接正文})
                .to_string()
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
