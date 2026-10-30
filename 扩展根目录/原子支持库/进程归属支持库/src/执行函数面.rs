use crate::命令声明面::{函数表项数, 命令表内位, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};

const 文本上限字节: u64 = 4194304;

unsafe fn 读文本槽(槽项: &数据槽) -> Result<String, u32> {
    if 槽项.类型标签.取号值() != 4 {
        return Err(错误码::归属参数不合法);
    }
    let 字节长度 = 槽项.槽字节长度 as usize;
    if 字节长度 > 文本上限字节 as usize {
        return Err(错误码::归属资源受限);
    }
    if 字节长度 == 0 {
        return Ok(String::new());
    }
    if !槽项.是否引用() {
        let 内联字节 = 槽项.槽值.to_le_bytes();
        if 字节长度 > 内联字节.len() {
            return Err(错误码::归属参数不合法);
        }
        return std::str::from_utf8(&内联字节[..字节长度])
            .map(str::to_owned)
            .map_err(|_| 错误码::归属内容不合法);
    }
    if 槽项.槽值 == 0 {
        return Err(错误码::归属参数不合法);
    }
    let 文本字节 = unsafe { std::slice::from_raw_parts(槽项.槽值 as *const u8, 字节长度) };
    std::str::from_utf8(文本字节)
        .map(str::to_owned)
        .map_err(|_| 错误码::归属内容不合法)
}

unsafe fn 处理调用(
    编号: u32, 参数个数: u32, 参数表: *const 数据槽
) -> Result<数据槽, u32> {
    if 参数表.is_null() || 参数个数 != 造命令表()[命令表内位(编号)].参数个数 {
        return Err(错误码::归属参数不合法);
    }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    let 返回文本 = match 编号 {
        能力号::判定进程归属 => {
            let 进程表 = unsafe { 读文本槽(&参数槽[0]) }?;
            let 归属登记 = unsafe { 读文本槽(&参数槽[1]) }?;
            let 保护参数 = unsafe { 读文本槽(&参数槽[2]) }?;
            crate::业务实现::执行判定进程归属(&进程表, &归属登记, &保护参数)?
        }
        能力号::读取进程表 => {
            let 筛选参数 = unsafe { 读文本槽(&参数槽[0]) }?;
            crate::业务实现::执行读取进程表(&筛选参数)?
        }
        _ => return Err(错误码::归属参数不合法),
    };
    let 返回字节 = 返回文本.into_bytes();
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(
        类型标签::构造(4),
        返回指针 as u64,
        返回长度,
        true,
    ))
}

unsafe fn 写调用(
    编号: u32, 返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽
) {
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

pub unsafe extern "C-unwind" fn 判定进程归属入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::判定进程归属, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 读取进程表入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::读取进程表, 返回槽, 参数个数, 参数表);
    }
}

pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [判定进程归属入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::判定进程归属)] = 判定进程归属入口;
    本表[命令表内位(能力号::读取进程表)] = 读取进程表入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
