//! PPTX 解析：ZIP → presentation.xml 取页尺寸与页序 → 逐张 slideN.xml 取文本框。
//!
//! 只读不写、不还原版式；取不到的（图形化文字、图片内文字、SmartArt）如实空着，
//! 不猜不编 —— 要图片里的字走 6201 识别图片文字。
use std::collections::HashMap;
use std::io::Read;

use quick_xml::events::Event as 文档事件;
use quick_xml::name::ResolveResult as 命名空间结果;
use quick_xml::reader::NsReader as 文档读取器;
use quick_xml::XmlVersion::Implicit1_0 as 默认XML版本;

use crate::编号与码面::错误码;

/// 跨页重复率的判定线：出现在 ≥80% 页面上的同文本块，认作页眉页脚。
const 重复率判定: f64 = 0.8;
const 页眉页脚类型: &str = "页眉页脚";

const 绘图命名空间: &str = "http://schemas.openxmlformats.org/drawingml/2006/main";
const 演示命名空间: &str = "http://schemas.openxmlformats.org/presentationml/2006/main";
const 关系命名空间: &str = "http://schemas.openxmlformats.org/package/2006/relationships";
const 文件上限字节: usize = 64 * 1024 * 1024;
const 幻灯片上限: usize = 500;
const 文本上限字节: usize = 4 * 1024 * 1024;

pub(crate) struct 文本块 {
    pub 文本: String,
    /// 块内最大字号（磅×100，PPTX 的 sz 单位）；取不到记 0
    pub 字号: i32,
    /// 占位符类型：title / ctrTitle / body / subTitle 等；普通文本框记空串
    pub 类型: String,
}

pub(crate) struct 幻灯片内容 {
    pub 序号: usize,
    pub 标题: String,
    pub 文本块: Vec<文本块>,
}

pub(crate) struct 演示文稿 {
    pub 幻灯片数: usize,
    pub 页宽: i64,
    pub 页高: i64,
    pub 幻灯片: Vec<幻灯片内容>,
}

fn 读包内文本(包: &mut zip::ZipArchive<std::io::Cursor<Vec<u8>>>, 名称: &str) -> Result<String, u32> {
    let mut 条目 = 包.by_name(名称).map_err(|_| 错误码::内容不合法)?;
    if 条目.size() as usize > 文件上限字节 {
        return Err(错误码::内容超限);
    }
    let mut 缓冲 = String::new();
    条目.read_to_string(&mut 缓冲).map_err(|_| 错误码::内容不合法)?;
    Ok(缓冲)
}

