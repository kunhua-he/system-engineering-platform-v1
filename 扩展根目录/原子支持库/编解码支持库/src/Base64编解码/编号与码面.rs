use v1_contract::错误码信息;
pub mod 能力号 {
    pub const BASE64编解码标准编码: u32 = 4301;
    pub const BASE64编解码标准解码: u32 = 4302;
    pub const BASE64编解码网址安全编码: u32 = 4303;
    pub const BASE64编解码网址安全解码: u32 = 4304;
}
pub mod 错误码 {
    pub const BASE64编解码参数不合法: u32 = 4301;
    pub const BASE64编解码内容不合法: u32 = 4302;
    pub const BASE64编解码资源受限: u32 = 4303;
}
pub const fn 码项(
    错误码: u32,
    名称: &'static [u8],
    描述: &'static [u8],
    可重试: u8,
    可自愈: u8,
    需人工: u8,
) -> 错误码信息 {
    错误码信息 {
        码值: 错误码,
        段位: 错误码 / 1000,
        名称: 名称.as_ptr(),
        说明: 描述.as_ptr(),
        可重试,
        可自愈,
        需人工,
        保留: 0,
    }
}

pub const BASE64编解码错误码信息表: [错误码信息; 3] = [
    码项(
        错误码::BASE64编解码参数不合法,
        "BASE64编解码参数不合法\0".as_bytes(),
        "BASE64编解码参数不合法\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::BASE64编解码内容不合法,
        "BASE64编解码内容不合法\0".as_bytes(),
        "BASE64编解码内容不合法\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::BASE64编解码资源受限,
        "BASE64编解码资源受限\0".as_bytes(),
        "BASE64编解码资源受限\0".as_bytes(),
        0,
        0,
        0,
    ),
];

