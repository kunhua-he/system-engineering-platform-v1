use v1_contract::{数据槽, 类型标签, 执行函数};

use crate::命令声明面::{命令表内位, 函数表项数};
use crate::编号与码面::{能力号, 错误码};

const 文本上限: u64 = 88_000_000;

unsafe fn 取文本<'a>(参数表: *const 数据槽, 参数个数: u32, 序号: usize) -> Result<&'a str, u32> {
    if 序号 >= 参数个数 as usize {
        return Err(错误码::参数不合法);
    }
    let 槽位 = unsafe { &*参数表.add(序号) };
    if 槽位.类型标签.取号值() != 4 || !槽位.是否引用() || 槽位.槽值 == 0 || 槽位.槽字节长度 > 文本上限 {
        return Err(错误码::参数不合法);
    }
    let 字节 = unsafe { std::slice::from_raw_parts(槽位.槽值 as *const u8, 槽位.槽字节长度 as usize) };
    std::str::from_utf8(字节).map_err(|_| 错误码::参数不合法)
}

fn 装返回(正文: String) -> Result<数据槽, u32> {
    let 字节 = 正文.into_bytes().into_boxed_slice();
    let 字节长度 = 字节.len() as u64;
    let 指针 = Box::into_raw(字节) as *const u8;
    Ok(数据槽::指针(类型标签::构造(4), 指针 as u64, 字节长度, true))
}

fn 完成(产物: Result<String, u32>) -> 数据槽 {
    产物
        .and_then(装返回)
        .unwrap_or_else(|失败码| 数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4))
}

unsafe fn 处理分析图像(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::分析图像实现(unsafe { 取文本(参数表, 参数个数, 0)? })
}

unsafe fn 处理识别格式(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::识别格式实现(unsafe { 取文本(参数表, 参数个数, 0)? })
}

unsafe fn 处理占位图(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 6 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::生成占位图实现(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
        unsafe { 取文本(参数表, 参数个数, 2)? },
        unsafe { 取文本(参数表, 参数个数, 3)? },
        unsafe { 取文本(参数表, 参数个数, 4)? },
        unsafe { 取文本(参数表, 参数个数, 5)? },
    )
}

unsafe fn 处理缩放(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 3 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::缩放实现(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
        unsafe { 取文本(参数表, 参数个数, 2)? },
    )
}

unsafe fn 处理转置(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 2 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::转置实现(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
    )
}

unsafe fn 处理合成(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 4 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::合成实现(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
        unsafe { 取文本(参数表, 参数个数, 2)? },
        unsafe { 取文本(参数表, 参数个数, 3)? },
    )
}

unsafe fn 处理重编码(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 3 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    // 质量允许空串：空表示交给编码器默认。空串槽值 0 会被判非引用，故这里单独走内联分支。
    let 质量值 = if 参数个数 > 2 {
        let 槽位 = unsafe { &*参数表.add(2) };
        if 槽位.类型标签.取号值() == 4 && 槽位.是否引用() && 槽位.槽值 != 0 {
            let 字节 = unsafe {
                std::slice::from_raw_parts(槽位.槽值 as *const u8, 槽位.槽字节长度 as usize)
            };
            std::str::from_utf8(字节).map_err(|_| 错误码::参数不合法)?
        } else {
            ""
        }
    } else {
        ""
    };
    crate::图像处理::重编码实现(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
        质量值,
    )
}

unsafe fn 处理哈希组(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::哈希组实现(unsafe { 取文本(参数表, 参数个数, 0)? })
}

unsafe fn 处理转置修正(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 1 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::转置修正实现(unsafe { 取文本(参数表, 参数个数, 0)? })
}

unsafe fn 处理透明合成(参数个数: u32, 参数表: *const 数据槽) -> Result<String, u32> {
    if 参数个数 != 2 || 参数表.is_null() {
        return Err(错误码::参数不合法);
    }
    crate::图像处理::透明背景合成实现(
        unsafe { 取文本(参数表, 参数个数, 0)? },
        unsafe { 取文本(参数表, 参数个数, 1)? },
    )
}

macro_rules! 造入口 {
    ($名称:ident, $处理:ident) => {
        pub unsafe extern "C-unwind" fn $名称(
            返回槽: *mut 数据槽,
            参数个数: u32,
            参数表: *const 数据槽,
        ) {
            if 返回槽.is_null() {
                return;
            }
            let 产物 = unsafe { $处理(参数个数, 参数表) };
            unsafe { *返回槽 = 完成(产物) };
        }
    };
}

造入口!(分析图像入口, 处理分析图像);
造入口!(识别格式入口, 处理识别格式);
造入口!(生成占位图入口, 处理占位图);
造入口!(缩放入口, 处理缩放);
造入口!(转置入口, 处理转置);
造入口!(合成入口, 处理合成);
造入口!(重编码入口, 处理重编码);
造入口!(哈希组入口, 处理哈希组);
造入口!(转置修正入口, 处理转置修正);
造入口!(透明合成入口, 处理透明合成);

pub const fn 造函数表() -> [执行函数; 函数表项数] {
    // 每一格都必须显式覆写：默认填充值是首项入口，漏写会静默跑到「分析图像文件」。
    let mut 本表 = [分析图像入口 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::分析图像文件)] = 分析图像入口;
    本表[命令表内位(能力号::识别图像格式)] = 识别格式入口;
    本表[命令表内位(能力号::生成占位图)] = 生成占位图入口;
    本表[命令表内位(能力号::缩放图像)] = 缩放入口;
    本表[命令表内位(能力号::转置图像)] = 转置入口;
    本表[命令表内位(能力号::合成图像)] = 合成入口;
    本表[命令表内位(能力号::重编码图像)] = 重编码入口;
    本表[命令表内位(能力号::计算图像哈希组)] = 哈希组入口;
    本表[命令表内位(能力号::转置修正)] = 转置修正入口;
    本表[命令表内位(能力号::透明背景合成)] = 透明合成入口;
    本表
}

pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
