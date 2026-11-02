//! 读槽与调用 —— 入参槽校验（参数数 · 类型标签 · 长度）与返回槽写回。
//!
//! 五个受控号共用同一条读槽腿：拒绝类型标签不是 4、非引用槽、空槽与超 65536 字节的槽。

use v1_contract::{数据槽, 类型标签};

use crate::错误码;

use super::执行业务口;

fn 标准槽(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
    编号: u32,
    参数预期: usize,
) -> Result<Vec<Vec<u8>>, u32> {
    if 参数数 as usize != 参数预期 || 参数槽.is_null() || 返回槽.is_null() {
        return Err(错误码::参数不合法);
    }
    let 槽表 = unsafe { std::slice::from_raw_parts(参数槽, 参数数 as usize) };
    let mut 值表 = Vec::with_capacity(参数预期);
    for 槽 in 槽表 {
        if 槽.类型标签.取号值() != 4
            || !槽.是否引用()
            || 槽.槽字节长度 == 0
            || 槽.槽字节长度 > 65536
        {
            return Err(错误码::参数不合法);
        }
        let 字节 = unsafe {
            std::slice::from_raw_parts(槽.槽值 as *const u8, 槽.槽字节长度 as usize)
        };
        std::str::from_utf8(字节).map_err(|_| 错误码::参数不合法)?;
        值表.push(字节.to_vec());
    }
    let _ = 编号;
    Ok(值表)
}
pub(crate) unsafe fn 调用处理(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
    编号: u32,
) {
    if 返回槽.is_null() {
        return;
    }
    let 结果 = (|| -> Result<Vec<u8>, u32> {
        let 个数 = match 编号 {
            3120 => 4,
            3121 => 4,
            3122 => 3,
            3123 => 3,
            3124 => 3,
            _ => return Err(错误码::参数不合法),
        };
        let 入参 = 标准槽(返回槽, 参数数, 参数槽, 编号, 个数)?;
        let 文本表 = 入参
            .iter()
            .map(|项| std::str::from_utf8(项).map_err(|_| 错误码::参数不合法))
            .collect::<Result<Vec<_>, _>>()?;
        执行业务口(编号, &文本表)
    })();
    match 结果 {
        Ok(字节) => {
            let 长度 = 字节.len() as u64;
            let 指针 = Box::into_raw(字节.into_boxed_slice()) as *const u8;
            unsafe {
                *返回槽 = 数据槽::指针(类型标签::构造(4), 指针 as u64, 长度, true)
            };
        }
        Err(码) => unsafe {
            *返回槽 = 数据槽::内联槽(类型标签::构造(u32::MAX), 码 as u64, 4)
        },
    }
}
