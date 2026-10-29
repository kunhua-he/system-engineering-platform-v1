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
        能力号::取当前时间 => {
            let 偏移分钟: i32 = 取文本(0)?.trim().parse().map_err(|_| 错误码::内容不合法)?;
            if !(-1440..=1440).contains(&偏移分钟) {
                return Err(错误码::内容不合法);
            }
            let 时区偏移 = chrono::FixedOffset::east_opt(偏移分钟 * 60).ok_or(错误码::内容不合法)?;
            chrono::Utc::now()
                .with_timezone(&时区偏移)
                .to_rfc3339_opts(chrono::SecondsFormat::Secs, false)
        }
        能力号::计算间隔 => {
            let 起始时刻 = chrono::DateTime::parse_from_rfc3339(取文本(0)?).map_err(|_| 错误码::内容不合法)?;
            let 结束时刻 = chrono::DateTime::parse_from_rfc3339(取文本(1)?).map_err(|_| 错误码::内容不合法)?;
            let 毫秒差 = 结束时刻.signed_duration_since(起始时刻).num_milliseconds();
            let 单位 = 取文本(2)?;
            let 除数: i64 = match 单位 {
                "毫秒" => 1,
                "秒" => 1000,
                "分钟" => 60_000,
                "小时" => 3_600_000,
                "天" => 86_400_000,
                _ => return Err(错误码::内容不合法),
            };
            (毫秒差 / 除数).to_string()
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
