//! 基础形状 —— 版本 · 静态表 · 定长槽。三样是别的一切形状的砖。
//!
//! 公开面经 `lib.rs` 的 `pub use` 再导出 ⇒ `v1_contract::版本三元组` /
//! `v1_contract::表段` / `v1_contract::数据槽` / `v1_contract::槽标志` 逐字不变。

use crate::类型标签;

/// 实现版本（三段 `i32`：主 · 次 · 构建）。
///
/// 型名逐字不变（`v1_contract::版本三元组`）—— 它本来就是「三件」：主 · 次 · 构建。
/// 2026-09-27 前这里是 `4×u16`（多一个 `修订` 段），属**无理由偏离**：参照实现 `LIB_INFO`
/// 的 `m_nMajorVersion` + `m_nMinorVersion` + `m_nBuildNumber` 是 **3×i32**
/// （`项目文档/设计文档/接缝实测.md` §七.1）。拉齐走 `契约声明/冻结登记.json` 的旁路。
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 版本三元组 {
    pub 主: i32,
    pub 次: i32,
    pub 构建: i32,
}

impl 版本三元组 {
    pub const fn 新建(主版本: i32, 次版本: i32, 构建: i32) -> Self {
        Self { 主: 主版本, 次: 次版本, 构建 }
    }

    /// 本版本是否满足「版本要求」：**先比主、再比次**（要求无修订段；构建号不参与）。
    pub const fn 满足(&self, 要求: &版本要求) -> bool {
        if self.主 != 要求.主 {
            return self.主 > 要求.主;
        }
        self.次 >= 要求.次
    }
}

/// 版本要求（两段 `i32`：主 · 次）—— **无修订段**。
///
/// 与 `版本三元组` 是**两个型**：被比较的一方（要求）只有两段，照参照实现
/// `m_nRqSysMajorVer` + `m_nRqSysMinorVer`（2×i32，`项目文档/设计文档/接缝实测.md` §七.1）。
/// 判「满足」的是 `版本三元组::满足`（提供方拿本型当门槛）。
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 版本要求 {
    pub 主: i32,
    pub 次: i32,
}

impl 版本要求 {
    pub const fn 新建(主版本: i32, 次版本: i32) -> Self {
        Self { 主: 主版本, 次: 次版本 }
    }
}

/// 一张静态表：项数 + 项表指针。空表用 `表段::空实例()`。
#[repr(C)]
#[derive(Clone, Copy)]
pub struct 表段<元素> {
    pub 项数: u32,
    pub 项表: *const 元素,
}

impl<元素> 表段<元素> {
    pub const fn 空实例() -> Self {
        Self { 项数: 0, 项表: core::ptr::null() }
    }
    pub const fn 新建(项表: *const 元素, 项数: u32) -> Self {
        Self { 项数, 项表 }
    }
    pub fn 是否空(&self) -> bool {
        self.项数 == 0
    }
}

/// 跨边界唯一定长数据槽。**类型标签在槽内**——这是多语言能兼容的唯一原因。
///
/// 64 位对齐，24 字节。每种语言只需要会两件事：把值放进槽、把槽读出来。
///
/// **★ 槽里放指针时，被指内存必须比槽活得久**（实测踩过：把一个指向函数内临时 `Vec` 的槽
/// 返回出去 ⇒ 出栈即悬垂，`ptr::copy_nonoverlapping` 的前置条件被破 ⇒ **段错误、无输出**，
/// 而症状看起来像别的问题）。正确做法：让被指内存先落到**活得比槽久**的地方（`Vec`/`Box`/
/// 静态），槽**就地**构造，不跨函数返回「指向栈上临时量」的槽。
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 数据槽 {
    /// 类型标签，取自 `契约声明/类型声明/`。位置错位或类型不符，当场可判。
    pub 类型标签: 类型标签,
    /// 标志位：所有权 · 是否引用 · 是否空。
    pub 标志: u16,
    pub 保留: u16,
    /// 字节长度。**文本与字节集必带长度**——参照内核不带长度，是它的缺陷，不复刻。
    pub 长度: u64,
    /// 内联值，或指向数据的指针（由标志位区分）。
    pub 值: u64,
}

/// 槽标志位。
pub mod 槽标志 {
    /// 值是指针（否则是内联值）。
    pub const 引用: u16 = 1 << 0;
    /// 值归接收方所有，接收方负责释放。
    pub const 所有权交出: u16 = 1 << 1;
    /// 空值（等价于"无值"，不是错误）。
    pub const 空槽标志: u16 = 1 << 2;
    /// 只读：接收方不许改。
    pub const 只读: u16 = 1 << 3;
}

impl 数据槽 {
    pub const fn 空槽() -> Self {
        Self { 类型标签: 类型标签::新建(0), 标志: 槽标志::空槽标志, 保留: 0, 长度: 0, 值: 0 }
    }
    pub const fn 内联(标签: 类型标签, 待处理值: u64, 长度: u64) -> Self {
        Self { 类型标签: 标签, 标志: 0, 保留: 0, 长度, 值: 待处理值 }
    }
    pub const fn 指针(标签: 类型标签, 地址: u64, 字节长度: u64, 交出所有权: bool) -> Self {
        let 标志 = if 交出所有权 { 槽标志::引用 | 槽标志::所有权交出 } else { 槽标志::引用 };
        Self { 类型标签: 标签, 标志, 保留: 0, 长度: 字节长度, 值: 地址 }
    }
    pub const fn 是否空(&self) -> bool {
        self.标志 & 槽标志::空槽标志 != 0
    }
    pub const fn 是否引用(&self) -> bool {
        self.标志 & 槽标志::引用 != 0
    }
    pub const fn 交出了所有权(&self) -> bool {
        self.标志 & 槽标志::所有权交出 != 0
    }
}
