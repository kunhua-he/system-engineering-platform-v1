//! 数据槽到引擎封装的唯一桥；返回槽沿用契约复合载荷。
use crate::命令声明面::{函数表项数, 命令表内位};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合值, 编码复合值载荷, 解码复合值载荷};
use v1_contract::{执行函数, 数据槽, 类型标签};
unsafe fn 取文本(槽项: &数据槽) -> Result<String, u32> {
    if 槽项.类型标签.取号值() != 4 || !槽项.是否引用() || 槽项.槽值 == 0 || 槽项.槽字节长度 > 65536
    {
        return Err(错误码::数据库参数不合法);
    }
    let 文本字节 = unsafe {
        std::slice::from_raw_parts(槽项.槽值 as *const u8, 槽项.槽字节长度 as usize)
    };
    std::str::from_utf8(文本字节)
        .map(str::to_owned)
        .map_err(|_| 错误码::数据库参数不合法)
}
unsafe fn 处理调用(
    编号: u32, 参数个数: u32, 参数表: *const 数据槽
) -> Result<数据槽, u32> {
    if 参数个数 != 2 || 参数表.is_null() {
        return Err(错误码::数据库参数不合法);
    }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 2) };
    let 数据库路径 = unsafe { 取文本(&参数槽[0]) }?;
    if 编号 == 能力号::执行事务 {
        let 列表槽 = &参数槽[1];
        if 列表槽.类型标签.取号值() != 100
            || !列表槽.是否引用()
            || 列表槽.槽值 == 0
            || 列表槽.槽字节长度 > 4194304
        {
            return Err(错误码::数据库参数不合法);
        }
        let 列表字节 = unsafe {
            std::slice::from_raw_parts(列表槽.槽值 as *const u8, 列表槽.槽字节长度 as usize)
        };
        let 元素表 =
            解码复合值载荷(列表字节, 100).map_err(|_| 错误码::数据库参数不合法)?;
        let 语句列表 = 元素表
            .into_iter()
            .map(|元素项| match 元素项.值 {
                复合值::文本载荷(文本值) => Ok(文本值),
                _ => Err(错误码::数据库参数不合法),
            })
            .collect::<Result<Vec<_>, _>>()?;
        let 执行数 = crate::引擎封装::执行事务(&数据库路径, &语句列表)?;
        Ok(数据槽::内联槽(类型标签::构造(1), 执行数 as u64, 8))
    } else {
        let 查询语句 = unsafe { 取文本(&参数槽[1]) }?;
        let 查询结果 = crate::引擎封装::只读查询(&数据库路径, &查询语句)?;
        let 返回字节 =
            编码复合值载荷(103, &查询结果).map_err(|_| 错误码::数据库查询越界)?;
        let 返回长度 = 返回字节.len() as u64;
        let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
        Ok(数据槽::指针(
            类型标签::构造(103),
            返回指针 as u64,
            返回长度,
            true,
        ))
    }
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
pub unsafe extern "C-unwind" fn 执行事务入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::执行事务, 返回槽, 参数个数, 参数表);
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
pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [执行事务入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::执行事务)] = 执行事务入口;
    本表[命令表内位(能力号::只读查询)] = 只读查询入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
