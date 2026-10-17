use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    let 原文 = 取文本(0)?;
    let 输出文本 = match 操作号 {
        能力号::转JSON文本 => {
            let mut 读取器 = csv::ReaderBuilder::new()
                .has_headers(false)
                .flexible(true)
                .from_reader(原文.as_bytes());
            let mut 行表: Vec<Vec<String>> = Vec::new();
            for CSV记录 in 读取器.records() {
                let CSV记录 = CSV记录.map_err(|_| 错误码::内容不合法)?;
                if 行表.len() >= 1000 || CSV记录.len() > 256 {
                    return Err(错误码::资源受限);
                }
                行表.push(CSV记录.iter().map(str::to_owned).collect());
            }
            serde_json::to_string(&行表).map_err(|_| 错误码::内容不合法)?
        }
        能力号::从JSON文本生成 => {
            let 行表: Vec<Vec<String>> =
                serde_json::from_str(原文).map_err(|_| 错误码::内容不合法)?;
            if 行表.len() > 1000 || 行表.iter().any(|行项| 行项.len() > 256) {
                return Err(错误码::资源受限);
            }
            if 行表.iter().any(Vec::is_empty) {
                return Err(错误码::内容不合法);
            }
            let mut 写入器 = csv::WriterBuilder::new()
                .has_headers(false)
                .flexible(true)
                .from_writer(Vec::new());
            for 行项 in 行表 {
                写入器.write_record(行项).map_err(|_| 错误码::内容不合法)?;
            }
            let 字节组 = 写入器.into_inner().map_err(|_| 错误码::内容不合法)?;
            String::from_utf8(字节组).map_err(|_| 错误码::内容不合法)?
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
