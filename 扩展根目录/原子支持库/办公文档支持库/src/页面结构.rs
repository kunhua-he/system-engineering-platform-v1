//! 检查页面结构 —— PPTX 的页数、页序、关系文件、缺关系、重号与孤儿页。
//!
//! **为何要有**：`6112 解析DOCX` 只认 docx；pptx 的页序在 `ppt/presentation.xml` 的
//! `sldIdLst`（顺序）与 `ppt/_rels/presentation.xml.rels`（标识 → 部件）两处，
//! 调用方自行拼一遍就要维护两套判据，迟早给出相反结论（实跑审计问题 06/07/08/18）。
//!
//! **只读判据**：不开 Office、不改文件、不写盘；坏包直接在 `6103 内容不合法` 明说。
use std::collections::BTreeMap;

use quick_xml::events::Event as 文档事件;
use quick_xml::name::ResolveResult as 命名空间结果;
use quick_xml::reader::NsReader as 文档读取器;
use quick_xml::XmlVersion::Implicit1_0 as 默认XML版本;
use serde_json::json;

use crate::编号与码面::错误码;

const 演示命名空间: &str = "http://schemas.openxmlformats.org/presentationml/2006/main";
const 绘图命名空间: &str = "http://schemas.openxmlformats.org/drawingml/2006/main";
/// 单个 XML 条目上限（与 6112 一致）；整包不设上限。
const 部件上限字节: u64 = 32 * 1024 * 1024;
const 关系落点A: &str = "ppt/_rels/presentation.xml.rels";
const 关系落点B: &str = "ppt/presentation.xml.rels";
const 演示落点: &str = "ppt/presentation.xml";

/// 检查一个 pptx 的页面结构，返回 JSON 文本（类型标签 4）。
pub(crate) fn 检查页面结构(文件路径: &str) -> Result<String, u32> {
    // 整包大小不设上限：zip 只按名读需要的那几个 XML 条目，内存不随文件膨胀。
    // （实测真实招商 PPT 有 125 MiB，按 6112 的「整包 32 MiB」口径会把它整个拒掉。）
    let 元数据 = std::fs::metadata(文件路径).map_err(|_| 错误码::参数不合法)?;
    if !元数据.is_file() {
        return Err(错误码::参数不合法);
    }
    let 源文件 = std::fs::File::open(文件路径).map_err(|_| 错误码::参数不合法)?;
    let mut 压缩包 = zip::ZipArchive::new(源文件).map_err(|_| 错误码::内容不合法)?;
    let 页面部件集: Vec<String> = 压缩包
        .file_names()
        .filter_map(|条目名| 条目名.ok())
        .filter(|条目名| 是页面部件(条目名.as_ref()))
        .map(|条目名| 条目名.to_string())
        .collect();
    // 关系文件的两种落点都试：实测两种都见过（OPC 规范是 A，个别生成器写 B）。
    let 关系正文 = match 读文本条目(&mut 压缩包, 关系落点A)? {
        Some(正文值) => 正文值,
        None => match 读文本条目(&mut 压缩包, 关系落点B)? {
            Some(正文值) => 正文值,
            None => return Err(错误码::内容不合法),
        },
    };
    let 关系映射表 = 解析关系表(&关系正文)?;
    let 演示正文 = 读文本条目(&mut 压缩包, 演示落点)?.ok_or(错误码::内容不合法)?;
    let 页序标识表 = 收集页序(&演示正文)?;
    let mut 页序 = Vec::new();
    let mut 缺关系表: Vec<String> = Vec::new();
    let mut 重号表 = Vec::new();
    let mut 已登目标: BTreeMap<String, String> = BTreeMap::new();
    let mut 页序部件集: Vec<String> = Vec::new();
    for (位置, 关系标识) in 页序标识表.iter().enumerate() {
        let 关系目标 = match 关系映射表.get(关系标识) {
            Some(目标值) => 目标值,
            None => {
                缺关系表.push(关系标识.clone());
                continue;
            }
        };
        let 目标路径 = 归一关系目标(关系目标);
        match 已登目标.get(&目标路径) {
            Some(先登标识) => 重号表.push(json!({"关系标识": 关系标识, "先登标识": 先登标识})),
            None => {
                已登目标.insert(目标路径.clone(), 关系标识.clone());
            }
        }
        let 缺文件 = !页面部件集.contains(&目标路径);
        页序部件集.push(目标路径.clone());
        let (标题文字, 标题来源, 片段表) = match 读文本条目(&mut 压缩包, &目标路径)? {
            Some(页正文) => 提取页标题(&页正文)?,
            None => (String::new(), String::new(), Vec::new()),
        };
        页序.push(json!({
            "页序号": 位置 + 1,
            "关系标识": 关系标识,
            "关系文件": 目标路径,
            "标题": 标题文字,
            "标题来源": 标题来源,
            "文字片段": 片段表,
            "缺文件": 缺文件,
        }));
    }
    let 孤儿页表: Vec<&String> = 页面部件集
        .iter()
        .filter(|条目名| !页序部件集.contains(条目名))
        .collect();
    Ok(serde_json::json!({
        "页数": 页序.len(),
        "页序": 页序,
        "缺关系": 缺关系表,
        "重号": 重号表,
        "孤儿页": 孤儿页表,
        "部件数": 页面部件集.len(),
    })
    .to_string())
}

