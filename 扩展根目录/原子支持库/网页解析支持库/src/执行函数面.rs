use crate::命令声明面::{函数表项数, 命令表内位, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};
unsafe fn 处理调用(编号: u32, 参数个数: u32, 参数表: *const 数据槽) -> Result<数据槽, u32> {
    if 参数表.is_null() || 参数个数 != 造命令表()[命令表内位(编号)].参数个数 { return Err(错误码::参数不合法); }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    let mut 字节参数表 = Vec::new();
    for (参数位置, 槽项) in 参数槽.iter().enumerate() {
        let 声明参数 = unsafe { &*造命令表()[命令表内位(编号)].参数表.add(参数位置) };
        if 槽项.类型标签 != 声明参数.类型标签 || !槽项.是否引用() || (槽项.槽值 == 0 && 槽项.槽字节长度 != 0) { return Err(错误码::参数不合法); }
        if 槽项.槽字节长度 > 65536 { return Err(错误码::资源受限); }
        let 文本字节 = if 槽项.槽字节长度 == 0 { &[][..] } else { unsafe { std::slice::from_raw_parts(槽项.槽值 as *const u8, 槽项.槽字节长度 as usize) } };
        if 槽项.类型标签.取号值() == 4 { std::str::from_utf8(文本字节).map_err(|_| 错误码::参数不合法)?; }
        字节参数表.push(文本字节);
    }
    let (返回标签, 返回字节) = crate::业务实现::执行业务操作(编号, &字节参数表)?;
    if 返回字节.len() > 65536 { return Err(错误码::资源受限); }
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(类型标签::构造(返回标签), 返回指针 as u64, 返回长度, true))
}
unsafe fn 写调用(编号: u32, 返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 返回槽.is_null() { return; }
    unsafe { *返回槽 = 处理调用(编号, 参数个数, 参数表).unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)); }
}
pub unsafe extern "C-unwind" fn 提取标题入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) { unsafe { 写调用(能力号::提取标题, 返回槽, 参数个数, 参数表); } }
pub unsafe extern "C-unwind" fn 提取正文入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) { unsafe { 写调用(能力号::提取正文, 返回槽, 参数个数, 参数表); } }
pub unsafe extern "C-unwind" fn 选择文本入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) { unsafe { 写调用(能力号::选择文本, 返回槽, 参数个数, 参数表); } }
pub unsafe extern "C-unwind" fn 选择属性入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) { unsafe { 写调用(能力号::选择属性, 返回槽, 参数个数, 参数表); } }
pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [提取标题入口 as 执行函数; 函数表项数];
本表[命令表内位(能力号::提取标题)] = 提取标题入口;
本表[命令表内位(能力号::提取正文)] = 提取正文入口;
本表[命令表内位(能力号::选择文本)] = 选择文本入口;
本表[命令表内位(能力号::选择属性)] = 选择属性入口;
本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
