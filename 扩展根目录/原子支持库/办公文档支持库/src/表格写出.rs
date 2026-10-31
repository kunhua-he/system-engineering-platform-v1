use rust_xlsxwriter::{
    Color as 颜色对象, Format as 格式对象, FormatAlign as 对齐枚举, FormatBorder as 边框枚举,
    FormatPattern as 图案枚举, Formula as 公式对象, Workbook as 工作簿写入器, Worksheet as 工作表写入器,
};
use serde_json::{Map as 对象表, Value as 数据值, json as 构造数据};

use crate::办公资源;
use crate::编号与码面::错误码;
use crate::表格边界::{核矩形预算, 最大工作表数, 最大文件字节, 最大表格行数, 最大表格列数};

const 合并写出上限: usize = 4096;
const 列宽条数上限: usize = 256;
const 行高条数上限: usize = 10000;

struct 格式规格 {
    是否加粗: bool,
    字号磅值: Option<f64>,
    字体名称: String,
    字体颜色: Option<u32>,
    底色值: Option<u32>,
    水平对位: Option<对齐枚举>,
    垂直对位: Option<对齐枚举>,
    是否换行: bool,
    数字格式: Option<String>,
    边框线型: Option<边框枚举>,
}

impl 格式规格 {
    fn 缺省规格() -> 格式规格 {
        格式规格 {
            是否加粗: false,
            字号磅值: None,
            字体名称: String::new(),
            字体颜色: None,
            底色值: None,
            水平对位: None,
            垂直对位: None,
            是否换行: false,
            数字格式: None,
            边框线型: None,
        }
    }
}

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
        let 合并清单 = 取合并清单(表参数)?;
        let 单表 = 工作簿.add_worksheet();
        单表.set_name(表名文本).map_err(|_| 错误码::参数不合法)?;
        // 合并先落：merge_range 会把首格写成空串，随后按矩阵写值再覆盖首格，值以矩阵为准。
        let mut 已占区域: Vec<(u32, u16, u32, u16)> = Vec::new();
        for 合并项 in &合并清单 {
            let 区域值 = 解析合并项(合并项)?;
            核合并越界(区域值)?;
            if 已占区域.iter().any(|区域项| 区域重叠(*区域项, 区域值)) { return Err(错误码::参数不合法); }
            核矩形预算(
                (区域值.2 - 区域值.0 + 1) as usize,
                (区域值.3 - 区域值.1 + 1) as usize,
                &mut 累计格数,
                错误码::参数不合法,
            )?;
            已占区域.push(区域值);
            单表.merge_range(区域值.0, 区域值.1, 区域值.2, 区域值.3, "", &格式对象::new())
                .map_err(|_| 错误码::参数不合法)?;
        }
        for (行位序, 单行) in 矩阵清单.iter().enumerate() {
            for (列位序, 单元数据) in 单行.iter().enumerate() {
                写单个单元(单表, 行位序 as u32, 列位序 as u16, 单元数据)?;
            }
        }
        写列宽清单(单表, 表参数)?;
        写行高清单(单表, 表参数)?;
    }
    let 文件字节 = 工作簿.save_to_buffer().map_err(|_| 错误码::写出失败)?;
    if 文件字节.len() > 最大文件字节 { return Err(错误码::内容超限); }
    办公资源::原子写出(输出路径, &文件字节)?;
    Ok(构造数据!({"输出路径":输出路径,"字节数":文件字节.len()}).to_string())
}

fn 写单个单元(单表: &mut 工作表写入器, 行位序: u32, 列位序: u16, 单元数据: &数据值) -> Result<(), u32> {
    let (内容值, 格式选项) = 拆解单元(单元数据)?;
    match 格式选项 {
        None => 写单元值(单表, 行位序, 列位序, 内容值),
        Some(格式值) => 写单元内容(单表, 行位序, 列位序, 内容值, Some(&格式值)),
    }
}

