use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    let 原文 = 取文本(0)?;
    if 原文.as_bytes().contains(&0) {
        return Err(错误码::内容不合法);
    }
    let 路径值 = std::path::Path::new(原文);
    let 输出文本 = match 操作号 {
        能力号::合并路径 => {
            let 子路径 = 取文本(1)?;
            if 子路径.as_bytes().contains(&0) {
                return Err(错误码::内容不合法);
            }
            路径值
                .join(子路径)
                .to_str()
                .ok_or(错误码::内容不合法)?
                .to_owned()
        }
        能力号::取父路径 => 路径值
            .parent()
            .map_or(Ok(""), |路径项| 路径项.to_str().ok_or(错误码::内容不合法))?
            .to_owned(),
        能力号::取文件名 => 路径值
            .file_name()
            .map_or(Ok(""), |名称项| 名称项.to_str().ok_or(错误码::内容不合法))?
            .to_owned(),
        能力号::取扩展名 => 路径值
            .extension()
            .map_or(Ok(""), |名称项| 名称项.to_str().ok_or(错误码::内容不合法))?
            .to_owned(),
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
