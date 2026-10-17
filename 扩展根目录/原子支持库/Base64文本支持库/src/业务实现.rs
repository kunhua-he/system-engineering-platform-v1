use crate::编号与码面::{能力号, 错误码};
pub fn 执行文本操作(操作号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 文本参数表.iter().any(|文本参数表| 文本参数表.len() > 65536) {
        return Err(错误码::资源受限);
    }
    let 取文本 = |参数位置: usize| 文本参数表.get(参数位置).copied().ok_or(错误码::参数不合法);

    use base64::Engine as _;
    let 原文 = 取文本(0)?;
    let 输出文本 = match 操作号 {
        能力号::标准编码 | 能力号::网址安全编码 => {
            if 原文.len() > 49152 {
                return Err(错误码::资源受限);
            }
            if 操作号 == 能力号::标准编码 {
                base64::engine::general_purpose::STANDARD.encode(原文.as_bytes())
            } else {
                base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(原文.as_bytes())
            }
        }
        能力号::标准解码 | 能力号::网址安全解码 => {
            let 字节组 = if 操作号 == 能力号::标准解码 {
                base64::engine::general_purpose::STANDARD.decode(原文)
            } else {
                base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(原文)
            }
            .map_err(|_| 错误码::内容不合法)?;
            String::from_utf8(字节组).map_err(|_| 错误码::内容不合法)?
        }
        _ => return Err(错误码::参数不合法),
    };

    if 输出文本.len() > 65536 {
        return Err(错误码::资源受限);
    }
    Ok((4, 输出文本.into_bytes()))
}
