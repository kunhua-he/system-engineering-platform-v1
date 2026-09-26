//! 语言面 —— 词法 · 语法 · 语义。**本模块形状未冻结，先占位。**
//!
//! 冻结它之前不派活：记号与语法树是所有下游模块共用的脊梁，改了全体返工
//! （见 `项目文档/设计文档/内核落点.md` 第六节「接口先冻结，再派活」）。

/// 记号（形状待冻结）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 记号 {
    pub 种类: u16,
    pub 起: u32,
    pub 止: u32,
}

/// 语法树节点（形状待冻结）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 节点 {
    pub 种类: u16,
    pub 子: Vec<节点>,
}
