use v1_contract::{数据槽, 类型标签, 执行函数};
use crate::命令声明面::{命令表内位, 函数表项数};
use crate::{能力号,错误码};
unsafe fn 处理识别调用(参数个数:u32,参数表:*const 数据槽) -> Result<数据槽,u32> {
    if 参数个数 != 1 || 参数表.is_null() { return Err(错误码::参数不合法); }
    let 参数槽 = unsafe { &*参数表 };
    if 参数槽.类型标签.取号值() != 4 || !参数槽.是否引用() || 参数槽.槽值 == 0 || 参数槽.槽字节长度 > 16384 { return Err(错误码::参数不合法); }
    let 文本字节 = unsafe { std::slice::from_raw_parts(参数槽.槽值 as *const u8,参数槽.槽字节长度 as usize) };
    let 图片路径 = std::str::from_utf8(文本字节).map_err(|_| 错误码::参数不合法)?;
    let 返回正文 = crate::识别提供者::识别图片文字(图片路径)?;
    if 返回正文.len() > 65536 { return Err(错误码::图片资源超限); }
    let 返回字节 = 返回正文.into_bytes().into_boxed_slice();
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节) as *const u8;
    Ok(数据槽::指针(类型标签::构造(4),返回指针 as u64,返回长度,true))
}
pub unsafe extern "C-unwind" fn 识别图片入口(返回槽:*mut 数据槽,参数个数:u32,参数表:*const 数据槽) {
    if 返回槽.is_null() { return; }
    unsafe { *返回槽 = 处理识别调用(参数个数,参数表).unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX),失败码 as u64,4)); }
}
pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [识别图片入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::识别图片文字)] = 识别图片入口;
    本表
}
pub(crate) const 执行函数表:[执行函数;函数表项数] = 造函数表();
