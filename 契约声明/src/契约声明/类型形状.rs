//! 类型形状 —— 数据类型与它上面的事件 · 属性 · 元素。
//!
//! 公开面经 `lib.rs` 再导出 ⇒ `v1_contract::事件信息` / `v1_contract::属性信息` /
//! `v1_contract::元素信息` / `v1_contract::数据类型信息` 逐字不变。

use crate::参数信息;

/// 事件信息（数据类型上的事件）。
#[repr(C)]
pub struct 事件信息 {
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 参数个数: u32,
    pub 参数表: *const 参数信息,
}

/// 属性信息（数据类型上的属性）。
#[repr(C)]
pub struct 属性信息 {
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 类型标签: u32,
    pub 状态位: u16,
}

/// 元素信息（枚举型数据类型的元素）。
#[repr(C)]
pub struct 元素信息 {
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 数值: i64,
}

/// 数据类型信息。
///
/// **字段顺序＝冻结区 + 旁路区**：旁路字段一律追加在尾部（旧读者仍能读前缀）。
/// 这是「新增段类型号不动旧段」在结构层的形态。
#[repr(C)]
pub struct 数据类型信息 {
    // ── 冻结区 ──
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 状态位: u32,
    pub 命令个数: u32,
    pub 命令号表: *const u32,
    pub 事件个数: u32,
    pub 事件表: *const 事件信息,
    pub 属性个数: u32,
    pub 属性表: *const 属性信息,
    pub 元素个数: u32,
    pub 元素表: *const 元素信息,
    // ── 旁路区（只增不改；一律追加）──
    /// 显式类型标签。**必须显式**：用表内下标当标签会让标签随合并顺序变化，跨版本不稳定。
    /// （参照实现正是为此才不得不用占位项保索引不塌。我们既留占位项保编号，又给类型显式标签保稳定。）
    pub 类型标签: u32,
}