// 旧形状是裸标量或 {"公式":..}；新形状是 {"值":..,"样式":{..}}，两者都收。
fn 拆解单元<'a>(单元数据: &'a 数据值) -> Result<(&'a 数据值, Option<格式对象>), u32> {
    let 对象项 = match 单元数据 {
        数据值::Object(对象项) => 对象项,
        _ => return Ok((单元数据, None)),
    };
    if 对象项.contains_key("公式") {
        if 对象项.len() != 1 { return Err(错误码::参数不合法); }
        return Ok((单元数据, None));
    }
    let 内容值 = 对象项.get("值").ok_or(错误码::参数不合法)?;
    for 键名 in 对象项.keys() {
        if 键名 != "值" && 键名 != "样式" { return Err(错误码::参数不合法); }
    }
    let 格式选项 = match 对象项.get("样式") {
        None => None,
        Some(样式数据) => Some(构造单元格式(&解析样式规格(样式数据)?)?),
    };
    Ok((内容值, 格式选项))
}

fn 写单元值(单表: &mut 工作表写入器, 行位序: u32, 列位序: u16, 单元数据: &数据值) -> Result<(), u32> {
    写单元内容(单表, 行位序, 列位序, 单元数据, None)
}

fn 写单元内容(
    单表: &mut 工作表写入器,
    行位序: u32,
    列位序: u16,
    单元数据: &数据值,
    格式项: Option<&格式对象>,
) -> Result<(), u32> {
    let 空白格式 = 格式对象::new();
    let 采用格式 = 格式项.unwrap_or(&空白格式);
    let 写入结果 = match 单元数据 {
        数据值::Null => return Ok(()),
        数据值::Bool(逻辑值) => 单表.write_boolean_with_format(行位序, 列位序, *逻辑值, 采用格式),
        数据值::String(单元文本) => 单表.write_string_with_format(行位序, 列位序, 单元文本.as_str(), 采用格式),
        数据值::Number(单元数值) => {
            let 浮点值 = 单元数值.as_f64().filter(|浮点值|浮点值.is_finite()).ok_or(错误码::参数不合法)?;
            if (单元数值.is_i64() || 单元数值.is_u64()) && 浮点值.abs() > 999999999999999.0 { return Err(错误码::参数不合法); }
            单表.write_number_with_format(行位序, 列位序, 浮点值, 采用格式)
        }
        数据值::Object(单元对象) if 单元对象.len() == 1 => {
            let 公式文本 = 单元对象.get("公式").and_then(数据值::as_str).filter(|公式文本|公式文本.starts_with('=') && 公式文本.len() > 1).ok_or(错误码::参数不合法)?;
            单表.write_formula_with_format(行位序, 列位序, 公式对象::new(公式文本), 采用格式)
        }
        _ => return Err(错误码::参数不合法),
    };
    写入结果.map(|_|()).map_err(|_|错误码::参数不合法)
}

fn 取合并清单(表参数: &数据值) -> Result<Vec<&数据值>, u32> {
    match 表参数.get("合并列表") {
        None => Ok(Vec::new()),
        Some(合并数据) => {
            let 合并数组 = 合并数据.as_array().ok_or(错误码::参数不合法)?;
            if 合并数组.len() > 合并写出上限 { return Err(错误码::参数不合法); }
            Ok(合并数组.iter().collect())
        }
    }
}

fn 解析合并项(合并项: &数据值) -> Result<(u32, u16, u32, u16), u32> {
    let 对象项 = 合并项.as_object().ok_or(错误码::参数不合法)?;
    if let Some(区域数据) = 对象项.get("区域") {
        if 对象项.len() != 1 { return Err(错误码::参数不合法); }
        let 区域文本 = 区域数据.as_str().ok_or(错误码::参数不合法)?;
        let mut 分段遍历 = 区域文本.splitn(2, ':');
        let 首段文本 = 分段遍历.next().ok_or(错误码::参数不合法)?;
        let 末段文本 = 分段遍历.next().ok_or(错误码::参数不合法)?;
        let (首行位序, 首列位序) = 解析坐标文本(首段文本)?;
        let (末行位序, 末列位序) = 解析坐标文本(末段文本)?;
        return Ok((首行位序, 首列位序, 末行位序, 末列位序));
    }
    if 对象项.len() != 4 { return Err(错误码::参数不合法); }
    Ok((
        取行号项(对象项, "首行")?,
        取列号项(对象项, "首列")?,
        取行号项(对象项, "末行")?,
        取列号项(对象项, "末列")?,
    ))
}

