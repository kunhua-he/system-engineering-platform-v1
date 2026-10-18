use crate::编号与码面::{能力号, 错误码};
use scraper::{Html as 网页, Selector as 选择器, Node as 节点};
use v1_contract::复合值载荷::{复合值, 复合元素, 编码复合值载荷};
fn 文本值(原字节: &[u8]) -> Result<&str,u32> { std::str::from_utf8(原字节).map_err(|_| 错误码::参数不合法) }
fn 编列表(文本表: Vec<String>) -> Result<(u32,Vec<u8>),u32> {
    let 元素表 = 文本表.into_iter().map(|原文| 复合元素 { 名称: String::new(), 值: 复合值::文本载荷(原文) }).collect::<Vec<_>>();
    Ok((100,编码复合值载荷(100,&元素表).map_err(|_| 错误码::内容不合法)?))
}
pub fn 执行业务操作(编号:u32, 参数表:&[&[u8]]) -> Result<(u32,Vec<u8>),u32> {
    let 文档 = 网页::parse_document(文本值(参数表[0])?);
    if 编号 == 能力号::提取标题 {
        let 标题选择器 = 选择器::parse("title").map_err(|_| 错误码::内容不合法)?;
        let 标题 = 文档.select(&标题选择器).next().map(|网页元素| 网页元素.text().collect::<String>()).unwrap_or_default();
        return Ok((4,标题.trim().as_bytes().to_vec()));
    }
    if 编号 == 能力号::提取正文 {
        let 正文选择器 = 选择器::parse("body").map_err(|_| 错误码::内容不合法)?;
        let mut 文本片段 = Vec::new();
        if let Some(正文) = 文档.select(&正文选择器).next() {
            for 叶节点 in 正文.descendants() {
                if let 节点::Text(文本节点) = 叶节点.value() {
                    let 应跳过 = 叶节点.ancestors().any(|祖先| matches!(祖先.value(),节点::Element(网页元素) if matches!(网页元素.name(),"script"|"style"|"noscript"|"template")));
                    if !应跳过 { 文本片段.extend(文本节点.split_whitespace()); }
                }
            }
        }
        return Ok((4,文本片段.join(" ").into_bytes()));
    }
    let 选择表达式 = 文本值(参数表[1])?;
    if 选择表达式.len()>4096 { return Err(错误码::资源受限); }
    let CSS选择器 = 选择器::parse(选择表达式).map_err(|_| 错误码::内容不合法)?;
    let mut 文本表=Vec::new();
    let mut 总字节数=0;
    for 网页元素 in 文档.select(&CSS选择器) {
        let 选中内容 = if 编号==能力号::选择属性 { match 网页元素.value().attr(文本值(参数表[2])?) { Some(属性值)=>属性值.to_owned(), None=>continue } } else { 网页元素.text().collect::<String>() };
        总字节数+=选中内容.len();
        if 文本表.len()>=1000 || 总字节数>65536 { return Err(错误码::资源受限); }
        文本表.push(选中内容);
    }
    编列表(文本表)
}
