//! 接口说明段编码 —— 把 [`接口说明`](super::形状::接口说明) 六字段排成一串字节。
//!
//! 这就是 `说明/使用说明.md` 「1106 接口说明段编码（施工方案）」与
//! `能力包件.md` §六 待办 1 说的那个**「装法」**：字段形状已冻（= 接口面返回体，
//! 逐条同名同序），本件只规定它们**在段里怎么排字节**。
//!
//! # 规矩（逐条照施工方案）
//!
//! 与 `容器结构边界编码` / `原生路边界编码` / `语义编码` **同一条规矩**：
//! 只搬字段、不含业务知识；编解码只有这一处，不另起第二套。小端。
//!
//! | 字段的 JSON 类型 | 段里的字节排布 |
//! |---|---|
//! | 整数 | 按该字段宽度**小端**搬（`u32` / `u16` / `u8` 各按其宽度） |
//! | 文本 | `u32 字节长` + UTF-8 字节 |
//! | 表 | `u32 项数` + 逐项按本表递归（**参数表的行序 = 契约行序，不许重排**） |
//! | 槽（参数项的 `默认值`） | 定长数据槽 **24 字节原样** |
//! | 布尔 | `u8`：`0` / `1` |
//!
//! # 本编码未冻
//!
//! `决策记录/2026-09-27_语言主线三缺口裁决.md` §四 把它归**施工面**
//! （「形状部分当场闭，剩下的只是编码」）⇒ 本件**不自行登记** `冻结登记.json`。
//! 若收口方要把本编码冻成盘面形状，照 `原生路边界编码` 的先例补一条旁路即可。

use super::形状::{接口说明, 接口参数项, 接口错误项};

/// 六字段的**字段序**（照接口面返回体，`接口面形状.md` §三）。
///
/// 列在这里是为了让「字段表只有一源」这条可核对：本件只实现这个序，不自定一个。
/// 反向解码（[`解码`]）也读同一个常量 ⇒ 两个方向不会各写一套。
pub const 字段序: [&str; 6] = ["编号", "名称", "说明", "参数表", "返回类型", "可抛错误码"];

/// 数据槽宽度（字节）。**冻结项 `冻结项[2] 数据槽形状`**：
/// `u32 类型标签 · u16 标志 · u16 保留 · u64 长度 · u64 值` = 4+2+2+8+8 = 24。
pub const 槽宽度: usize = 24;

/// 接口说明 → 段数据字节。
pub fn 编码(说明: &接口说明) -> Vec<u8> {
    let mut 出 = Vec::new();
    出.extend_from_slice(&说明.编号.to_le_bytes());
    写文本(&mut 出, &说明.名称);
    写文本(&mut 出, &说明.说明);
    出.extend_from_slice(&(说明.参数表.len() as u32).to_le_bytes());
    for 参 in &说明.参数表 {
        写参数项(&mut 出, 参);
    }
    出.extend_from_slice(&说明.返回类型.to_le_bytes());
    出.extend_from_slice(&(说明.可抛错误码.len() as u32).to_le_bytes());
    for 错 in &说明.可抛错误码 {
        写错误项(&mut 出, 错);
    }
    出
}

/// 段数据字节 → 接口说明。`None` = 编码非法（截断 / 尾部多余字节 / 不是合法 UTF-8）。
///
/// **不许尽力而为**：非空字节集必须**正好**解完，剩余一字节即 `None`（同
/// [`注册表::解码`](crate::语义::注册表::解码) 的口径）。
pub fn 解码(字节: &[u8]) -> Option<接口说明> {
    let mut 读 = 读器 { 字节, 位: 0 };
    let 编号 = 读.u32()?;
    let 名称 = 读.文本()?;
    let 说明文本 = 读.文本()?;
    let 参数个数 = 读.u32()? as usize;
    // 每项至少 4 字节名长 + 4 类型标签 + 2 状态位 + 24 槽 = 34 字节。
    if 参数个数 > 读.剩() / 34 {
        return None;
    }
    let mut 参数表 = Vec::with_capacity(参数个数);
    for _ in 0..参数个数 {
        参数表.push(读参数项(&mut 读)?);
    }
    let 返回类型 = 读.u32()?;
    let 错误个数 = 读.u32()? as usize;
    // 每项至少 4 码 + 4 段位 + 4 名长 + 4 布尔 = 16 字节。
    if 错误个数 > 读.剩() / 16 {
        return None;
    }
    let mut 可抛错误码 = Vec::with_capacity(错误个数);
    for _ in 0..错误个数 {
        可抛错误码.push(读错误项(&mut 读)?);
    }
    if 读.位 != 字节.len() {
        return None;
    }
    Some(接口说明 { 编号, 名称, 说明: 说明文本, 参数表, 返回类型, 可抛错误码 })
}

