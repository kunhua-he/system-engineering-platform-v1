//! 执行函数面 —— 九条数值命令的执行入口与它们共用的槽读写口。
//!
//! 入参从 `数据槽` 取、结果写回返回槽，失败写结构化错误码（不靠返回值）。
//! 复合类型按 §九 的**自描述 TLV 载荷形状**承载（`项目文档/决策记录/2026-10-12_复合类型槽载荷裁决.md`）：
//!   · 出参 `103 结果结构`：**指针槽**，载荷 = 元素表（字段名 + 值）；
//!   · 入参 `100 列表`：**指针槽**，载荷 = 元素表（名称空串 + 值）。
//! 形状与编解码只在契约层一份（`v1_contract::复合值载荷`），本件只调用，不另写第二套。

use v1_contract::复合值载荷::{复合元素, 复合值, 编码复合值载荷, 解码复合值载荷};
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

/// 从入参槽取数值列表（指针槽，类型标签 100，载荷 = §九 自描述 TLV）。
///
/// `None` = 槽形状或载荷解不出来（**不是空列表**）—— 由调用方落 `参数不合法`，不静默当空表。
unsafe fn 读数值列表(参数槽: *const 数据槽) -> Option<Vec<f64>> {
    if unsafe { (*参数槽).类型标签.取号值() } != 100 {
        return None;
    }
    if unsafe { (*参数槽).是否空() } {
        return Some(Vec::new());
    }
    if !unsafe { (*参数槽).是否引用() } || unsafe { (*参数槽).槽值 } == 0 {
        return None;
    }
    // SAFETY: 契约保证「引用」槽的 值..值+长度 可读。
    let 载荷字节 = unsafe {
        core::slice::from_raw_parts((*参数槽).槽值 as *const u8, (*参数槽).槽字节长度 as usize)
    };
    let 元素表 = 解码复合值载荷(载荷字节, 100).ok()?;
    let mut 数值表 = Vec::with_capacity(元素表.len());
    for 元素项 in 元素表 {
        match 元素项.值 {
            复合值::双精度(值) => 数值表.push(值),
            复合值::整数值(值) => 数值表.push(值 as f64),
            // 列表元素只认数值两种标签；别的标签说明这块载荷不是数值列表。
            _ => return None,
        }
    }
    Some(数值表)
}

/// 写结果结构（类型标签 103）：字段表 → §九 自描述 TLV 载荷 → **指针槽**（所有权交出）。
///
/// 字段名与类型取自本扩展 `类型声明/103.json` 的 `元素表`（该表记本扩展各能力的返回字段）。
/// 编不出来（字段名空 / 重名）是**本扩展自身的构造错误** ⇒ 如实写结构化错误码，不假成功。
unsafe fn 写结果结构(返回槽: *mut 数据槽, 字段表: Vec<(&'static str, 复合值)>) {
    if 返回槽.is_null() {
        return;
    }
    let 元素表: Vec<复合元素> = 字段表
        .into_iter()
        .map(|(字段名, 值)| 复合元素 { 名称: String::from(字段名), 值 })
        .collect();
    match 编码复合值载荷(103, &元素表) {
        Ok(载荷字节) => {
            let 槽字节长度 = 载荷字节.len() as u64;
            let 数据指针 = Box::into_raw(载荷字节.into_boxed_slice()) as *const u8;
            // SAFETY: 由调用方保证 返回槽 可写；载荷字节的所有权随槽交出。
            unsafe { *返回槽 = 数据槽::指针(类型标签::构造(103), 数据指针 as u64, 槽字节长度, true) };
        }
        Err(_) => unsafe { 写计算失败(返回槽) },
    }
}

/// 一个结果字段：`(字段名, 双精度值)`。
fn 双精度字段(字段名: &'static str, 值: f64) -> (&'static str, 复合值) {
    (字段名, 复合值::双精度(值))
}

/// 一个结果字段：`(字段名, 整数值)`。
fn 整数字段(字段名: &'static str, 值: i64) -> (&'static str, 复合值) {
    (字段名, 复合值::整数值(值))
}

/// 一个结果字段：`(字段名, 文本值)`。
fn 文本字段(字段名: &'static str, 值: &str) -> (&'static str, 复合值) {
    (字段名, 复合值::文本载荷(String::from(值)))
}

/// 1324 四舍五入：待处理数值（双精度）· 小数位（整数）。
pub unsafe extern "C-unwind" fn 四舍五入执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 2 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 待处理数值 = unsafe { 读双精度(参数表) };
    let 小数位 = unsafe { 读整数(参数表.add(1)) };
    let 因子 = 10f64.powi(小数位.clamp(0, 15) as i32);
    unsafe {
        写结果结构(
            返回槽,
            vec![
                双精度字段("结果", (待处理数值 * 因子).round() / 因子),
                整数字段("小数位", 小数位),
            ],
        )
    };
}