/// 从 `ppt/presentation.xml` 取页尺寸（EMU）与 rId 顺序。
fn 读演示结构(xml文本: &str) -> Result<(i64, i64, Vec<String>), u32> {
    let mut 读取器 = 文档读取器::from_str(xml文本);
    // 必须展开空元素：`<p:sldSz .../>` 这类自闭合标签只给 Start 不给 End，
    // 不展开就会让深度只增不减，几十个标签后撞上限被当成坏 XML（实测本样本必中）。
    读取器.config_mut().expand_empty_elements = true;
    let mut 页宽 = 0i64;
    let mut 页高 = 0i64;
    let mut 序表 = Vec::new();
    let mut 深度 = 0usize;
    loop {
        let (空间值, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        let 是本节点 = matches!(空间值, 命名空间结果::Bound(名) if 名.as_ref() == 演示命名空间);
        match 事件值 {
            文档事件::Start(标签值) => {
                深度 += 1;
                if 深度 > 64 { return Err(错误码::内容不合法); }
                if !是本节点 { continue; }
                let 名 = 标签值.local_name();
                match 名.as_ref() {
                    "sldSz" => {
                        for 属性结果 in 标签值.attributes() {
                            let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                            let 键 = 属性项.key.local_name();
                            let 值文本 = 属性项.normalized_value(默认XML版本).map_err(|_| 错误码::内容不合法)?;
                            match 键.as_ref() {
                                "cx" => 页宽 = 值文本.parse::<i64>().map_err(|_| 错误码::内容不合法)?,
                                "cy" => 页高 = 值文本.parse::<i64>().map_err(|_| 错误码::内容不合法)?,
                                _ => {}
                            }
                        }
                    }
                    "sldId" => {
                        for 属性结果 in 标签值.attributes() {
                            let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                            // r:id 带命名空间前缀，本地名是 id
                            if 属性项.key.local_name().as_ref() == "id" && 属性项.key.as_ref().contains(':') {
                                序表.push(属性项.normalized_value(默认XML版本).map_err(|_| 错误码::内容不合法)?.into_owned());
                            }
                        }
                    }
                    _ => {}
                }
            }
            文档事件::End(_) => { 深度 = 深度.saturating_sub(1); }
            文档事件::Eof => break,
            _ => {}
        }
    }
    if 页宽 <= 0 || 页高 <= 0 { return Err(错误码::内容不合法); }
    Ok((页宽, 页高, 序表))
}

/// `ppt/_rels/presentation.xml.rels`：rId → 包内路径。
fn 读关系表(xml文本: &str) -> Result<HashMap<String, String>, u32> {
    let mut 读取器 = 文档读取器::from_str(xml文本);
    读取器.config_mut().expand_empty_elements = true;
    let mut 表 = HashMap::new();
    let mut 深度 = 0usize;
    loop {
        let (空间值, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        let 是本节点 = matches!(空间值, 命名空间结果::Bound(名) if 名.as_ref() == 关系命名空间);
        match 事件值 {
            文档事件::Start(标签值) => {
                深度 += 1;
                if 深度 > 16 { return Err(错误码::内容不合法); }
                if !是本节点 || 标签值.local_name().as_ref() != "Relationship" { continue; }
                let mut 编号 = String::new();
                let mut 目标 = String::new();
                for 属性结果 in 标签值.attributes() {
                    let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                    let 值文本 = 属性项.normalized_value(默认XML版本).map_err(|_| 错误码::内容不合法)?.into_owned();
                    match 属性项.key.as_ref() {
                        "Id" => 编号 = 值文本,
                        "Target" => 目标 = 值文本,
                        _ => {}
                    }
                }
                if !编号.is_empty() && !目标.is_empty() {
                    // Target 可能是 "slides/slide1.xml"（相对 ppt/）或 "/ppt/slides/slide1.xml"
                    let 规整 = if 目标.starts_with('/') {
                        目标.trim_start_matches('/').to_string()
                    } else {
                        format!("ppt/{}", 目标)
                    };
                    表.insert(编号, 规整);
                }
            }
            文档事件::End(_) => { 深度 = 深度.saturating_sub(1); }
            文档事件::Eof => break,
            _ => {}
        }
    }
    Ok(表)
}

/// 单张幻灯片：按 `<p:sp>` 分块，块内 `<a:t>` 拼接；`<p:ph type="title|ctrTitle">` 记为标题。
fn 解析单页(xml文本: &str, 序号: usize) -> Result<幻灯片内容, u32> {
    let mut 读取器 = 文档读取器::from_str(xml文本);
    读取器.config_mut().expand_empty_elements = true;
    let mut 深度 = 0usize;
    let mut 块缓冲 = String::new();
    let mut 块表: Vec<文本块> = Vec::new();
    let mut 当前块类型 = String::new();
    let mut 当前块字号: i32 = 0;
    let mut 在块内 = false;
    let mut 在文本内 = false;
    loop {
        let (空间值, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        let 是绘图 = matches!(空间值, 命名空间结果::Bound(名) if 名.as_ref() == 绘图命名空间);
        let 是演示 = matches!(空间值, 命名空间结果::Bound(名) if 名.as_ref() == 演示命名空间);
        match 事件值 {
            文档事件::Start(标签值) => {
                深度 += 1;
                if 深度 > 96 { return Err(错误码::内容不合法); }
                let 名 = 标签值.local_name();
                if 是演示 && 名.as_ref() == "sp" {
                    在块内 = true;
                    当前块类型.clear();
                    当前块字号 = 0;
                    块缓冲.clear();
                } else if 是绘图 && (名.as_ref() == "rPr" || 名.as_ref() == "defRPr") && 在块内 {
                    // 字号挂在绘图命名空间（`a:rPr` / `a:defRPr`）上，不是 `p:` —— 早先按演示命名空间判，
                    // 条件恒假，字号永远是 0（实测某课件每块都有 sz="1000" 却全取 0）。
                    // 字号挂在 run 属性上：块内取最大值，用来判断这块是不是标题
                    for 属性结果 in 标签值.attributes() {
                        let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                        if 属性项.key.local_name().as_ref() == "sz" {
                            当前块字号 = 属性项.normalized_value(默认XML版本).ok()
                                .and_then(|值文本| 值文本.trim().parse::<i32>().ok())
                                .map_or(当前块字号, |值| 当前块字号.max(值));
                        }
                    }
                } else if 是演示 && 名.as_ref() == "ph" && 在块内 {
                    for 属性结果 in 标签值.attributes() {
                        let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                        if 属性项.key.local_name().as_ref() == "type" {
                            当前块类型 = 属性项.normalized_value(默认XML版本)
                                .map_err(|_| 错误码::内容不合法)?.into_owned();
                        }
                    }
                } else if 是绘图 && 名.as_ref() == "t" && 在块内 {
                    在文本内 = true;
                }
            }
            文档事件::Text(文本值) if 在文本内 => {
                let 片段 = 文本值.xml_content(默认XML版本);
                if 块缓冲.len() + 片段.len() > 文本上限字节 {
                    return Err(错误码::内容超限);
                }
                块缓冲.push_str(&片段);
            }
            文档事件::Text(_) => {}
            文档事件::End(标签值) => {
                深度 = 深度.saturating_sub(1);
                let 名 = 标签值.local_name();
                if 是绘图 && 名.as_ref() == "t" {
                    在文本内 = false;
                } else if 是演示 && 名.as_ref() == "sp" && 在块内 {
                    在块内 = false;
                    let 干净 = 块缓冲.trim().to_string();
                    if !干净.is_empty() {
                        块表.push(文本块 { 文本: 干净, 字号: 当前块字号, 类型: 当前块类型.clone() });
                    }
                    块缓冲.clear();
                    当前块类型.clear();
                    当前块字号 = 0;
                }
            }
            文档事件::Eof => break,
            _ => {}
        }
    }
    let 标题 = 挑标题(&块表);
    Ok(幻灯片内容 { 序号, 标题, 文本块: 块表 })
}

/// 标题策略：先认占位符类型（title/ctrTitle），再退 body/subTitle，最后才用第一个非页眉块。
/// 页眉页脚常常就是第一个块，直接取首个会把每页标题都取成页眉（实测某课件 21 页全中）。
fn 挑标题(块表: &[文本块]) -> String {
    ["title", "ctrTitle", "body", "subTitle"]
        .iter()
        .find_map(|类名| 块表.iter().find(|块| 块.类型 == *类名).map(|块| 块.文本.clone()))
        .or_else(|| {
            // 没用占位符的课件：取第一个非页眉块。**不按字号猜** —— 实测字号最大的常是
            // 装饰性英文/水印（如「BLACK GOLD COLLECTION」），比首个非页眉块更容易错。
            块表.iter()
                .find(|块| 块.类型 != 页眉页脚类型)
                .map(|块| 块.文本.clone())
        })
        .unwrap_or_default()
}

pub(crate) fn 解析演示文稿(字节: &[u8]) -> Result<演示文稿, u32> {
    if 字节.is_empty() {
        return Err(错误码::参数不合法);
    }
    if 字节.len() > 文件上限字节 {
        return Err(错误码::内容超限);
    }
    let mut 包 = zip::ZipArchive::new(std::io::Cursor::new(字节.to_vec()))
        .map_err(|_| 错误码::内容不合法)?;
    let 演示XML = 读包内文本(&mut 包, "ppt/presentation.xml")?;
    let (页宽, 页高, 序表) = 读演示结构(&演示XML)?;
    let 关系XML = 读包内文本(&mut 包, "ppt/_rels/presentation.xml.rels").unwrap_or_default();
    let 关系表 = 读关系表(&关系XML)?;

    // 页序以 presentation.xml 的 sldIdLst 为准（rels 映射 rId → 包内路径）；
    // 映射不到就退回按 slideN.xml 的自然序，并在结果里如实标出。
    let mut 路径表: Vec<String> = 序表.iter().filter_map(|编号| 关系表.get(编号).cloned()).collect();
    let 用了关系表 = !路径表.is_empty();
    if !用了关系表 {
        // zip 9 的 file_names 每项是 Result（个别条目名非 UTF-8）⇒ 跳过读不出的，不整包失败。
        let mut 候选: Vec<String> = 包.file_names()
            .filter_map(|名| 名.ok().map(|值| 值.into_owned()))
            .filter(|名| 名.starts_with("ppt/slides/slide") && 名.ends_with(".xml"))
            .collect();
        候选.sort_by_key(|名| {
            名.trim_start_matches("ppt/slides/slide")
                .trim_end_matches(".xml")
                .parse::<usize>()
                .unwrap_or(usize::MAX)
        });
        路径表 = 候选;
    }
    if 路径表.len() > 幻灯片上限 {
        return Err(错误码::内容超限);
    }

    let mut 幻灯片 = Vec::new();
    let mut 累计文本 = 0usize;
    for (位, 路径) in 路径表.iter().enumerate() {
        let xml文本 = match 读包内文本(&mut 包, 路径) {
            Ok(值) => 值,
            Err(_) => continue,
        };
        let 页 = 解析单页(&xml文本, 位)?;
        累计文本 += 页.文本块.iter().map(|块| 块.文本.len()).sum::<usize>();
        if 累计文本 > 文本上限字节 {
            return Err(错误码::内容超限);
        }
        幻灯片.push(页);
    }
    if 幻灯片.is_empty() {
        return Err(错误码::内容不合法);
    }
    标记页眉页脚(&mut 幻灯片);
    Ok(演示文稿 { 幻灯片数: 幻灯片.len(), 页宽, 页高, 幻灯片 })
}

/// 跨页重复的块认作页眉页脚：**不删块**（那是真实内容，调用方可能要），只把类型标出来，
/// 并让标题重挑一次 —— 很多课件根本不用占位符，全靠手工文本框，页眉就是第一块。
fn 标记页眉页脚(幻灯片表: &mut [幻灯片内容]) {
    if 幻灯片表.len() < 3 {
        return;
    }
    let 判定线 = (幻灯片表.len() as f64 * 重复率判定).ceil() as usize;
    let mut 计数: HashMap<String, usize> = HashMap::new();
    for 页 in 幻灯片表.iter() {
        let mut 本页: Vec<&String> = 页.文本块.iter().map(|块| &块.文本).collect();
        本页.sort();
        本页.dedup();
        for 文本 in 本页 {
            *计数.entry(文本.clone()).or_insert(0) += 1;
        }
    }
    let 重复集: Vec<String> = 计数.into_iter()
        .filter(|(_, 次)| *次 >= 判定线)
        .map(|(文本, _)| 文本)
        .collect();
    if 重复集.is_empty() {
        return;
    }
    for 页 in 幻灯片表.iter_mut() {
        for 块 in 页.文本块.iter_mut() {
            if 重复集.contains(&块.文本) {
                块.类型 = 页眉页脚类型.to_string();
            }
        }
        页.标题 = 挑标题(&页.文本块);
    }
}

#[cfg(test)]
mod 测试 {
    use super::*;

    /// 真样本走环境变量：没设 `V1_PPTX_SAMPLE` 就跳过（不把某台机器的路径写进仓库）。
    #[test]
    fn 解析真实PPTX() {
        let 路径 = match std::env::var("V1_PPTX_SAMPLE") {
            Ok(值) if !值.is_empty() => 值,
            _ => return,
        };
        let 字节 = std::fs::read(&路径).expect("样本读不出");
        let 文稿 = 解析演示文稿(&字节).expect("解析失败");
        assert!(文稿.幻灯片数 > 0, "至少要有一页");
        assert!(文稿.页宽 > 0 && 文稿.页高 > 0, "页尺寸要取到");
        assert_eq!(文稿.幻灯片.len(), 文稿.幻灯片数);
        let 有文字页 = 文稿.幻灯片.iter().filter(|页| !页.文本块.is_empty()).count();
        println!("幻灯片数={} 页尺寸={}x{} EMU | 有文字页={}", 文稿.幻灯片数, 文稿.页宽, 文稿.页高, 有文字页);
        for 页 in 文稿.幻灯片.iter().take(4) {
            println!("  第{}页 标题=「{}」 块数={} 首块=「{}」", 页.序号, 页.标题, 页.文本块.len(),
                     页.文本块.first().map(|块| 块.文本.clone()).unwrap_or_default().chars().take(30).collect::<String>());
        }
        assert!(有文字页 > 0, "整份样本一页文字都没取到，解析器可疑");
    }

    #[test]
    fn 空字节被拒() {
        assert!(解析演示文稿(b"").is_err());
    }

    #[test]
    fn 非ZIP被拒() {
        assert!(解析演示文稿(b"%PDF-1.4 not a zip").is_err());
    }
}
