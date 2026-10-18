//! URI组件编解码：RFC3986未保留字符不变，其余UTF-8字节百分号编码。
use crate::URI组件编解码::编号与码面::错误码;
pub fn 执行文本操作(操作号: u32, 输入文本: &str) -> Result<String, u32> {
    if 输入文本.len() > 196608 { return Err(错误码::URI组件编解码编码资源受限); }
    if 操作号 == crate::URI组件编解码::编号与码面::能力号::URI组件编解码编码组件 {
        if 输入文本.len() > 65536 { return Err(错误码::URI组件编解码编码资源受限); }
        let mut 输出文本 = String::new();
        for 字节值 in 输入文本.bytes() {
            if 字节值.is_ascii_alphanumeric() || b"-._~".contains(&字节值) { 输出文本.push(字节值 as char); }
            else { 输出文本.push_str(&format!("%{字节值:02X}")); }
        }
        Ok(输出文本)
    } else {
        let 原文字节 = 输入文本.as_bytes();
        let mut 输出字节 = Vec::new();
        let mut 读取位置 = 0;
        while 读取位置 < 原文字节.len() {
            if 原文字节[读取位置] == b'%' {
                let 字节对 = 原文字节.get(读取位置+1..读取位置+3).ok_or(错误码::URI组件编解码编码参数不合法)?;
                let 高位 = (字节对[0] as char).to_digit(16).ok_or(错误码::URI组件编解码编码参数不合法)?;
                let 低位 = (字节对[1] as char).to_digit(16).ok_or(错误码::URI组件编解码编码参数不合法)?;
                输出字节.push(((高位<<4)|低位) as u8);
                读取位置 += 3;
            } else { 输出字节.push(原文字节[读取位置]); 读取位置 += 1; }
            if 输出字节.len() > 65536 { return Err(错误码::URI组件编解码编码资源受限); }
        }
        String::from_utf8(输出字节).map_err(|_| 错误码::URI组件编解码编码参数不合法)
    }
}
#[test]
fn 百分号中文零字节往返与拒错() {
    for 原文 in ["", "中文🙂", "A\0B", "+ /?%", "-._~"] {
        assert_eq!(执行文本操作(4102,&执行文本操作(4101,原文).unwrap()).unwrap(),原文);
    }
    for 坏文本 in ["%", "%GG", "%FF"] { assert!(执行文本操作(4102,坏文本).is_err()); }
    assert_eq!(执行文本操作(4102,"+").unwrap(),"+");
}
