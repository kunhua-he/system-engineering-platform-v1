use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    use sha2::Digest as _;
    let 原文 = 取文本(0)?;
    let 字节组 = match 操作号 {
        能力号::计算SHA256 => sha2::Sha256::digest(原文.as_bytes()).to_vec(),
        能力号::计算SHA512 => sha2::Sha512::digest(原文.as_bytes()).to_vec(),
        _ => return Err(错误码::参数不合法),
    };
    let 输出文本 = 字节组
        .iter()
        .map(|字节值| format!("{字节值:02x}"))
        .collect::<String>();

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
