//! 生成 —— 记录流 → 段数据字节（必须与反解构成往返一致）。

use super::形状::{段体魔数, 段数据头长度, 体长实算, 记录流};
use super::错误::生成错误;

/// 生成：记录流 → 段数据字节。**必须与 `反解段数据` 构成往返一致**。
pub fn 生成段数据(输出流: &记录流) -> Result<Vec<u8>, 生成错误> {
    let 首数组长 = 输出流.支持库.首数组.len() as u64;
    let 次数组长 = 输出流.支持库.次数组.len() as u64;
    let 末数组长 = 输出流.支持库.末数组.len() as u64;
    let 引用表长 = 输出流.支持库.引用表.len() as u64;
    if 首数组长 != 次数组长 || 首数组长 != 末数组长 || 首数组长 != 引用表长 {
        return Err(生成错误::支持库数组长度不一致 { 首数组长, 次数组长, 末数组长, 引用表: 引用表长 });
    }
    for (序号, 引用记录) in 输出流.支持库.引用表.iter().enumerate() {
        if 引用记录.字段.is_empty() {
            return Err(生成错误::支持库引用字段为空 { 第几条: 序号 as u32 });
        }
    }
    if let Some(读游标) = 输出流.段头字段.补零.iter().position(|&字节| 字节 != 0) {
        return Err(生成错误::补零非零 { 第几字节: 读游标 as u32 });
    }

    let 体长 = 体长实算(输出流);
    let mut 输出缓冲 = Vec::with_capacity(段数据头长度 + 体长 as usize);

    输出缓冲.extend_from_slice(&输出流.段头字段.段序号.to_le_bytes());
    输出缓冲.extend_from_slice(&输出流.段头字段.保留.to_le_bytes());
    // 校验值 = 折(体)，体由内容重建（与 `体长` 同一口径）⇒ 先留 4 字节占位，函数尾回填。
    // 不读 `头.校验值` 快照（同「体长由内容重算」一条规矩）。
    输出缓冲.extend_from_slice(&[0u8; 4]);
    // 体长由内容重算后写回，不读 `头.体长`（见模块注释「一处与容器层同源的口径」）。
    输出缓冲.extend_from_slice(&(体长 as u32).to_le_bytes());
    输出缓冲.extend_from_slice(&输出流.段头字段.补零);

    输出缓冲.extend_from_slice(&输出流.体头.首字段.to_le_bytes());
    输出缓冲.extend_from_slice(&段体魔数.to_le_bytes());

    输出缓冲.extend_from_slice(&((4 * 首数组长) as u32).to_le_bytes());
    for 待处理值 in &输出流.支持库.首数组 {
        输出缓冲.extend_from_slice(&待处理值.to_le_bytes());
    }
    输出缓冲.extend_from_slice(&((2 * 首数组长) as u32).to_le_bytes());
    for 待处理值 in &输出流.支持库.次数组 {
        输出缓冲.extend_from_slice(&待处理值.to_le_bytes());
    }
    输出缓冲.extend_from_slice(&((2 * 首数组长) as u32).to_le_bytes());
    for 待处理值 in &输出流.支持库.末数组 {
        输出缓冲.extend_from_slice(&待处理值.to_le_bytes());
    }
    输出缓冲.extend_from_slice(&(首数组长 as u16).to_le_bytes());

    for 引用记录 in &输出流.支持库.引用表 {
        输出缓冲.extend_from_slice(&(引用记录.串长() as u32).to_le_bytes());
        输出缓冲.extend_from_slice(&引用记录.原文());
    }

    输出缓冲.extend_from_slice(&输出流.其余载荷);
    // 校验槽回填：折(体) = 折(段数据头之后的全部字节)。体已全部拼齐，故在函数尾一次算完。
    let 校验值 = crate::容器::校验槽::折(&输出缓冲[段数据头长度..]);
    输出缓冲[0x08..0x0C].copy_from_slice(&校验值.to_le_bytes());
    Ok(输出缓冲)
}