/// 1325 取整：待处理数值（双精度）· 方式（文本：向下 / 向上 / 四舍五入）。
pub unsafe extern "C-unwind" fn 取整执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 2 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 待处理数值 = unsafe { 读双精度(参数表) };
    let 方式槽 = unsafe { &*参数表.add(1) };
    let 方式字节 = unsafe { core::slice::from_raw_parts(方式槽.槽值 as *const u8, 方式槽.槽字节长度 as usize) };
    let 方式文本 = core::str::from_utf8(方式字节).unwrap_or("四舍五入");
    let 取整值 = match 方式文本 {
        "向下" => 待处理数值.floor(),
        "向上" => 待处理数值.ceil(),
        _ => 待处理数值.round(),
    };
    unsafe {
        写结果结构(
            返回槽,
            vec![
                整数字段("结果", 取整值 as i64),
                文本字段("方式", 方式文本),
            ],
        )
    };
}

/// 1326 绝对值：待处理数值（双精度）。
pub unsafe extern "C-unwind" fn 绝对值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    unsafe { 写结果结构(返回槽, vec![双精度字段("结果", unsafe { 读双精度(参数表) }.abs())]) };
}

/// 1327 最大值：数值列表（列表型）。
pub unsafe extern "C-unwind" fn 最大值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let Some(数值表) = (unsafe { 读数值列表(参数表) }) else {
        unsafe { 写参数不合法(返回槽) };
        return;
    };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let mut 最值 = 数值表[0];
    let mut 命中位次 = 0usize;
    for (位次, 值) in 数值表.iter().enumerate().skip(1) {
        if *值 > 最值 {
            最值 = *值;
            命中位次 = 位次;
        }
    }
    unsafe {
        写结果结构(
            返回槽,
            vec![
                双精度字段("结果", 最值),
                整数字段("索引", 命中位次 as i64),
            ],
        )
    };
}

/// 1328 最小值：数值列表（列表型）。
pub unsafe extern "C-unwind" fn 最小值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let Some(数值表) = (unsafe { 读数值列表(参数表) }) else {
        unsafe { 写参数不合法(返回槽) };
        return;
    };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let mut 最值 = 数值表[0];
    let mut 命中位次 = 0usize;
    for (位次, 值) in 数值表.iter().enumerate().skip(1) {
        if *值 < 最值 {
            最值 = *值;
            命中位次 = 位次;
        }
    }
    unsafe {
        写结果结构(
            返回槽,
            vec![
                双精度字段("结果", 最值),
                整数字段("索引", 命中位次 as i64),
            ],
        )
    };
}

/// 1329 随机数：下限（整数）· 上限（整数）—— 闭区间内取一个。
pub unsafe extern "C-unwind" fn 随机数执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
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
    unsafe { 写结果结构(返回槽, vec![整数字段("结果", 命中)]) };
}

/// 1330 求和：数值列表（列表型）。
pub unsafe extern "C-unwind" fn 求和执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let Some(数值表) = (unsafe { 读数值列表(参数表) }) else {
        unsafe { 写参数不合法(返回槽) };
        return;
    };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    unsafe { 写结果结构(返回槽, vec![双精度字段("结果", 数值表.iter().sum::<f64>())]) };
}

/// 1331 平均值：数值列表（列表型）。
pub unsafe extern "C-unwind" fn 平均值执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 1 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let Some(数值表) = (unsafe { 读数值列表(参数表) }) else {
        unsafe { 写参数不合法(返回槽) };
        return;
    };
    if 数值表.is_empty() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let 相加和: f64 = 数值表.iter().sum();
    unsafe { 写结果结构(返回槽, vec![双精度字段("结果", 相加和 / 数值表.len() as f64)]) };
}

/// 1332 分位数：数值列表（列表型）· 百分位（双精度）· 小数位（整数）。
pub unsafe extern "C-unwind" fn 分位数执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
    if 参数个数 != 3 || 参数表.is_null() {
        unsafe { 写参数不合法(返回槽) };
        return;
    }
    let Some(数值表) = (unsafe { 读数值列表(参数表) }) else {
        unsafe { 写参数不合法(返回槽) };
        return;
    };
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
    let 按位取整 = |值: f64| (值 * 因子).round() / 因子;
    let 中位数 = if 有序.len() % 2 == 1 {
        有序[有序.len() / 2]
    } else {
        (有序[有序.len() / 2 - 1] + 有序[有序.len() / 2]) / 2.0
    };
    unsafe {
        写结果结构(
            返回槽,
            vec![
                双精度字段("分位数值", 按位取整(分位数值)),
                整数字段("样本数", 有序.len() as i64),
                双精度字段("百分位", 百分位),
                双精度字段("最小值", 按位取整(有序[0])),
                双精度字段("中位数", 中位数),
                双精度字段("最大值", 按位取整(有序[有序.len() - 1])),
            ],
        )
    };
}

/// 保留项执行函数：`造函数表` 的初值，也是「命令表加了位而函数表漏覆写」时的诚实状态 ——
/// 它写的是结构化错误码，**不是假成功**。当前九位全部覆写，正常路径不会走到它。
pub(crate) unsafe extern "C-unwind" fn 保留项执行(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽) {
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
