use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 规范化网址: u32 = 4201;
    pub const 合并相对网址: u32 = 4202;
    pub const 取查询参数JSON: u32 = 4203;
    pub const 提取外部标识: u32 = 4204;
}
pub mod 错误码 {
    pub const 参数不合法: u32 = 4201;
    pub const 内容不合法: u32 = 4202;
    pub const 资源受限: u32 = 4203;
    pub const 标识无法识别: u32 = 4205;
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

pub const 错误码信息表: [错误码信息; 4] = [
    码项(
        错误码::参数不合法,
        "参数不合法\0".as_bytes(),
        "参数不合法\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::内容不合法,
        "内容不合法\0".as_bytes(),
        "内容不合法\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::资源受限,
        "资源受限\0".as_bytes(),
        "资源受限\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::标识无法识别,
        "标识无法识别\0".as_bytes(),
        "标识无法识别:youtube 需 11 位且后继断开；arxiv 需 新式 数字.数字 或 旧式 分类/7位数字。\0".as_bytes(),
        0,
        0,
        0,
    ),
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> {
    v1_contract::表段::构造(错误码信息表.as_ptr(), 4)
}
