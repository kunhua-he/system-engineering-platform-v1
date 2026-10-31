use crate::命令声明面::{函数表项数, 命令表内位};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};
unsafe fn 取文本(槽项: &数据槽) -> Result<String, u32> {
    if 槽项.类型标签.取号值() != 4 || 槽项.槽字节长度 > 65536 {
        return Err(错误码::连接参数不合法);
    }
    let 内联字节 = 槽项.槽值.to_le_bytes();
    let 文本字节 = if 槽项.是否引用() {
        if 槽项.槽值 == 0 {
            return Err(错误码::连接参数不合法);
        }
        unsafe {
            std::slice::from_raw_parts(槽项.槽值 as *const u8, 槽项.槽字节长度 as usize)
        }
    } else {
        内联字节
            .get(..槽项.槽字节长度 as usize)
            .ok_or(错误码::连接参数不合法)?
    };
    std::str::from_utf8(文本字节)
        .map(str::to_owned)
        .map_err(|_| 错误码::连接参数不合法)
}
unsafe fn 处理调用(
    编号: u32, 参数个数: u32, 参数表: *const 数据槽
) -> Result<数据槽, u32> {
    let 期望个数 = if [能力号::打开连接, 能力号::释放连接].contains(&编号) {
        1
    } else {
        2
    };
    if 参数个数 != 期望个数 || 参数表.is_null() {
        return Err(错误码::连接参数不合法);
    }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    if 编号 == 能力号::打开连接 {
        let 连接文本 = unsafe { 取文本(&参数槽[0]) }?;
        return Ok(数据槽::内联槽(
            类型标签::构造(6),
            crate::连接与句柄::打开连接(&连接文本)?,
            8,
        ));
    }
    if 参数槽[0].类型标签.取号值() != 6 {
        return Err(错误码::连接参数不合法);
    }
    let 连接编号 = 参数槽[0].槽值;
    let 返回整数 = match 编号 {
        能力号::释放连接 => crate::连接与句柄::释放连接(连接编号)?,
        能力号::执行事务 => {
            let 语句文本 = unsafe { 取文本(&参数槽[1]) }?;
            let 语句列表: Vec<String> =
                serde_json::from_str(&语句文本).map_err(|_| 错误码::连接参数不合法)?;
            crate::连接与句柄::事务(连接编号, &语句列表)?
        }
        能力号::只读查询 => {
            let 语句文本 = unsafe { 取文本(&参数槽[1]) }?;
            let 返回文本 = crate::连接与句柄::查询(连接编号, &语句文本)?;
            let 返回字节 = 返回文本.into_bytes().into_boxed_slice();
            let 返回长度 = 返回字节.len();
            let 返回指针 = Box::into_raw(返回字节) as *const u8;
            return Ok(数据槽::指针(
                类型标签::构造(4),
                返回指针 as u64,
                返回长度 as u64,
                true,
            ));
        }
        _ => return Err(错误码::连接参数不合法),
    };
    Ok(数据槽::内联槽(类型标签::构造(1), 返回整数 as u64, 8))
}
unsafe fn 写调用(
    编号: u32, 返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽
) {
    if 返回槽.is_null() {
        return;
    }
    let 执行返回 = unsafe { 处理调用(编号, 参数个数, 参数表) };
    unsafe {
        *返回槽 = 执行返回.unwrap_or_else(|失败码| {
            数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)
        });
    }
}
pub unsafe extern "C-unwind" fn 打开连接入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::打开连接, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 只读查询入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::只读查询, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 执行事务入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::执行事务, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 释放连接入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::释放连接, 返回槽, 参数个数, 参数表);
    }
}
pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [打开连接入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::打开连接)] = 打开连接入口;
    本表[命令表内位(能力号::只读查询)] = 只读查询入口;
    本表[命令表内位(能力号::执行事务)] = 执行事务入口;
    本表[命令表内位(能力号::释放连接)] = 释放连接入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
