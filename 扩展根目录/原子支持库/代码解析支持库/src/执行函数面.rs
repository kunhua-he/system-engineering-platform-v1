use crate::命令声明面::{函数表项数, 命令表内位, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};

const 文本上限字节: usize = 1048576;

unsafe fn 读文本槽(槽项: &数据槽) -> Result<String, u32> {
    if 槽项.类型标签.取号值() != 4 {
        return Err(错误码::解析参数不合法);
    }
    let 字节长度 = 槽项.槽字节长度 as usize;
    if 字节长度 > 文本上限字节 {
        return Err(错误码::解析资源受限);
    }
    if 字节长度 == 0 {
        return Ok(String::new());
    }
    if !槽项.是否引用() {
        let 内联字节 = 槽项.槽值.to_le_bytes();
        if 字节长度 > 内联字节.len() {
            return Err(错误码::解析参数不合法);
        }
        return std::str::from_utf8(&内联字节[..字节长度])
            .map(str::to_owned)
            .map_err(|_| 错误码::解析内容不合法);
    }
    if 槽项.槽值 == 0 {
        return Err(错误码::解析参数不合法);
    }
    let 文本字节 = unsafe { std::slice::from_raw_parts(槽项.槽值 as *const u8, 字节长度) };
    std::str::from_utf8(文本字节)
        .map(str::to_owned)
        .map_err(|_| 错误码::解析内容不合法)
}

unsafe fn 读字节槽(槽项: &数据槽) -> Result<Vec<u8>, u32> {
    let 标签号 = 槽项.类型标签.取号值();
    if 标签号 != 5 && 标签号 != 4 {
        return Err(错误码::解析参数不合法);
    }
    let 字节长度 = 槽项.槽字节长度 as usize;
    if 字节长度 > 文本上限字节 {
        return Err(错误码::解析资源受限);
    }
    if 字节长度 == 0 {
        return Ok(Vec::new());
    }
    if !槽项.是否引用() {
        let 内联字节 = 槽项.槽值.to_le_bytes();
        if 字节长度 > 内联字节.len() {
            return Err(错误码::解析参数不合法);
        }
        return Ok(内联字节[..字节长度].to_vec());
    }
    if 槽项.槽值 == 0 {
        return Err(错误码::解析参数不合法);
    }
    let 字节 = unsafe { std::slice::from_raw_parts(槽项.槽值 as *const u8, 字节长度) };
    Ok(字节.to_vec())
}

unsafe fn 读整数槽(槽项: &数据槽, 默认值: u64) -> Result<u64, u32> {
    let 标签号 = 槽项.类型标签.取号值();
    if 标签号 == 0 {
        return Ok(默认值);
    }
    if 标签号 != 1 {
        return Err(错误码::解析参数不合法);
    }
    Ok(槽项.槽值)
}

fn 回文本(文本值: String) -> Result<数据槽, u32> {
    let 返回字节 = 文本值.into_bytes();
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(
        类型标签::构造(4),
        返回指针 as u64,
        返回长度,
        true,
    ))
}

unsafe fn 处理调用(
    编号: u32,
    参数个数: u32,
    参数表: *const 数据槽,
) -> Result<数据槽, u32> {
    if 参数表.is_null() || 参数个数 != 造命令表()[命令表内位(编号)].参数个数 {
        return Err(错误码::解析参数不合法);
    }
    let 参数槽 = unsafe { std::slice::from_raw_parts(参数表, 参数个数 as usize) };
    match 编号 {
        能力号::解码文本 => {
            let 原始字节 = unsafe { 读字节槽(&参数槽[0])? };
            let 编码名 = unsafe { 读文本槽(&参数槽[1])? };
            let 解码结果值 = crate::文本解码::解码或失败(&原始字节, &编码名)?;
            let 载荷 = serde_json::json!({"文本": 解码结果值.文本值, "编码": 解码结果值.编码名});
            回文本(serde_json::to_string(&载荷).map_err(|_| 错误码::解析内容不合法)?)
        }
        能力号::载入切块规则 => {
            let 路径文本 = unsafe { 读文本槽(&参数槽[0])? };
            let 强制重载 = unsafe { 读整数槽(&参数槽[1], 0)? } != 0;
            回文本(crate::规则载入::执行载入切块规则(&路径文本, 强制重载)?)
        }
        能力号::重载切块规则 => {
            let 路径文本 = unsafe { 读文本槽(&参数槽[0])? };
            回文本(crate::规则载入::执行重载切块规则(&路径文本)?)
        }
        能力号::按规则切块 => {
            let 源码全文 = unsafe { 读文本槽(&参数槽[0])? };
            let 文件格式 = unsafe { 读文本槽(&参数槽[1])? };
            let 规则文本 = unsafe { 读文本槽(&参数槽[2])? };
            let 规则对象 = crate::规则载入::校验规则文本(&规则文本)?;
            let 切块结果值 = crate::规则切块::执行按规则切块(&源码全文, &规则对象)?;
            let mut 载荷 = crate::规则切块::组装块表载荷(&切块结果值);
            载荷["格式化"] = serde_json::Value::String(crate::业务实现::规范化扩展名(&文件格式));
            回文本(serde_json::to_string(&载荷).map_err(|_| 错误码::解析内容不合法)?)
        }
        能力号::解析代码字节 => {
            let 原始字节 = unsafe { 读字节槽(&参数槽[0])? };
            let 文件格式 = unsafe { 读文本槽(&参数槽[1])? };
            let 编码名 = unsafe { 读文本槽(&参数槽[2])? };
            回文本(crate::业务实现::执行解析代码字节(&原始字节, &文件格式, &编码名)?)
        }
        能力号::解析代码文件 => {
            let 文件路径 = unsafe { 读文本槽(&参数槽[0])? };
            let 扩展名 = unsafe { 读文本槽(&参数槽[1])? };
            let 编码名 = unsafe { 读文本槽(&参数槽[2])? };
            回文本(crate::业务实现::执行解析代码文件(&文件路径, &扩展名, &编码名)?)
        }
        _ => Err(错误码::解析参数不合法),
    }
}

unsafe fn 写调用(
    编号: u32,
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
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

pub unsafe extern "C-unwind" fn 解码文本入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::解码文本, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 载入切块规则入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::载入切块规则, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 重载切块规则入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::重载切块规则, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 按规则切块入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::按规则切块, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 解析代码字节入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::解析代码字节, 返回槽, 参数个数, 参数表);
    }
}

pub unsafe extern "C-unwind" fn 解析代码文件入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    unsafe {
        写调用(能力号::解析代码文件, 返回槽, 参数个数, 参数表);
    }
}

pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [解码文本入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::解码文本)] = 解码文本入口;
    本表[命令表内位(能力号::载入切块规则)] = 载入切块规则入口;
    本表[命令表内位(能力号::重载切块规则)] = 重载切块规则入口;
    本表[命令表内位(能力号::按规则切块)] = 按规则切块入口;
    本表[命令表内位(能力号::解析代码字节)] = 解析代码字节入口;
    本表[命令表内位(能力号::解析代码文件)] = 解析代码文件入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
