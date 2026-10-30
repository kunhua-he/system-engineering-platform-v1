use rust_xlsxwriter::{Workbook as 工作簿写入器, Worksheet as 工作表写入器, Formula as 公式对象};
use serde_json::{Value as 数据值, json as 构造数据};
use crate::编号与码面::错误码;
use crate::表格边界::{核矩形预算, 最大工作表数, 最大文件字节};

pub fn 生成表格(内容文本: &str, 输出路径: &str) -> Result<String, u32> {
    if !std::path::Path::new(输出路径).is_absolute() { return Err(错误码::参数不合法); }
    let 输入数据: 数据值 = serde_json::from_str(内容文本).map_err(|_| 错误码::参数不合法)?;
    let 工作表清单 = 输入数据.get("工作表列表").and_then(数据值::as_array).ok_or(错误码::参数不合法)?;
    if 工作表清单.is_empty() || 工作表清单.len() > 最大工作表数 { return Err(错误码::参数不合法); }
    let mut 工作簿 = 工作簿写入器::new();
    let mut 已用表名 = std::collections::HashSet::new();
    let mut 累计格数 = 0usize;
    for 表参数 in 工作表清单 {
        let 表名文本 = 表参数.get("表名").and_then(数据值::as_str).ok_or(错误码::参数不合法)?;
        if !已用表名.insert(表名文本.to_lowercase()) { return Err(错误码::参数不合法); }
        let 单表 = 工作簿.add_worksheet();
        单表.set_name(表名文本).map_err(|_| 错误码::参数不合法)?;
        let 空数组 = Vec::new();
        let 列清单 = match 表参数.get("列") {
            None => &空数组,
            Some(列数据) => 列数据.as_array().ok_or(错误码::参数不合法)?,
        };
        let 行清单 = match 表参数.get("行") {
            None => &空数组,
            Some(行数据) => 行数据.as_array().ok_or(错误码::参数不合法)?,
        };
        let mut 矩阵清单 = Vec::new();
        if !列清单.is_empty() { 矩阵清单.push(列清单); }
        for 单行 in 行清单 { 矩阵清单.push(单行.as_array().ok_or(错误码::参数不合法)?); }
        let 最大列数 = 矩阵清单.iter().map(|单行|单行.len()).max().unwrap_or(0);
        核矩形预算(矩阵清单.len(), 最大列数, &mut 累计格数, 错误码::参数不合法)?;
        for (行位序, 单行) in 矩阵清单.iter().enumerate() {
            for (列位序, 单元数据) in 单行.iter().enumerate() {
                写单元值(单表, 行位序 as u32, 列位序 as u16, 单元数据)?;
            }
        }
    }
    let 文件字节 = 工作簿.save_to_buffer().map_err(|_| 错误码::写出失败)?;
    if 文件字节.len() > 最大文件字节 { return Err(错误码::内容不合法); }
    std::fs::write(输出路径, &文件字节).map_err(|_| 错误码::写出失败)?;
    Ok(构造数据!({"输出路径":输出路径,"字节数":文件字节.len()}).to_string())
}

fn 写单元值(单表: &mut 工作表写入器, 行位序: u32, 列位序: u16, 单元数据: &数据值) -> Result<(), u32> {
    let 写入结果 = match 单元数据 {
        数据值::Null => return Ok(()),
        数据值::Bool(逻辑值) => 单表.write_boolean(行位序, 列位序, *逻辑值),
        数据值::String(单元文本) => 单表.write_string(行位序, 列位序, 单元文本),
        数据值::Number(单元数值) => {
            let 浮点值 = 单元数值.as_f64().filter(|浮点值|浮点值.is_finite()).ok_or(错误码::参数不合法)?;
            if (单元数值.is_i64() || 单元数值.is_u64()) && 浮点值.abs() > 999999999999999.0 { return Err(错误码::参数不合法); }
            单表.write_number(行位序, 列位序, 浮点值)
        }
        数据值::Object(单元对象) if 单元对象.len() == 1 => {
            let 公式文本 = 单元对象.get("公式").and_then(数据值::as_str).filter(|公式文本|公式文本.starts_with('=') && 公式文本.len() > 1).ok_or(错误码::参数不合法)?;
            单表.write_formula(行位序, 列位序, 公式对象::new(公式文本))
        }
        _ => return Err(错误码::参数不合法),
    };
    写入结果.map(|_|()).map_err(|_|错误码::参数不合法)
}
