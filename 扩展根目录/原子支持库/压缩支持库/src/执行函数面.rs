use v1_contract::{数据槽, 类型标签, 执行函数};
use crate::编号与码面::{能力号, 错误码};
use crate::命令声明面::{函数表项数, 命令表内位};
unsafe fn 处理文本(操作号: u32, 参数个数: u32, 参数表: *const 数据槽) -> Result<数据槽, u32> {
    if 参数个数 != 1 || 参数表.is_null() { return Err(错误码::压缩参数不合法); }
    let 槽项 = unsafe { &*参数表 };
    if 槽项.类型标签.取号值() != 4 || !槽项.是否引用() || 槽项.槽字节长度 > 196608 || (槽项.槽值 == 0 && 槽项.槽字节长度 != 0) { return Err(错误码::压缩参数不合法); }
    let 文本字节 = if 槽项.槽字节长度 == 0 { &[][..] } else { unsafe { std::slice::from_raw_parts(槽项.槽值 as *const u8,槽项.槽字节长度 as usize) } };
    let 输入文本 = std::str::from_utf8(文本字节).map_err(|_|错误码::压缩参数不合法)?;
    let 返回文本 = crate::业务实现::执行文本操作(操作号,输入文本)?;
    let 返回字节 = 返回文本.into_bytes().into_boxed_slice();
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节) as *const u8;
    Ok(数据槽::指针(类型标签::构造(4),返回指针 as u64,返回长度,true))
}
unsafe fn 写文本调用(操作号: u32, 返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 返回槽.is_null() { return; }
    let 返回结果 = unsafe { 处理文本(操作号,参数个数,参数表) };
    unsafe { *返回槽 = 返回结果.unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX),失败码 as u64,4)); }
}
pub unsafe extern "C-unwind" fn 压缩文本入口(返回槽: *mut 数据槽,参数个数: u32,参数表: *const 数据槽) { unsafe { 写文本调用(能力号::压缩文本,返回槽,参数个数,参数表); } }
pub unsafe extern "C-unwind" fn 解压文本入口(返回槽: *mut 数据槽,参数个数: u32,参数表: *const 数据槽) { unsafe { 写文本调用(能力号::解压文本,返回槽,参数个数,参数表); } }
pub const fn 造函数表() -> [执行函数; 函数表项数] { let mut 本表 = [压缩文本入口 as 执行函数; 函数表项数];
本表[命令表内位(能力号::压缩文本)] = 压缩文本入口;
本表[命令表内位(能力号::解压文本)] = 解压文本入口;
本表 }
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
