use crate::命令声明面::{函数表项数, 命令表内位, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};

/// 读一个参数槽：文本按字节取，句柄与整数按数值取；类型不对一律参数不合法。
fn 读参数槽(
    槽项: &数据槽,
    声明参数: &v1_contract::参数信息,
) -> Result<crate::业务实现::调用参数<'static>, u32> {
    if 槽项.类型标签 != 声明参数.类型标签 {
        return Err(错误码::参数不合法);
    }
    let 类型号 = 槽项.类型标签.取号值();
    if 类型号 == 6 || 类型号 == 1 {
        // 句柄与整数跨边界只是数值，不占字节
        if 槽项.槽字节长度 != 0 {
            return Err(错误码::参数不合法);
        }
        return Ok(crate::业务实现::调用参数::数值(槽项.槽值));
    }
    if !槽项.是否引用() || (槽项.槽值 == 0 && 槽项.槽字节长度 != 0) {
        return Err(错误码::参数不合法);
    }
    let 字节: &'static [u8] = if 槽项.槽字节长度 == 0 {
        &[]
    } else {
        unsafe {
            std::slice::from_raw_parts(槽项.槽值 as *const u8, 槽项.槽字节长度 as usize)
        }
    };
    if 类型号 == 4 {
        std::str::from_utf8(字节).map_err(|_| 错误码::参数不合法)?;
    }
    Ok(crate::业务实现::调用参数::文本(字节))
}

unsafe fn 处理调用(
    编号: u32, 参数个数: u32, 参数表: *const 数据槽
) -> Result<数据槽, u32> {
    if 参数表.is_null() || 参数个数 != 造命令表()[命令表内位(编号)].参数个数 {
        return Err(错误码::参数不合法);
    }
    let 输入字节上限 = 1_048_576u64;
    let 输出字节上限 = 4_194_304usize;
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    let 命令项 = &造命令表()[命令表内位(编号)];
    let mut 参数值表 = Vec::new();
    for (参数位置, 槽项) in 参数槽.iter().enumerate() {
        let 声明参数 = unsafe { &*命令项.参数表.add(参数位置) };
        if 槽项.槽字节长度 > 输入字节上限 {
            return Err(错误码::资源受限);
        }
        参数值表.push(读参数槽(槽项, 声明参数)?);
    }
    let (返回标签, 返回字节) = crate::业务实现::执行业务操作(编号, &参数值表)?;
    if 返回标签 == 3 {
        // 逻辑型走内联槽，不占堆
        let 逻辑值 = 返回字节.first().copied().unwrap_or(0) as u64;
        return Ok(数据槽::内联槽(类型标签::构造(3), 逻辑值, 0));
    }
    if 返回字节.len() > 输出字节上限 {
        return Err(错误码::资源受限);
    }
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(
        类型标签::构造(返回标签),
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
    unsafe {
        *返回槽 = 处理调用(编号, 参数个数, 参数表).unwrap_or_else(|失败码| {
            数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)
        });
    }
}

pub unsafe extern "C-unwind" fn 渲染组件树入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::渲染组件树, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 操作组件入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::操作组件, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 读组件状态入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::读组件状态, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 释放组件句柄入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::释放组件句柄, 返回槽, 参数个数, 参数表);
    }
}

pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [渲染组件树入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::渲染组件树)] = 渲染组件树入口;
    本表[命令表内位(能力号::操作组件)] = 操作组件入口;
    本表[命令表内位(能力号::读组件状态)] = 读组件状态入口;
    本表[命令表内位(能力号::释放组件句柄)] = 释放组件句柄入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
