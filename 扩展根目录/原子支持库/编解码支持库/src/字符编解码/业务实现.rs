use crate::字符编解码::编号与码面::{能力号,错误码};
use encoding_rs::Encoding as 字符编码;
pub fn 执行业务操作(编号:u32,参数表:&[&[u8]])->Result<(u32,Vec<u8>),u32> {
    let 编码名=std::str::from_utf8(参数表[1]).map_err(|_|错误码::字符编解码参数不合法)?;
    let 编码=字符编码::for_label(编码名.as_bytes()).ok_or(错误码::字符编解码内容不合法)?;
    if 编号==能力号::字符编解码编码文本 {
        let 原文=std::str::from_utf8(参数表[0]).map_err(|_|错误码::字符编解码参数不合法)?;
        if 编码==encoding_rs::UTF_16LE || 编码==encoding_rs::UTF_16BE {
            let mut 字节=Vec::new();
            for 码元 in 原文.encode_utf16(){
                字节.extend_from_slice(&if 编码==encoding_rs::UTF_16LE {码元.to_le_bytes()}else{码元.to_be_bytes()});
            }
            return Ok((5,字节));
        }
        let (字节,_,有错误)=编码.encode(原文);
        if 有错误 {return Err(错误码::字符编解码内容不合法);}
        return Ok((5,字节.into_owned()));
    }
    let (原文,有错误)=编码.decode_without_bom_handling(参数表[0]);
    if 有错误 {return Err(错误码::字符编解码内容不合法);}
    Ok((4,原文.into_owned().into_bytes()))
}