fn 解析坐标文本(坐标文本: &str) -> Result<(u32, u16), u32> {
    let mut 列号值 = 0u32;
    let mut 行号拼文 = String::new();
    for 单字节 in 坐标文本.trim().bytes() {
        if 单字节 == b'$' {
            continue;
        } else if 单字节.is_ascii_uppercase() && 行号拼文.is_empty() {
            列号值 = 列号值
                .checked_mul(26)
                .and_then(|列号值| 列号值.checked_add((单字节 - b'A' + 1) as u32))
                .ok_or(错误码::参数不合法)?;
        } else if 单字节.is_ascii_digit() {
            行号拼文.push(单字节 as char);
        } else {
            return Err(错误码::参数不合法);
        }
    }
    let 行号值 = 行号拼文.parse::<u32>().map_err(|_| 错误码::参数不合法)?;
    if 列号值 == 0 || 行号值 == 0 { return Err(错误码::参数不合法); }
    Ok((行号值 - 1, (列号值 - 1) as u16))
}

fn 核合并越界(区域值: (u32, u16, u32, u16)) -> Result<(), u32> {
    let (首行位序, 首列位序, 末行位序, 末列位序) = 区域值;
    if 首行位序 > 末行位序 || 首列位序 > 末列位序 { return Err(错误码::参数不合法); }
    if 首行位序 == 末行位序 && 首列位序 == 末列位序 { return Err(错误码::参数不合法); }
    if 末行位序 as usize >= 最大表格行数 || 末列位序 as usize >= 最大表格列数 { return Err(错误码::参数不合法); }
    Ok(())
}

fn 区域重叠(左区域: (u32, u16, u32, u16), 右区域: (u32, u16, u32, u16)) -> bool {
    左区域.0 <= 右区域.2 && 右区域.0 <= 左区域.2 && 左区域.1 <= 右区域.3 && 右区域.1 <= 左区域.3
}

fn 写列宽清单(单表: &mut 工作表写入器, 表参数: &数据值) -> Result<(), u32> {
    let 列宽数据 = match 表参数.get("列宽") { None => return Ok(()), Some(数据项) => 数据项 };
    let 列宽数组 = 列宽数据.as_array().ok_or(错误码::参数不合法)?;
    if 列宽数组.len() > 列宽条数上限 { return Err(错误码::参数不合法); }
    for 列宽项 in 列宽数组 {
        let 对象项 = 列宽项.as_object().ok_or(错误码::参数不合法)?;
        if 对象项.len() != 2 { return Err(错误码::参数不合法); }
        let 列序位 = 取列号项(对象项, "列")?;
        let 宽度值 = 取浮点项(对象项, "宽")?;
        if !(宽度值 > 0.0 && 宽度值 <= 255.0) { return Err(错误码::参数不合法); }
        单表.set_column_width(列序位, 宽度值).map_err(|_| 错误码::参数不合法)?;
    }
    Ok(())
}

