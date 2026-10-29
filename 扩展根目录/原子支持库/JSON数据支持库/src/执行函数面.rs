use crate::命令声明面::{函数表项数, 命令表内位, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};
unsafe fn 处理调用(
    编号: u32, 参数个数: u32, 参数表: *const 数据槽
) -> Result<数据槽, u32> {
    if 参数表.is_null() || 参数个数 != 造命令表()[命令表内位(编号)].参数个数 {
        return Err(错误码::JSON参数不合法);
    }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    let mut 文本参数表 = Vec::new();
    for 槽项 in 参数槽 {
        if 槽项.类型标签.取号值() != 4
            || !槽项.是否引用()
            || (槽项.槽值 == 0 && 槽项.槽字节长度 != 0)
        {
            return Err(错误码::JSON参数不合法);
        }
        if 槽项.槽字节长度 > 65536 {
            return Err(错误码::JSON资源受限);
        }
        let 文本字节 = if 槽项.槽字节长度 == 0 {
            &[][..]
        } else {
            unsafe {
                std::slice::from_raw_parts(槽项.槽值 as *const u8, 槽项.槽字节长度 as usize)
            }
        };
        文本参数表.push(std::str::from_utf8(文本字节).map_err(|_| 错误码::JSON参数不合法)?);
    }
    let (返回标签, 返回字节) = crate::业务实现::执行文本操作(编号, &文本参数表)?;
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
    let 返回结果 = unsafe { 处理调用(编号, 参数个数, 参数表) };
    unsafe {
        *返回槽 = 返回结果.unwrap_or_else(|失败码| {
            数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)
        });
    }
}
pub unsafe extern "C-unwind" fn 规范化JSON入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::规范化JSON, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 按指针取值入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::按指针取值, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 按指针取文本入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::按指针取文本, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 提取摘要入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::提取摘要, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 按字段查找入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::按字段查找, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 过滤入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::过滤, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 映射转换入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::映射转换, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 按字段排序入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::按字段排序, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 列表添加入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::列表添加, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 列表移除入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::列表移除, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 展平字典入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::展平字典, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 展平结构条目入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::展平结构条目, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 规范化条目指纹入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::规范化条目指纹, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 反序列化CSV入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::反序列化CSV, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 深合并入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::深合并, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 解析YAML入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::解析YAML, 返回槽, 参数个数, 参数表);
    }
}
pub unsafe extern "C-unwind" fn 序列化YAML入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::序列化YAML, 返回槽, 参数个数, 参数表);
    }
}
pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [规范化JSON入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::规范化JSON)] = 规范化JSON入口;
    本表[命令表内位(能力号::按指针取值)] = 按指针取值入口;
    本表[命令表内位(能力号::按指针取文本)] = 按指针取文本入口;
    本表[命令表内位(能力号::提取摘要)] = 提取摘要入口;
    本表[命令表内位(能力号::按字段查找)] = 按字段查找入口;
    本表[命令表内位(能力号::过滤)] = 过滤入口;
    本表[命令表内位(能力号::映射转换)] = 映射转换入口;
    本表[命令表内位(能力号::按字段排序)] = 按字段排序入口;
    本表[命令表内位(能力号::列表添加)] = 列表添加入口;
    本表[命令表内位(能力号::列表移除)] = 列表移除入口;
    本表[命令表内位(能力号::展平字典)] = 展平字典入口;
    本表[命令表内位(能力号::展平结构条目)] = 展平结构条目入口;
    本表[命令表内位(能力号::规范化条目指纹)] = 规范化条目指纹入口;
    本表[命令表内位(能力号::反序列化CSV)] = 反序列化CSV入口;
    本表[命令表内位(能力号::深合并)] = 深合并入口;
    本表[命令表内位(能力号::解析YAML)] = 解析YAML入口;
    本表[命令表内位(能力号::序列化YAML)] = 序列化YAML入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
