use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 求值公式: u32 = 6110;
    pub const 解析标记块: u32 = 6111;
    pub const 解析DOCX: u32 = 6112;
    pub const 生成DOCX: u32 = 6113;
    pub const 解析XLSX: u32 = 6114;
    pub const 生成XLSX: u32 = 6115;
}
pub mod 错误码 {
    pub const 参数不合法: u32 = 6101;
    pub const 计算失败: u32 = 6102;
    pub const 内容不合法: u32 = 6103;
    pub const 写出失败: u32 = 6104;
}
pub const fn 码项(
    错误码值: u32,
    名称: &'static [u8],
    描述: &'static [u8],
    可重试: u8,
    可自愈: u8,
    需人工: u8,
) -> 错误码信息 {
    错误码信息 {
        码值: 错误码值,
        段位: 错误码值 / 1000,
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
        "参数个数或写法不合契约\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::计算失败,
        "计算失败\0".as_bytes(),
        "公式非法、变量缺失或除零\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::内容不合法,
        "内容不合法\0".as_bytes(),
        "输入文本不是合法结构\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::写出失败,
        "写出失败\0".as_bytes(),
        "目标路径不可写或写盘中断\0".as_bytes(),
        1,
        0,
        0,
    ),
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> {
    v1_contract::表段::构造(错误码信息表.as_ptr(), 4)
}
