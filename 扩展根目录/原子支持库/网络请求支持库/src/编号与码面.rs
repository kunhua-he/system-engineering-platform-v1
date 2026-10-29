use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 获取文本: u32 = 2401;
    pub const 提交JSON文本: u32 = 2402;
    pub const 获取字节: u32 = 2403;
    pub const 下载文件: u32 = 2404;
    pub const 提交网络请求:u32=2405;
    pub const 读取网络任务:u32=2406;
    pub const 取消网络任务:u32=2407;
    pub const 释放网络任务:u32=2408;
    pub const 构建查询串:u32=2409;

}
pub mod 错误码 {
    pub const 参数不合法: u32 = 2401;
    pub const 内容不合法: u32 = 2402;
    pub const 资源受限: u32 = 2403;
    pub const 请求失败: u32 = 2404;
    pub const 状态不成功: u32 = 2405;
    pub const 文件已存在: u32 = 2406;
    pub const 写入失败: u32 = 2407;
    pub const 任务无效:u32=2408;
    pub const 任务已取消:u32=2409;
    pub const 出站被拒:u32=2410;
    pub const 任务未完成:u32=2411;
    pub const 请求超时:u32=2412;

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

pub const 错误码信息表: [错误码信息; 12] = [码项(错误码::参数不合法, "参数不合法\0".as_bytes(), "参数不合法\0".as_bytes(), 0, 0, 0),码项(错误码::内容不合法, "内容不合法\0".as_bytes(), "内容不合法\0".as_bytes(), 0, 0, 0),码项(错误码::资源受限, "资源受限\0".as_bytes(), "资源受限\0".as_bytes(), 0, 0, 0),码项(错误码::请求失败, "请求失败\0".as_bytes(), "请求失败\0".as_bytes(), 0, 0, 0),码项(错误码::状态不成功, "状态不成功\0".as_bytes(), "状态不成功\0".as_bytes(), 0, 0, 0),码项(错误码::文件已存在, "文件已存在\0".as_bytes(), "文件已存在\0".as_bytes(), 0, 0, 0),码项(错误码::写入失败, "写入失败\0".as_bytes(), "写入失败\0".as_bytes(), 0, 0, 0),码项(错误码::任务无效,"任务无效\0".as_bytes(),"任务无效\0".as_bytes(),0,0,0),码项(错误码::任务已取消,"任务已取消\0".as_bytes(),"任务已取消\0".as_bytes(),0,0,0),码项(错误码::出站被拒,"出站被拒\0".as_bytes(),"出站被拒\0".as_bytes(),0,0,0),码项(错误码::任务未完成,"任务未完成\0".as_bytes(),"任务未完成\0".as_bytes(),0,0,0),码项(错误码::请求超时,"请求超时\0".as_bytes(),"请求超时\0".as_bytes(),0,0,0)];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> { v1_contract::表段::构造(错误码信息表.as_ptr(), 12) }
