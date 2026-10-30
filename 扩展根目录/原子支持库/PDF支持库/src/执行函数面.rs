use v1_contract::{数据槽, 类型标签, 执行函数};

use crate::命令声明面::{命令表内位, 函数表项数};
use crate::编号与码面::{错误码, 能力号};

const 文本上限: u64 = 4096;

unsafe fn 取文本<'a>(参数表: *const 数据槽, 参数个数: u32, 参数序位: usize) -> Result<&'a str, u32> {
    if 参数序位 >= 参数个数 as usize {
        return Err(错误码::参数不合法);
    }
    let 参数槽位 = unsafe { &*参数表.add(参数序位) };
    if 参数槽位.类型标签.取号值() != 4 || !参数槽位.是否引用() || 参数槽位.槽值 == 0 || 参数槽位.槽字节长度 > 文本上限 {
        return Err(错误码::参数不合法);
    }
    let 字节 = unsafe { std::slice::from_raw_parts(参数槽位.槽值 as *const u8, 参数槽位.槽字节长度 as usize) };
    std::str::from_utf8(字节).map_err(|_| 错误码::参数不合法)
}

fn 完成(处理结果: Result<String, u32>) -> 数据槽 {
    let 正文 = match 处理结果 {
        Ok(值) => 值,
        Err(失败码) => return 数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4),
    };
    let 字节 = 正文.into_bytes().into_boxed_slice();
    let 字节长度 = 字节.len() as u64;
    let 指针 = Box::into_raw(字节) as *const u8;
    数据槽::指针(类型标签::构造(4), 指针 as u64, 字节长度, true)
}

unsafe fn 处理页数(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::PDF提供者::检测加密页数(unsafe { 取文本(参数表, 参数个数, 0)? })
}

unsafe fn 处理渲染(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 4 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::PDF提供者::渲染页面(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
        unsafe { 取文本(参数表, 参数个数, 2)? },
        unsafe { 取文本(参数表, 参数个数, 3).unwrap_or("") },
    )
}

unsafe fn 处理提取(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 2 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::PDF提供者::提取内嵌图(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
    )
}

unsafe fn 处理校验(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::PDF提供者::校验文件(unsafe { 取文本(参数表, 参数个数, 0)? })
}

macro_rules! 造入口 {
    ($入口名:ident, $处理:ident) => {
        pub unsafe extern "C-unwind" fn $入口名(
            返回槽: *mut 数据槽,
            参数个数: u32,
            参数表: *const 数据槽,
        ) {
            if 返回槽.is_null() {
                return;
            }
            let 处理结果 = unsafe { $处理(参数个数, 参数表) };
            unsafe { *返回槽 = 完成(处理结果) };
        }
    };
}

造入口!(页数入口, 处理页数);
造入口!(渲染入口, 处理渲染);
造入口!(提取入口, 处理提取);
造入口!(校验入口, 处理校验);

pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [页数入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::检测加密页数)] = 页数入口;
    本表[命令表内位(能力号::渲染页面)] = 渲染入口;
    本表[命令表内位(能力号::提取内嵌图)] = 提取入口;
    本表[命令表内位(能力号::校验文件)] = 校验入口;
    本表
}

pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
