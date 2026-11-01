use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 渲染页面骨架: u32 = 4910;
    pub const 渲染数据表格: u32 = 4911;
    pub const 渲染表单: u32 = 4912;
    pub const 渲染对话框: u32 = 4913;
    pub const 渲染侧栏布局: u32 = 4914;
    pub const 渲染桌面外壳: u32 = 4915;
    pub const 渲染输入控件: u32 = 4916;
    pub const 渲染按钮: u32 = 4917;
    pub const 渲染登录页: u32 = 4918;
    pub const 渲染桌面菜单栏: u32 = 4919;
    pub const 渲染桌面图标区: u32 = 4920;
    pub const 渲染桌面图标坞: u32 = 4921;
    pub const 渲染窗口: u32 = 4922;
    pub const 渲染桌面交互脚本: u32 = 4923;
    pub const 渲染完整桌面: u32 = 4924;
    pub const 渲染启动器: u32 = 4925;
    pub const 渲染区块组: u32 = 4926;
    pub const 渲染聊天消息流: u32 = 4927;
    pub const 渲染组件树: u32 = 4928;
}
pub mod 错误码 {
    pub const 参数不合法: u32 = 4921;
    pub const 内容不合法: u32 = 4922;
    pub const 资源受限: u32 = 4923;
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
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> {
    v1_contract::表段::构造(错误码信息表.as_ptr(), 3)
}
