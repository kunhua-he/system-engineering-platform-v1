use crate::十六进制编解码::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::十六进制编解码资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::十六进制编解码参数不合法);

    let 原文 = 取文本(0)?;
    let 输出文本 = match 操作号 {
        能力号::十六进制编解码编码文本 => {
            if 原文.len() > 32768 {
                return Err(错误码::十六进制编解码资源受限);
            }
            原文
                .as_bytes()
                .iter()
                .map(|字节值| format!("{字节值:02X}"))
                .collect::<String>()
        }
        能力号::十六进制编解码解码文本 => {
            if !原文.len().is_multiple_of(2) {
                return Err(错误码::十六进制编解码内容不合法);
            }
            let mut 输出字节 = Vec::with_capacity(原文.len() / 2);
            for 字节对 in 原文.as_bytes().chunks_exact(2) {
                let 高位 = (字节对[0] as char).to_digit(16).ok_or(错误码::十六进制编解码内容不合法)?;
                let 低位 = (字节对[1] as char).to_digit(16).ok_or(错误码::十六进制编解码内容不合法)?;
                输出字节.push(((高位 << 4) | 低位) as u8);
            }
            String::from_utf8(输出字节).map_err(|_| 错误码::十六进制编解码内容不合法)?
        }
        _ => return Err(错误码::十六进制编解码参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::十六进制编解码资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