fn 写文本(出: &mut Vec<u8>, 文: &str) {
    出.extend_from_slice(&(文.len() as u32).to_le_bytes());
    出.extend_from_slice(文.as_bytes());
}

fn 写参数项(出: &mut Vec<u8>, 参: &接口参数项) {
    写文本(出, &参.名称);
    出.extend_from_slice(&参.类型标签.to_le_bytes());
    出.extend_from_slice(&参.状态位.to_le_bytes());
    写槽(出, &参.默认值);
}

fn 写错误项(出: &mut Vec<u8>, 错: &接口错误项) {
    出.extend_from_slice(&错.码.to_le_bytes());
    出.extend_from_slice(&错.段位.to_le_bytes());
    写文本(出, &错.名称);
    出.push(bool::from(错.可重试) as u8);
    出.push(bool::from(错.可自愈) as u8);
    出.push(bool::from(错.需人工) as u8);
    出.push(bool::from(错.已登记) as u8);
}

/// 定长槽**原样** 24 字节（小端）。
///
/// 不拆成五个字段写：槽形状是**冻结项**，拆写等于在本件里复刻一份槽布局，
/// 将来槽加宽就会两处不同步。直接按冻结的那五个字段拼一遍是最少知识。
fn 写槽(出: &mut Vec<u8>, 槽: &v1_contract::数据槽) {
    出.extend_from_slice(&槽.类型标签.取().to_le_bytes());
    出.extend_from_slice(&槽.标志.to_le_bytes());
    出.extend_from_slice(&槽.保留.to_le_bytes());
    出.extend_from_slice(&槽.长度.to_le_bytes());
    出.extend_from_slice(&槽.值.to_le_bytes());
}

fn 读参数项(读: &mut 读器) -> Option<接口参数项> {
    let 名称 = 读.文本()?;
    let 类型标签 = 读.u32()?;
    let 状态位 = 读.u16()?;
    let 默认值 = 读.槽()?;
    Some(接口参数项 { 名称, 类型标签, 状态位, 默认值 })
}

fn 读错误项(读: &mut 读器) -> Option<接口错误项> {
    Some(接口错误项 {
        码: 读.u32()?,
        段位: 读.u32()?,
        名称: 读.文本()?,
        可重试: 读.布尔()?,
        可自愈: 读.布尔()?,
        需人工: 读.布尔()?,
        已登记: 读.布尔()?,
    })
}

/// 顺序读器：每个 `取` 都查边界，越界给 `None`（不 panic）。同 `注册表定义.rs` 的形状。
struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    fn 剩(&self) -> usize {
        self.字节.len().saturating_sub(self.位)
    }

    fn 取(&mut self, 数: usize) -> Option<&'a [u8]> {
        let 尾 = self.位.checked_add(数)?;
        if 尾 > self.字节.len() {
            return None;
        }
        let 片 = &self.字节[self.位..尾];
        self.位 = 尾;
        Some(片)
    }

    fn u16(&mut self) -> Option<u16> {
        Some(u16::from_le_bytes(self.取(2)?.try_into().ok()?))
    }

    fn u32(&mut self) -> Option<u32> {
        Some(u32::from_le_bytes(self.取(4)?.try_into().ok()?))
    }

    fn u64(&mut self) -> Option<u64> {
        Some(u64::from_le_bytes(self.取(8)?.try_into().ok()?))
    }

    fn 文本(&mut self) -> Option<String> {
        let 长 = self.u32()? as usize;
        let 片 = self.取(长)?;
        Some(core::str::from_utf8(片).ok()?.to_owned())
    }

    fn 布尔(&mut self) -> Option<bool> {
        Some(match self.取(1)?[0] {
            0 => false,
            1 => true,
            _ => return None,
        })
    }

    fn 槽(&mut self) -> Option<v1_contract::数据槽> {
        let 类型标签 = self.u32()?;
        let 标志 = self.u16()?;
        let 保留 = self.u16()?;
        let 长度 = self.u64()?;
        let 值 = self.u64()?;
        Some(v1_contract::数据槽 {
            类型标签: v1_contract::类型标签::新(类型标签),
            标志,
            保留,
            长度,
            值,
        })
    }
}