/// 页面部件 = `ppt/slides/slideN.xml`，且不是 `_rels` 下的关系文件。
fn 是页面部件(条目名: &str) -> bool {
    let 前缀对 = 条目名.starts_with("ppt/slides/slide");
    let 后缀对 = 条目名.ends_with(".xml");
    let 非关系 = !条目名.contains("/_rels/");
    let 无非数字 = 条目名
        .trim_start_matches("ppt/slides/slide")
        .trim_end_matches(".xml")
        .chars()
        .all(|单字| 单字.is_ascii_digit());
    前缀对 && 后缀对 && 非关系 && 无非数字
}

fn 读文本条目(压缩包: &mut zip::ZipArchive<std::fs::File>, 条目名: &str) -> Result<Option<String>, u32> {
    let mut 条目 = match 压缩包.by_name(条目名) {
        Ok(条目值) => 条目值,
        Err(zip::result::ZipError::FileNotFound) => return Ok(None),
        Err(_) => return Err(错误码::内容不合法),
    };
    if 条目.size() > 部件上限字节 {
        return Err(错误码::内容不合法);
    }
    let mut 缓冲 = String::new();
    use std::io::Read;
    条目.read_to_string(&mut 缓冲).map_err(|_| 错误码::内容不合法)?;
    Ok(Some(缓冲))
}

