//! 执行函数表：一条 C 入口，落到业务实现。

use crate::命令声明面::{命令表内位, 函数表项数, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 类型标签, 数据槽};

unsafe fn 处理调用(编号: u32, 参数个数: u32, 参数表: *const 数据槽) -> Result<数据槽, u32> {
    if 参数表.is_null() || 参数个数 != 造命令表()[命令表内位(编号)].参数个数 {
        return Err(错误码::参数不合法);
    }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    let 首槽 = &参数槽[0];
    if 首槽.类型标签.取号值() != 4 || !首槽.是否引用() || (首槽.槽值 == 0 && 首槽.槽字节长度 != 0) {
        return Err(错误码::参数不合法);
    }
    if 首槽.槽字节长度 > 4 * 1024 * 1024 {
        return Err(错误码::资源超限);
    }
    let 文本字节 = if 首槽.槽字节长度 == 0 {
        &[][..]
    } else {
        unsafe { std::slice::from_raw_parts(首槽.槽值 as *const u8, 首槽.槽字节长度 as usize) }
    };
    let 文本 = std::str::from_utf8(文本字节).map_err(|_| 错误码::参数不合法)?;
    let 参数值: serde_json::Value = serde_json::from_str(文本).map_err(|_| 错误码::参数不合法)?;
    let 返回文本 = crate::业务实现::执行(编号, &参数值)?.to_string();
    let 返回字节 = 返回文本.into_bytes();
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(类型标签::构造(4), 返回指针 as u64, 返回长度, true))
}

unsafe fn 写调用(编号: u32, 返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 返回槽.is_null() {
        return;
    }
    let 返回结果 = unsafe { 处理调用(编号, 参数个数, 参数表) };
    unsafe {
        *返回槽 = 返回结果.unwrap_or_else(|失败码| {
            数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)
        });
    }
}

pub unsafe extern "C-unwind" fn 准备技能执行入口(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    unsafe { 写调用(能力号::准备技能执行, 返回槽, 参数个数, 参数表); }
}

pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [准备技能执行入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::准备技能执行)] = 准备技能执行入口;
    本表
}

pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
