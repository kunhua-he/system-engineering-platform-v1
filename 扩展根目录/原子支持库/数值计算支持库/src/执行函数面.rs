//! 执行函数面 —— 九条数值命令的执行入口与它们共用的槽读写口。
//!
//! 入参从 `数据槽` 取、结果写回返回槽，失败写结构化错误码（不靠返回值）。
//! 本扩展私有的两种边界编码（复合类型形状未裁，按「内联/指针槽」最小承载）：
//!   · 结果结构（标签 103）：内联槽「槽值 = 结果值 f64 位形 · 槽字节长度 = 小数位」；
//!   · 列表型（标签 100）：指针槽「槽值 = 指向 f64 数组 · 槽字节长度 = 项数 × 8」。

use v1_contract::{执行函数, 数据槽, 类型标签};

use crate::错误码;
use crate::命令声明面::{命令表内位, 函数表项数};
use crate::能力号;

/// 写一个结构化错误码到返回槽（「错误」标签 4294967295，与底座统一注册表同口径）。
unsafe fn 写错误槽(返回槽: *mut 数据槽, 错误码值: u32) {
    if 返回槽.is_null() {
        return;
    }
    unsafe { *返回槽 = 数据槽::内联槽(类型标签::构造(4294967295), 错误码值 as u64, 4) };
}

/// 写「参数不合法」。
unsafe fn 写参数不合法(返回槽: *mut 数据槽) {
    unsafe { 写错误槽(返回槽, 错误码::参数不合法) };
}

/// 写「计算失败」。
unsafe fn 写计算失败(返回槽: *mut 数据槽) {
    unsafe { 写错误槽(返回槽, 错误码::计算失败) };
}

/// 从入参槽取双精度数（内联槽，类型标签 2）。
unsafe fn 读双精度(参数槽: *const 数据槽) -> f64 {
    f64::from_bits(unsafe { (*参数槽).槽值 })
}

/// 从入参槽取整数（内联槽，类型标签 1）。
unsafe fn 读整数(参数槽: *const 数据槽) -> i64 {
    unsafe { (*参数槽).槽值 as i64 }
}

/// 从入参槽取数值列表（指针槽，类型标签 100）。
unsafe fn 读数值列表(参数槽: *const 数据槽) -> Vec<f64> {
    let 列表项数 = (unsafe { (*参数槽).槽字节长度 } / 8) as usize;
    if 列表项数 == 0 {
        return Vec::new();
    }
    let 起址 = unsafe { (*参数槽).槽值 } as *const f64;
    let mut 数值表 = Vec::with_capacity(列表项数);
    for 元素序位 in 0..列表项数 {
        数值表.push(unsafe { *起址.add(元素序位) });
    }
    数值表
}

/// 写结果：结果结构（类型标签 103）内联承载「结果值 f64 位形 + 小数位」。
unsafe fn 写结果(返回槽: *mut 数据槽, 结果值: f64, 小数位: i64) {
    if 返回槽.is_null() {
        return;
    }
    unsafe { *返回槽 = 数据槽::内联槽(类型标签::构造(103), 结果值.to_bits(), 小数位 as u64) };
}

/// 1324 四舍五入：待处理数值（双精度）· 小数位（整数）。
pub unsafe extern "C" fn 四舍五入执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 2 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 待处理数值 = unsafe { 读双精度(参数表) };
    let 小数位 = unsafe { 读整数(参数表.add(1)) };
    let 因子 = 10f64.powi(小数位.clamp(0, 15) as i32);
    unsafe { 写结果(返回槽, (待处理数值 * 因子).round() / 因子, 小数位) };
}

/// 1325 取整：待处理数值（双精度）· 方式（文本：向下 / 向上 / 四舍五入）。
pub unsafe extern "C" fn 取整执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 2 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 待处理数值 = unsafe { 读双精度(参数表) };
    let 方式槽 = unsafe { &*参数表.add(1) };
    let 方式字节 = unsafe { core::slice::from_raw_parts(方式槽.槽值 as *const u8, 方式槽.槽字节长度 as usize) };
    let 取整值 = match core::str::from_utf8(方式字节).unwrap_or("四舍五入") {
        "向下" => 待处理数值.floor(),
        "向上" => 待处理数值.ceil(),
        _ => 待处理数值.round(),
    };
    unsafe { 写结果(返回槽, 取整值, 0) };
}

/// 1326 绝对值：待处理数值（双精度）。
pub unsafe extern "C" fn 绝对值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    unsafe { 写结果(返回槽, unsafe { 读双精度(参数表) }.abs(), 0) };
}

