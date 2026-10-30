use calamine::{Data as 单元值, Reader as 工作簿读取接口, Xlsx as 工作簿读取器};
use serde_json::{Value as 数据值, json as 构造数据};
use crate::编号与码面::错误码;
use crate::表格边界::{读取表格文件, 核矩形预算, 最大工作表数, 最大回读字节};

pub fn 解析表格(文件路径: &str) -> Result<String, u32> {
    let 文件字节 = 读取表格文件(文件路径)?;
    let mut 读取器 = 工作簿读取器::new(std::io::Cursor::new(文件字节)).map_err(|_| 错误码::内容不合法)?;
    let 表名清单 = 读取器.sheet_names().to_vec();
    if 表名清单.is_empty() || 表名清单.len() > 最大工作表数 { return Err(错误码::内容不合法); }
    let mut 块列表 = Vec::new();
    let mut 累计格数 = 0usize;
    let mut 累计文本字节 = 0usize;
    for 表名文本 in 表名清单 {
        let 数据区域 = 读取器.worksheet_range(&表名文本).map_err(|_| 错误码::内容不合法)?;
        let 公式区域 = 读取器.worksheet_formula(&表名文本).map_err(|_| 错误码::内容不合法)?;
        let 末格位序 = match (数据区域.end(), 公式区域.end()) {
            (Some(数据末格), Some(公式末格)) => Some((数据末格.0.max(公式末格.0), 数据末格.1.max(公式末格.1))),
            (数据末格, 公式末格) => 数据末格.or(公式末格),
        };
        let mut 表格数据 = Vec::new();
        if let Some((末行位序, 末列位序)) = 末格位序 {
            核矩形预算(末行位序 as usize + 1, 末列位序 as usize + 1, &mut 累计格数, 错误码::内容不合法)?;
            for 行位序 in 0..=末行位序 {
                let mut 单行数据 = Vec::new();
                for 列位序 in 0..=末列位序 {
                    let 单元数据 = if let Some(公式文本) = 公式区域.get_value((行位序, 列位序)).filter(|公式文本| !公式文本.is_empty()) {
                        数据值::String(format!("={公式文本}"))
                    } else {
                        转换单元值(数据区域.get_value((行位序, 列位序)).unwrap_or(&单元值::Empty))?
                    };
                    if let Some(单元文本) = 单元数据.as_str() {
                        累计文本字节 = 累计文本字节.checked_add(单元文本.len()).ok_or(错误码::内容不合法)?;
                        if 累计文本字节 > 最大回读字节 { return Err(错误码::内容不合法); }
                    }
                    单行数据.push(单元数据);
                }
                表格数据.push(单行数据);
            }
        }
        块列表.push(构造数据!({"类型":"工作表","文本":"","表格数据":表格数据,"来源位置":{"工作表":表名文本}}));
    }
    let 返回文本 = 构造数据!({"工作表数":块列表.len(),"块列表":块列表,"资源列表":[]}).to_string();
    if 返回文本.len() > 最大回读字节 { return Err(错误码::内容不合法); }
    Ok(返回文本)
}

fn 转换单元值(单元数据: &单元值) -> Result<数据值, u32> {
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
