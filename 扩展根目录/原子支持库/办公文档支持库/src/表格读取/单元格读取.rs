//! 单元格读取：单元值 → JSON 值、A1 引用 → 零基行列、单格可见样式组装。

use calamine::Data as 单元值;
use serde_json::{Value as 数据值, json as 构造数据};

use crate::编号与码面::错误码;

use super::样式解析::样式目录;

pub(super) fn 转换单元值(单元数据: &单元值) -> Result<数据值, u32> {
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

pub(super) fn 解析单元坐标(引用文本: &str) -> Result<(usize, usize), u32> {
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

pub(super) fn 组装样式格(行序位: usize, 列序位: usize, 格式序位: usize, 样式表: &样式目录) -> Option<数据值> {
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
