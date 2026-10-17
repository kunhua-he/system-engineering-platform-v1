use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 编码组件: u32 = 4101;
    pub const 解码组件: u32 = 4102;
}
pub mod 错误码 {
    pub const 编码参数不合法: u32 = 4101;
    pub const 编码执行失败: u32 = 4102;
    pub const 编码资源受限: u32 = 4103;
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

pub const 错误码信息表: [错误码信息; 3] = [
码项(错误码::编码参数不合法, "编码参数不合法\0".as_bytes(), "编码参数不合法\0".as_bytes(),0,0,0),
码项(错误码::编码执行失败, "编码执行失败\0".as_bytes(), "编码执行失败\0".as_bytes(),0,0,0),
码项(错误码::编码资源受限, "编码资源受限\0".as_bytes(), "编码资源受限\0".as_bytes(),0,0,0),
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> { v1_contract::表段::构造(错误码信息表.as_ptr(), 3) }