fn 写行高清单(单表: &mut 工作表写入器, 表参数: &数据值) -> Result<(), u32> {
    let 行高数据 = match 表参数.get("行高") { None => return Ok(()), Some(数据项) => 数据项 };
    let 行高数组 = 行高数据.as_array().ok_or(错误码::参数不合法)?;
    if 行高数组.len() > 行高条数上限 { return Err(错误码::参数不合法); }
    for 行高项 in 行高数组 {
        let 对象项 = 行高项.as_object().ok_or(错误码::参数不合法)?;
        if 对象项.len() != 2 { return Err(错误码::参数不合法); }
        let 行序位 = 取行号项(对象项, "行")?;
        let 高度值 = 取浮点项(对象项, "高")?;
        if !(高度值 > 0.0 && 高度值 <= 409.0) { return Err(错误码::参数不合法); }
        单表.set_row_height(行序位, 高度值).map_err(|_| 错误码::参数不合法)?;
    }
    Ok(())
}

fn 取行号项(对象项: &对象表<String, 数据值>, 键名: &str) -> Result<u32, u32> {
    let 号值 = 对象项.get(键名).and_then(数据值::as_u64).ok_or(错误码::参数不合法)?;
    let 行号值 = u32::try_from(号值).map_err(|_| 错误码::参数不合法)?;
    if 行号值 as usize >= 最大表格行数 { return Err(错误码::参数不合法); }
    Ok(行号值)
}

fn 取列号项(对象项: &对象表<String, 数据值>, 键名: &str) -> Result<u16, u32> {
    let 号值 = 对象项.get(键名).and_then(数据值::as_u64).ok_or(错误码::参数不合法)?;
    let 列号值 = u16::try_from(号值).map_err(|_| 错误码::参数不合法)?;
    if 列号值 as usize >= 最大表格列数 { return Err(错误码::参数不合法); }
    Ok(列号值)
}

fn 取浮点项(对象项: &对象表<String, 数据值>, 键名: &str) -> Result<f64, u32> {
    对象项
        .get(键名)
        .and_then(数据值::as_f64)
        .filter(|数值项| 数值项.is_finite())
        .ok_or(错误码::参数不合法)
}

fn 解析样式规格(样式数据: &数据值) -> Result<格式规格, u32> {
    let 对象项 = 样式数据.as_object().ok_or(错误码::参数不合法)?;
    let mut 规格值 = 格式规格::缺省规格();
    for (键名, 取值数据) in 对象项 {
        match 键名.as_str() {
            "加粗" => 规格值.是否加粗 = 取值数据.as_bool().ok_or(错误码::参数不合法)?,
            "字号" => {
                let 字号值 = 取值数据
                    .as_f64()
                    .filter(|字号值| 字号值.is_finite() && *字号值 >= 1.0 && *字号值 <= 409.0)
                    .ok_or(错误码::参数不合法)?;
                规格值.字号磅值 = Some(字号值);
            }
            "字体" => {
                let 字体文本 = 取值数据.as_str().ok_or(错误码::参数不合法)?;
                if 字体文本.is_empty() || 字体文本.chars().count() > 64 { return Err(错误码::参数不合法); }
                规格值.字体名称 = 字体文本.to_string();
            }
            "字体颜色" => 规格值.字体颜色 = Some(解析十六进制颜色(取值数据)?),
            "底色" => 规格值.底色值 = Some(解析十六进制颜色(取值数据)?),
            "水平对齐" => 规格值.水平对位 = Some(转换水平对齐枚举(取值数据.as_str().ok_or(错误码::参数不合法)?)?),
            "垂直对齐" => 规格值.垂直对位 = Some(转换垂直对齐枚举(取值数据.as_str().ok_or(错误码::参数不合法)?)?),
            "自动换行" => 规格值.是否换行 = 取值数据.as_bool().ok_or(错误码::参数不合法)?,
            "数字格式" => {
                let 格式文本 = 取值数据.as_str().ok_or(错误码::参数不合法)?;
                if 格式文本.is_empty() || 格式文本.chars().count() > 128 { return Err(错误码::参数不合法); }
                规格值.数字格式 = Some(格式文本.to_string());
            }
            "边框" => 规格值.边框线型 = Some(转换边框枚举(取值数据.as_str().ok_or(错误码::参数不合法)?)?),
            _ => return Err(错误码::参数不合法),
        }
    }
    Ok(规格值)
}