/// 1327 最大值：数值列表（列表型）。
pub unsafe extern "C" fn 最大值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 数值表 = unsafe { 读数值列表(参数表) };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let mut 最值 = 数值表[0];
    for 值 in &数值表[1..] {
        if *值 > 最值 {
            最值 = *值;
        }
    }
    unsafe { 写结果(返回槽, 最值, 0) };
}

/// 1328 最小值：数值列表（列表型）。
pub unsafe extern "C" fn 最小值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 数值表 = unsafe { 读数值列表(参数表) };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let mut 最值 = 数值表[0];
    for 值 in &数值表[1..] {
        if *值 < 最值 {
            最值 = *值;
        }
    }
    unsafe { 写结果(返回槽, 最值, 0) };
}

/// 1329 随机数：下限（整数）· 上限（整数）—— 闭区间内取一个。
pub unsafe extern "C" fn 随机数执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 2 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 下限 = unsafe { 读整数(参数表) };
    let 上限 = unsafe { 读整数(参数表.add(1)) };
    if 上限 < 下限 {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 种子 = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|时段| 时段.as_nanos() as u64)
        .unwrap_or(0x2545_F491_4F6C_DD1D);
    let mut 状态 = 种子 ^ 0x9E37_79B9_7F4A_7C15;
    状态 ^= 状态 << 13;
    状态 ^= 状态 >> 7;
    状态 ^= 状态 << 17;
    let 命中 = 下限 + (状态 % (上限 - 下限 + 1) as u64) as i64;
    unsafe { 写结果(返回槽, 命中 as f64, 0) };
}

/// 1330 求和：数值列表（列表型）。
pub unsafe extern "C" fn 求和执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 数值表 = unsafe { 读数值列表(参数表) };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    unsafe { 写结果(返回槽, 数值表.iter().sum::<f64>(), 0) };
}

/// 1331 平均值：数值列表（列表型）。
pub unsafe extern "C" fn 平均值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 数值表 = unsafe { 读数值列表(参数表) };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 相加和: f64 = 数值表.iter().sum();
    unsafe { 写结果(返回槽, 相加和 / 数值表.len() as f64, 0) };
}

/// 1332 分位数：数值列表（列表型）· 百分位（双精度）· 小数位（整数）。
pub unsafe extern "C" fn 分位数执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 3 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 数值表 = unsafe { 读数值列表(参数表) };
    let 百分位 = unsafe { 读双精度(参数表.add(1)) };
    let 小数位 = unsafe { 读整数(参数表.add(2)) };
    if 数值表.is_empty() || !(0.0..=1.0).contains(&百分位) {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let mut 有序 = 数值表.clone();
    有序.sort_by(f64::total_cmp);
    let 位次 = 百分位 * (有序.len() - 1) as f64;
    let 下侧位次 = 位次.floor() as usize;
    let 上侧位次 = 位次.ceil() as usize;
    let 分位数值 = 有序[下侧位次] + (有序[上侧位次] - 有序[下侧位次]) * (位次 - 下侧位次 as f64);
    let 因子 = 10f64.powi(小数位.clamp(0, 15) as i32);
    unsafe { 写结果(返回槽, (分位数值 * 因子).round() / 因子, 小数位) };
}

/// 保留项执行函数：`造函数表` 的初值，也是「命令表加了位而函数表漏覆写」时的诚实状态 ——
/// 它写的是结构化错误码，**不是假成功**。当前九位全部覆写，正常路径不会走到它。
pub(crate) unsafe extern "C" fn 保留项执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    let _ = (参数个数, 参数表);
    unsafe { 写计算失败(返回槽) };
}

/// 造函数表：与命令表**等长**、一一对应（同一下标 = 同一条命令）。
pub const fn 造函数表() -> [执行函数; 函数表项数] {
    let mut 本表 = [保留项执行 as 执行函数; 函数表项数];
    本表[命令表内位(能力号::四舍五入)] = 四舍五入执行;
    本表[命令表内位(能力号::取整)] = 取整执行;
    本表[命令表内位(能力号::绝对值)] = 绝对值执行;
    本表[命令表内位(能力号::最大值)] = 最大值执行;
    本表[命令表内位(能力号::最小值)] = 最小值执行;
    本表[命令表内位(能力号::随机数)] = 随机数执行;
    本表[命令表内位(能力号::求和)] = 求和执行;
    本表[命令表内位(能力号::平均值)] = 平均值执行;
    本表[命令表内位(能力号::分位数)] = 分位数执行;
    本表
}

/// 函数表：与命令表等长，一一对应。**不许留空指针。**
pub(crate) const 执行函数表: [执行函数; 函数表项数] = 造函数表();