/// 关系文件 ⇒ `关系标识 → Target`（同一标识重复登记只认首个，不静默改口径）。
fn 解析关系表(关系正文: &str) -> Result<BTreeMap<String, String>, u32> {
    let mut 读取器 = 文档读取器::from_str(关系正文);
    读取器.config_mut().expand_empty_elements = true;
    let mut 文档版本 = 默认XML版本;
    let mut 关系映射表: BTreeMap<String, String> = BTreeMap::new();
    let mut 节点深度 = 0usize;
    loop {
        let (_, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        match 事件值 {
            文档事件::Start(标签值) => {
                节点深度 += 1;
                if 节点深度 > 32 {
                    return Err(错误码::内容不合法);
                }
                if 标签值.local_name().as_ref() == "Relationship" {
                    let mut 关系标识 = String::new();
                    let mut 关系目标 = String::new();
                    for 属性结果 in 标签值.attributes() {
                        let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                        let 值文本 = 属性项
                            .normalized_value(文档版本)
                            .map_err(|_| 错误码::内容不合法)?
                            .into_owned();
                        match 属性项.key.local_name().as_ref() {
                            "Id" => 关系标识 = 值文本,
                            "Target" => 关系目标 = 值文本,
                            _ => {}
                        }
                    }
                    if 关系标识.is_empty() || 关系目标.is_empty() {
                        return Err(错误码::内容不合法);
                    }
                    关系映射表.entry(关系标识).or_insert(关系目标);
                }
            }
            文档事件::End(_) => {
                节点深度 = 节点深度.checked_sub(1).ok_or(错误码::内容不合法)?;
            }
            文档事件::Decl(声明值) => {
                文档版本 = 声明值.xml_version().map_err(|_| 错误码::内容不合法)?;
            }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    if 关系映射表.is_empty() {
        return Err(错误码::内容不合法);
    }
    Ok(关系映射表)
}

/// Target 有相对式（`slides/slide1.xml`）与绝对式（`/ppt/slides/slide1.xml`）两种，归一到 zip 内路径。
fn 归一关系目标(关系目标: &str) -> String {
    let 去斜杠 = 关系目标.trim_start_matches('/');
    if 去斜杠.starts_with("ppt/") {
        去斜杠.to_string()
    } else if 去斜杠.starts_with("../") {
        let 去上级 = 去斜杠.trim_start_matches("../");
        format!("ppt/{去上级}")
    } else {
        format!("ppt/{去斜杠}")
    }
}

/// `sldIdLst` 的顺序 ⇒ 关系标识顺序表；`sldId` 自带的无前缀 `id`（页编号）不算关系。
fn 收集页序(演示正文: &str) -> Result<Vec<String>, u32> {
    let mut 读取器 = 文档读取器::from_str(演示正文);
    读取器.config_mut().expand_empty_elements = true;
    let mut 文档版本 = 默认XML版本;
    let mut 页序标识表: Vec<String> = Vec::new();
    let mut 节点深度 = 0usize;
    let mut 清单层级 = 0usize;
    let mut 见到页清单 = false;
    loop {
        let (空间结果, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        let 是演示节点 = matches!(空间结果, 命名空间结果::Bound(空间名称) if 空间名称.as_ref() == 演示命名空间);
        match 事件值 {
            文档事件::Start(标签值) => {
                节点深度 += 1;
                if 节点深度 > 64 {
                    return Err(错误码::内容不合法);
                }
                if !是演示节点 {
                    continue;
                }
                match 标签值.local_name().as_ref() {
                    "sldIdLst" => {
                        见到页清单 = true;
                        清单层级 = 节点深度;
                    }
                    "sldId" if 清单层级 != 0 => {
                        for 属性结果 in 标签值.attributes() {
                            let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                            if 属性项.key.prefix().is_none() || 属性项.key.local_name().as_ref() != "id" {
                                continue;
                            }
                            let 值文本 = 属性项
                                .normalized_value(文档版本)
                                .map_err(|_| 错误码::内容不合法)?
                                .into_owned();
                            if 值文本.is_empty() {
                                return Err(错误码::内容不合法);
                            }
                            页序标识表.push(值文本);
                        }
                    }
                    _ => {}
                }
            }
            文档事件::End(标签值) => {
                if 是演示节点 && 标签值.local_name().as_ref() == "sldIdLst" {
                    清单层级 = 0;
                }
                节点深度 = 节点深度.checked_sub(1).ok_or(错误码::内容不合法)?;
            }
            文档事件::Decl(声明值) => {
                文档版本 = 声明值.xml_version().map_err(|_| 错误码::内容不合法)?;
            }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    if !见到页清单 {
        return Err(错误码::内容不合法);
    }
    Ok(页序标识表)
}

/// 一页的标题：先取标题占位符（`ph type=title` / `ctrTitle`）的文字；
/// 没有占位符时退化为**该页第一个非空形状的文字**（实测商业 PPT 多用自由文本框，页里根本没有 ph）。
/// 返回 `(标题, 来源)`，来源取值 `标题占位符` / `首段文字` / 空串。
fn 提取页标题(页正文: &str) -> Result<(String, String, Vec<String>), u32> {
    let mut 读取器 = 文档读取器::from_str(页正文);
    读取器.config_mut().expand_empty_elements = true;
    let mut 文档版本 = 默认XML版本;
    let mut 节点深度 = 0usize;
    let mut 形状层级 = 0usize;
    let mut 当前形状标记 = false;
    let mut 形状文字 = String::new();
    let mut 文本层级 = 0usize;
    let mut 标题文字 = String::new();
    let mut 首段文字 = String::new();
    let mut 占位已命中 = false;
    let mut 片段表: Vec<String> = Vec::new();
    const 片段上限: usize = 3;
    loop {
        let (空间结果, 事件值) = 读取器.read_resolved_event().map_err(|_| 错误码::内容不合法)?;
        let 是绘图节点 = matches!(空间结果, 命名空间结果::Bound(空间名称) if 空间名称.as_ref() == 绘图命名空间);
        match 事件值 {
            文档事件::Start(标签值) => {
                节点深度 += 1;
                if 节点深度 > 256 {
                    return Err(错误码::内容不合法);
                }
                let 节点名称 = 标签值.local_name();
                match 节点名称.as_ref() {
                    "sp" => {
                        形状层级 = 节点深度;
                        当前形状标记 = false;
                        形状文字.clear();
                    }
                    "ph" if 形状层级 != 0 => {
                        for 属性结果 in 标签值.attributes() {
                            let 属性项 = 属性结果.map_err(|_| 错误码::内容不合法)?;
                            if 属性项.key.local_name().as_ref() != "type" {
                                continue;
                            }
                            let 值文本 = 属性项
                                .normalized_value(文档版本)
                                .map_err(|_| 错误码::内容不合法)?
                                .into_owned();
                            if 值文本 == "title" || 值文本 == "ctrTitle" {
                                当前形状标记 = true;
                            }
                        }
                    }
                    // 所有形状的文字都收：标题占位符与「首段文字兜底」都要用（只收标题会让兜底永远为空）。
                    "t" if 是绘图节点 && 形状层级 != 0 => {
                        文本层级 = 节点深度;
                    }
                    _ => {}
                }
            }
            文档事件::End(标签值) => {
                match 标签值.local_name().as_ref() {
                    "t" => 文本层级 = 0,
                    "sp" => {
                        let 形状正文 = 形状文字.trim().to_string();
                        if 当前形状标记 && !占位已命中 && !形状正文.is_empty() {
                            标题文字 = 形状正文.clone();
                            占位已命中 = true;
                        } else if !当前形状标记 && 首段文字.is_empty() && !形状正文.is_empty() {
                            首段文字 = 形状正文.clone();
                        }
                        // 前几个非空形状都留：商业 PPT 常见「每页第一个形状是页眉/logo」，
                        // 只给首段会让调用方把页眉当标题（实测苏蜜雅 36 页全被页眉占据）。
                        if !形状正文.is_empty()
                            && 片段表.len() < 片段上限
                            && 片段表.last() != Some(&形状正文) {
                            片段表.push(形状正文);
                        }
                        形状层级 = 0;
                        当前形状标记 = false;
                        形状文字.clear();
                    }
                    _ => {}
                }
                节点深度 = 节点深度.checked_sub(1).ok_or(错误码::内容不合法)?;
            }
            文档事件::Text(文本节点) => {
                if 文本层级 != 0 {
                    形状文字.push_str(&文本节点.xml_content(文档版本));
                }
            }
            文档事件::CData(文本节点) if 文本层级 != 0 => {
                形状文字.push_str(&文本节点.xml_content(文档版本));
            }
            文档事件::Decl(声明值) => {
                文档版本 = 声明值.xml_version().map_err(|_| 错误码::内容不合法)?;
            }
            文档事件::DocType(_) => return Err(错误码::内容不合法),
            文档事件::Eof => break,
            _ => {}
        }
    }
    if 占位已命中 {
        return Ok((标题文字, "标题占位符".to_string(), 片段表));
    }
    if 首段文字.is_empty() {
        return Ok((String::new(), String::new(), 片段表));
    }
    // 首段文字只取第一行：整段多行文字当标题会把正文也塞进去。
    let 首段首行 = 首段文字.lines().next().unwrap_or("").trim().to_string();
    Ok((首段首行, "首段文字".to_string(), 片段表))
}
