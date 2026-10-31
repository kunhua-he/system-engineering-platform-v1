use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 打开连接: u32 = 5401;
    pub const 只读查询: u32 = 5402;
    pub const 执行事务: u32 = 5403;
    pub const 释放连接: u32 = 5404;
}
pub mod 错误码 {
    pub const 连接参数不合法: u32 = 5411;
    pub const 连接建立失败: u32 = 5412;
    pub const 数据库语句失败: u32 = 5413;
    pub const 连接句柄无效: u32 = 5414;
    pub const 连接资源受限: u32 = 5415;
    pub const 查询结果越界: u32 = 5416;
    pub const 连接不可继续: u32 = 5417;
}
pub const fn 码项(错误码: u32, 名称: &'static [u8]) -> 错误码信息 {
    错误码信息 {
        码值: 错误码,
        段位: 5,
        名称: 名称.as_ptr(),
        说明: 名称.as_ptr(),
        可重试: 0,
        可自愈: 0,
        需人工: 0,
        保留: 0,
    }
}
pub const 错误码信息表: [错误码信息; 7] = [
    码项(错误码::连接参数不合法, "连接参数不合法\0".as_bytes()),
    码项(错误码::连接建立失败, "连接建立失败\0".as_bytes()),
    码项(错误码::数据库语句失败, "数据库语句失败\0".as_bytes()),
    码项(错误码::连接句柄无效, "连接句柄无效\0".as_bytes()),
    码项(错误码::连接资源受限, "连接资源受限\0".as_bytes()),
    码项(错误码::查询结果越界, "查询结果越界\0".as_bytes()),
    码项(错误码::连接不可继续, "连接不可继续\0".as_bytes()),
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> {
    v1_contract::表段::构造(错误码信息表.as_ptr(), 7)
}
