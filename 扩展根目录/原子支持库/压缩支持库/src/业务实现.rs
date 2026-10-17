//! zlib文本压缩：输入输出均显式有界，十六进制保留压缩字节，不接文件路径。
use crate::编号与码面::错误码;
use std::ffi::{c_int, c_ulong};
#[link(name = "z")]
unsafe extern "C" {
    #[link_name = "compress2"]
    fn zlib_compress(输出: *mut u8, 输出长度: *mut c_ulong, 输入字节指针: *const u8, 输入长度: c_ulong, 等级: c_int) -> c_int;
    #[link_name = "uncompress2"]
    fn zlib_uncompress(输出: *mut u8, 输出长度: *mut c_ulong, 输入字节指针: *const u8, 输入长度: *mut c_ulong) -> c_int;
}
const 原文上限: usize = 65536;
const 压缩上限: usize = 66560;
fn 解十六进制(压缩文本: &str) -> Result<Vec<u8>, u32> {
    if 压缩文本.len() > 压缩上限 * 2 || !压缩文本.len().is_multiple_of(2) { return Err(错误码::压缩参数不合法); }
    压缩文本.as_bytes().chunks_exact(2).map(|字节对| {
        let 高位 = (字节对[0] as char).to_digit(16).ok_or(错误码::压缩参数不合法)?;
        let 低位 = (字节对[1] as char).to_digit(16).ok_or(错误码::压缩参数不合法)?;
        Ok(((高位 << 4) | 低位) as u8)
    }).collect()
}
pub fn 执行文本操作(操作号: u32, 输入文本: &str) -> Result<String, u32> {
    if 操作号 == crate::编号与码面::能力号::压缩文本 {
        if 输入文本.len() > 原文上限 { return Err(错误码::压缩资源受限); }
        let mut 输出字节 = vec![0u8; 压缩上限];
        let mut 输出长度 = 输出字节.len() as c_ulong;
        let 状态码 = unsafe { zlib_compress(输出字节.as_mut_ptr(), &mut 输出长度, 输入文本.as_ptr(), 输入文本.len() as c_ulong, 6) };
        if 状态码 != 0 { return Err(错误码::压缩执行失败); }
        输出字节.truncate(输出长度 as usize);
        Ok(输出字节.iter().map(|字节值| format!("{字节值:02X}")).collect())
    } else {
        let 压缩字节 = 解十六进制(输入文本)?;
        let mut 输出字节 = vec![0u8; 原文上限];
        let mut 输出长度 = 输出字节.len() as c_ulong;
        let mut 输入长度 = 压缩字节.len() as c_ulong;
        let 状态码 = unsafe { zlib_uncompress(输出字节.as_mut_ptr(), &mut 输出长度, 压缩字节.as_ptr(), &mut 输入长度) };
        if 状态码 == -5 { return Err(错误码::压缩资源受限); }
        if 状态码 != 0 { return Err(错误码::压缩执行失败); }
        if 输入长度 as usize != 压缩字节.len() { return Err(错误码::压缩参数不合法); }
        输出字节.truncate(输出长度 as usize);
        String::from_utf8(输出字节).map_err(|_| 错误码::压缩参数不合法)
    }
}
#[test]
fn 中文空文和零字节往返() {
    for 原文 in ["", "中文🙂", "A\0B", "重复重复重复"] {
        let 压缩文 = 执行文本操作(3201, 原文).unwrap();
        assert_eq!(执行文本操作(3202, &压缩文).unwrap(), 原文);
    }
    assert!(执行文本操作(3202, "GG").is_err());
    assert!(执行文本操作(3202, "00").is_err());
}
