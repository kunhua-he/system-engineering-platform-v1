use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    let 原文 = 取文本(0)?;
    let 输出文本 = match 操作号 {
        能力号::规范化日期 => chrono::DateTime::parse_from_rfc3339(原文)
            .map_err(|_| 错误码::内容不合法)?
            .with_timezone(&chrono::Utc)
            .to_rfc3339(),
        能力号::格式化日期 => {
            let 格式文本 = 取文本(1)?;
            if 格式文本.len() > 1024 {
                return Err(错误码::资源受限);
            }
            if chrono::format::StrftimeItems::new(格式文本)
                .any(|格式项| matches!(格式项, chrono::format::Item::Error))
            {
                return Err(错误码::内容不合法);
            }
            let 日期值 = chrono::DateTime::parse_from_rfc3339(原文)
                .map_err(|_| 错误码::内容不合法)?;
            let mut 格式输出 = String::new();
            std::fmt::write(&mut 格式输出, format_args!("{}", 日期值.format_with_items(chrono::format::StrftimeItems::new(格式文本))))
                .map_err(|_| 错误码::内容不合法)?;
            格式输出
        }
        能力号::按格式解析 => {
            let 格式文本 = 取文本(1)?;
            if 格式文本.len() > 1024 {
                return Err(错误码::资源受限);
            }
            chrono::DateTime::parse_from_str(原文, 格式文本)
                .map_err(|_| 错误码::内容不合法)?
                .to_rfc3339()
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
