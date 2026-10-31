use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合值, 复合元素, 编码复合值载荷};
use v1_contract::{数据槽, 类型标签};
unsafe fn 读命令文本(参数槽: &数据槽) -> Result<String, u32> {
    if 参数槽.类型标签.取号值() != 4 {
        return Err(错误码::参数不合法);
    }
    if 参数槽.槽字节长度 > 65536 {
        return Err(错误码::资源受限);
    }
    let 内联字节 = 参数槽.槽值.to_le_bytes();
    let 文本字节 = if 参数槽.是否引用() {
        if 参数槽.槽值 == 0 {
            return Err(错误码::参数不合法);
        }
        unsafe {
            std::slice::from_raw_parts(参数槽.槽值 as *const u8, 参数槽.槽字节长度 as usize)
        }
    } else {
        内联字节
            .get(..参数槽.槽字节长度 as usize)
            .ok_or(错误码::参数不合法)?
    };
    String::from_utf8(文本字节.to_vec()).map_err(|_| 错误码::参数不合法)
}
pub unsafe fn 处理调用(
    编号: u32,
    参数个数: u32,
    参数表: *const 数据槽,
) -> Result<数据槽, u32> {
    if 编号 != 能力号::检测危险命令 || 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    let 命令原文 = unsafe { 读命令文本(&*参数表)? };
    let (危险标记, 原因文本) = crate::命令检测::检测命令(&命令原文, 0)?;
    let 元素表 = vec![
        复合元素 {
            名称: "危险".into(),
            值: 复合值::逻辑型(危险标记),
        },
        复合元素 {
            名称: "原因".into(),
            值: 复合值::文本载荷(原因文本),
        },
    ];
    let 返回字节 = 编码复合值载荷(101, &元素表).map_err(|_| 错误码::命令安全不可用)?;
    let 返回长度 = 返回字节.len() as u64;
    let 返回指针 = Box::into_raw(返回字节.into_boxed_slice()) as *const u8;
    Ok(数据槽::指针(
        类型标签::构造(101),
        返回指针 as u64,
        返回长度,
        true,
    ))
}
