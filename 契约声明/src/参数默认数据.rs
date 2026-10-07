// 生成物，禁手改。要改请改源并重跑生成器。
// 本件是 `契约声明/src/声明数据.rs` 按表拆出的子件（路由件以 `#[path]` 挂它）—— 故本件不单独声明、不重复源指纹。
// 生成器：构建装配/形态装配/生成声明.py

const 可抛错误码_0000: &[v1_contract::错误码] = &[];
pub fn 取生成命令表(编号: u32) -> Option<v1_contract::命令信息> {
    match 编号 {
        0 => Some(v1_contract::命令信息 { 名称: "取平台信息\0".as_bytes().as_ptr(), 说明: "返回底座自身的契约主结构指针（终生有效，调用方不得释放、不得修改）。\0".as_bytes().as_ptr(), 类别号: 0, 状态位: 0, 返回类型: v1_contract::类型标签::构造(0), 用户级别: 0, 参数个数: 1, 参数表: core::ptr::null(), 编号: v1_contract::能力号::构造(0), 可抛错误码: v1_contract::表段::构造(可抛错误码_0000.as_ptr(), 0) }),
        _ => None,
    }
}
pub fn 取生成默认值(编号: u32, 序号: usize) -> Option<v1_contract::数据槽> {
    match (编号, 序号) {
        (0, 0) => Some(v1_contract::数据槽::空槽()),
        _ => None,
    }
}
pub fn 取生成参数(编号: u32, 序号: usize) -> Option<v1_contract::参数信息> {
    let (名称, 说明, 标签, 状态位): (&str, &str, u32, u16) = match (编号, 序号) {
        (0, 0) => ("目标字宽\0", "占位参数：本底座只出 64 位，该参数恒传空值（类型标签 0、值 0），不接受 32 位请求。\0", 0, 0),
        _ => return None,
    };
    Some(v1_contract::参数信息 { 名称: 名称.as_bytes().as_ptr(), 说明: 说明.as_bytes().as_ptr(), 类型标签: v1_contract::类型标签::构造(标签), 状态位, 默认值: 取生成默认值(编号, 序号).unwrap_or(v1_contract::数据槽::空槽()) })
}
