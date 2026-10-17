use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    use url::Url as 网址解析器;
    let 网址值 = 网址解析器::parse(取文本(0)?).map_err(|_| 错误码::内容不合法)?;
    let 输出文本 = match 操作号 {
        能力号::规范化网址 => 网址值.to_string(),
        能力号::合并相对网址 => 网址值
            .join(取文本(1)?)
            .map_err(|_| 错误码::内容不合法)?
            .to_string(),
        能力号::取查询参数JSON => {
            let 参数对表 = 网址值
                .query_pairs()
                .map(|(参数名, 参数值)| (参数名.into_owned(), 参数值.into_owned()))
                .collect::<Vec<_>>();
            if 参数对表.len() > 1000 {
                return Err(错误码::资源受限);
            }
            serde_json::to_string(&参数对表).map_err(|_| 错误码::内容不合法)?
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
