use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 规范化JSON: u32 = 5201;
    pub const 按指针取值: u32 = 5202;
    pub const 按指针取文本: u32 = 5203;
    pub const 提取摘要: u32 = 5204;
    pub const 按字段查找: u32 = 5205;
    pub const 过滤: u32 = 5206;
    pub const 映射转换: u32 = 5207;
    pub const 按字段排序: u32 = 5208;
    pub const 列表添加: u32 = 5209;
    pub const 列表移除: u32 = 5210;
    pub const 展平字典: u32 = 5211;
    pub const 展平结构条目: u32 = 5212;
    pub const 规范化条目指纹: u32 = 5213;
}
pub mod 错误码 {
    pub const JSON参数不合法: u32 = 5201;
    pub const JSON路径不存在: u32 = 5202;
    pub const JSON类型不符: u32 = 5203;
    pub const JSON资源受限: u32 = 5204;
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
        错误码::JSON参数不合法,
        "JSON参数不合法\0".as_bytes(),
        "JSON参数不合法\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::JSON路径不存在,
        "JSON路径不存在\0".as_bytes(),
        "JSON路径不存在\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::JSON类型不符,
        "JSON类型不符\0".as_bytes(),
        "JSON类型不符\0".as_bytes(),
        0,
        0,
        0,
    ),
    码项(
        错误码::JSON资源受限,
        "JSON资源受限\0".as_bytes(),
        "JSON资源受限\0".as_bytes(),
        0,
        0,
        0,
    ),
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> {
    v1_contract::表段::构造(错误码信息表.as_ptr(), 4)
}