fn 解析十六进制颜色(取值数据: &数据值) -> Result<u32, u32> {
    let 颜色文本 = 取值数据.as_str().ok_or(错误码::参数不合法)?.trim().trim_start_matches('#');
    let 十六进制位 = if 颜色文本.len() == 8 {
        &颜色文本[2..]
    } else if 颜色文本.len() == 6 {
        颜色文本
    } else {
        return Err(错误码::参数不合法);
    };
    if !十六进制位.bytes().all(|单字节| 单字节.is_ascii_hexdigit()) { return Err(错误码::参数不合法); }
    u32::from_str_radix(十六进制位, 16).map_err(|_| 错误码::参数不合法)
}

fn 转换水平对齐枚举(对齐文本: &str) -> Result<对齐枚举, u32> {
    Ok(match 对齐文本.trim() {
        "左" | "left" => 对齐枚举::Left,
        "中" | "center" => 对齐枚举::Center,
        "右" | "right" => 对齐枚举::Right,
        "两端" | "justify" => 对齐枚举::Justify,
        "分散" | "distributed" => 对齐枚举::Distributed,
        "填充" | "fill" => 对齐枚举::Fill,
        "跨列居中" | "centerAcross" => 对齐枚举::CenterAcross,
        _ => return Err(错误码::参数不合法),
    })
}

fn 转换垂直对齐枚举(对齐文本: &str) -> Result<对齐枚举, u32> {
    Ok(match 对齐文本.trim() {
        "上" | "top" => 对齐枚举::Top,
        "中" | "center" | "vcenter" => 对齐枚举::VerticalCenter,
        "下" | "bottom" => 对齐枚举::Bottom,
        "两端" | "justify" => 对齐枚举::VerticalJustify,
        "分散" | "distributed" => 对齐枚举::VerticalDistributed,
        _ => return Err(错误码::参数不合法),
    })
}

fn 转换边框枚举(边框文本: &str) -> Result<边框枚举, u32> {
    Ok(match 边框文本.trim() {
        "无" | "none" => 边框枚举::None,
        "细" | "thin" => 边框枚举::Thin,
        "中" | "medium" => 边框枚举::Medium,
        "粗" | "thick" => 边框枚举::Thick,
        "双" | "double" => 边框枚举::Double,
        "虚线" | "dashed" => 边框枚举::Dashed,
        "点线" | "dotted" => 边框枚举::Dotted,
        _ => return Err(错误码::参数不合法),
    })
}

fn 构造单元格式(规格值: &格式规格) -> Result<格式对象, u32> {
    let mut 格式值 = 格式对象::new();
    if 规格值.是否加粗 { 格式值 = 格式值.set_bold(); }
    if let Some(字号值) = 规格值.字号磅值 { 格式值 = 格式值.set_font_size(字号值); }
    if !规格值.字体名称.is_empty() { 格式值 = 格式值.set_font_name(规格值.字体名称.as_str()); }
    if let Some(颜色值) = 规格值.字体颜色 { 格式值 = 格式值.set_font_color(颜色对象::RGB(颜色值)); }
    if let Some(颜色值) = 规格值.底色值 {
        格式值 = 格式值
            .set_pattern(图案枚举::Solid)
            .set_foreground_color(颜色对象::RGB(颜色值));
    }
    if let Some(对位值) = 规格值.水平对位 { 格式值 = 格式值.set_align(对位值); }
    if let Some(对位值) = 规格值.垂直对位 { 格式值 = 格式值.set_align(对位值); }
    if 规格值.是否换行 { 格式值 = 格式值.set_text_wrap(); }
    if let Some(格式文本) = &规格值.数字格式 { 格式值 = 格式值.set_num_format(格式文本.as_str()); }
    if let Some(线型值) = 规格值.边框线型 { 格式值 = 格式值.set_border(线型值); }
    Ok(格式值)
}