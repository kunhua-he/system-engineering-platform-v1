//! 工作表正文附加扫描：合并区（mergeCell）与带格式格（c 上的 s 序位）两类附加信息。

use quick_xml::events::Event as 文档事件;
use quick_xml::reader::NsReader as 文档读取器;
use serde_json::{Value as 数据值, json as 构造数据};

use crate::编号与码面::错误码;
use crate::表格边界::{最大矩形格数, 最大表格列数, 最大表格行数};

use super::基础件::{取属性文本, XML嵌套深度上限};
use super::单元格读取::{组装样式格, 解析单元坐标};
use super::样式解析::样式目录;

const 合并条目上限: usize = 4096;

pub(super) fn 解析工作表附加(工作表文本: &str, 样式表: &样式目录) -> Result<(Vec<数据值>, Vec<数据值>), u32> {
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
