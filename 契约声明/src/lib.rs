//! 契约声明 —— 底座与扩展共用的全部契约类型。
//!
//! 本 crate 是整个平台的脊梁：所有跨边界形状都在这里定义一次，别处只许引用，不许复制。
//!
//! 三条硬约束（改这里之前先读）：
//! 1. **只做 64 位**：字宽一律 64 位，不写 32 位分支（`内核落点.md`）。
//! 2. **布局显式**：跨边界结构必须 `#[repr(C)]`，宽度必须写死。
//! 3. **签名冻结**：这里的一切都是冻结项，改动必须走 `契约声明/冻结登记.json`。
//!
//! 命名：内部标识符一律中文；**导出的 ABI 符号一律 ASCII**（外部协议边界）。

#![allow(uncommon_codepoints)]
#![allow(non_snake_case)]
#![no_std]

/// 声明格式号：这是**格式的身份证，不是版本号**。格式不变，它永远不变。
pub const 声明格式号: u32 = 20_000_101;

/// 版本三元组（含构建号）。
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 版本三元组 {
    pub 主: u16,
    pub 次: u16,
    pub 修订: u16,
    pub 构建: u16,
}

impl 版本三元组 {
    pub const fn 新(主: u16, 次: u16, 修订: u16, 构建: u16) -> Self {
        Self { 主, 次, 修订, 构建 }
    }

    /// 本版本是否满足「要求版本」：主次修订逐位比较，构建号不参与。
    pub const fn 满足(&self, 要求: &版本三元组) -> bool {
        if self.主 != 要求.主 {
            return self.主 > 要求.主;
        }
        if self.次 != 要求.次 {
            return self.次 > 要求.次;
        }
        self.修订 >= 要求.修订
    }
}

/// 一张静态表：项数 + 项表指针。空表用 `表段::空()`。
#[repr(C)]
#[derive(Clone, Copy)]
pub struct 表段<T> {
    pub 项数: u32,
    pub 项表: *const T,
}

impl<T> 表段<T> {
    pub const fn 空() -> Self {
        Self { 项数: 0, 项表: core::ptr::null() }
    }
    pub const fn 新(项表: *const T, 项数: u32) -> Self {
        Self { 项数, 项表 }
    }
    pub fn 是否空(&self) -> bool {
        self.项数 == 0
    }
}

/// 跨边界唯一定长数据槽。**类型标签在槽内**——这是多语言能兼容的唯一原因。
///
/// 64 位对齐，24 字节。每种语言只需要会两件事：把值放进槽、把槽读出来。
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 数据槽 {
    /// 类型标签，取自 `契约声明/类型声明/`。位置错位或类型不符，当场可判。
    pub 类型标签: u32,
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
    pub const 空: u16 = 1 << 2;
    /// 只读：接收方不许改。
    pub const 只读: u16 = 1 << 3;
}

impl 数据槽 {
    pub const fn 空槽() -> Self {
        Self { 类型标签: 0, 标志: 槽标志::空, 保留: 0, 长度: 0, 值: 0 }
    }
    pub const fn 内联(类型标签: u32, 值: u64, 长度: u64) -> Self {
        Self { 类型标签, 标志: 0, 保留: 0, 长度, 值 }
    }
    pub const fn 指针(类型标签: u32, 地址: u64, 字节长度: u64, 交出所有权: bool) -> Self {
        let 标志 = if 交出所有权 { 槽标志::引用 | 槽标志::所有权交出 } else { 槽标志::引用 };
        Self { 类型标签, 标志, 保留: 0, 长度: 字节长度, 值: 地址 }
    }
    pub const fn 是否空(&self) -> bool {
        self.标志 & 槽标志::空 != 0
    }
    pub const fn 是否引用(&self) -> bool {
        self.标志 & 槽标志::引用 != 0
    }
    pub const fn 交出了所有权(&self) -> bool {
        self.标志 & 槽标志::所有权交出 != 0
    }
}

/// 命令状态位。
pub mod 命令状态 {
    /// 隐含：不出现在帮助与自动补全里。
    pub const 隐含: u16 = 1 << 2;
    /// 错误项：占位或已废止。
    pub const 错误: u16 = 1 << 3;
    /// 发布版禁用。
    pub const 发布禁用: u16 = 1 << 4;
    /// 对象拷贝命令。
    pub const 对象拷贝: u16 = 1 << 7;
    /// 对象释放命令。
    pub const 对象释放: u16 = 1 << 8;
    /// 对象构造命令。
    pub const 对象构造: u16 = 1 << 9;
}

/// 参数信息。**参数行序即契约**：一旦公布，不许重排、不许插入。
#[repr(C)]
pub struct 参数信息 {
    pub 名称: *const u8,
    pub 说明: *const u8,
    /// 类型标签，必须能在 `契约声明/类型声明/` 里查到。
    pub 类型标签: u32,
    pub 状态位: u16,
    pub 默认值: 数据槽,
}

/// 命令信息。
#[repr(C)]
pub struct 命令信息 {
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 类别: u16,
    pub 状态位: u16,
    /// 返回类型标签；0 表示无返回值。
    pub 返回类型: u32,
    pub 用户级别: u16,
    pub 参数个数: u32,
    pub 参数表: *const 参数信息,
}

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
#[repr(C)]
pub struct 数据类型信息 {
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
}

/// 常量排布。
pub mod 常量排布 {
    pub const 空: u16 = 0;
    pub const 数值: u16 = 1;
    pub const 逻辑: u16 = 2;
    pub const 文本: u16 = 3;
}

/// 常量信息。
#[repr(C)]
pub struct 常量信息 {
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 排布: u16,
    pub 类型标签: u32,
    pub 文本: *const u8,
    /// 数值常量一律双精度；逻辑常量用 0/1。
    pub 数值: f64,
}

/// 执行函数：**调用形状 1:1 复刻**——三参数，返回槽与参数槽分离，返回 void。
///
/// 失败靠错误段位，不靠返回值。
pub type 执行函数 =
    unsafe extern "C" fn(返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽);

/// 通知函数：宿主与扩展之间的双向通道。
///
/// 返回值：`0` 成功；`-1` 失败；`2015` 请求延迟释放（生命周期号段）。
pub type 通知函数 = unsafe extern "C" fn(通知号: u32, 参数一: usize, 参数二: usize) -> isize;

/// 通知返回值。
pub mod 通知返回 {
    pub const 成功: isize = 0;
    pub const 失败: isize = -1;
    /// 延迟释放：本扩展还需要被延迟释放（有引用或挂了钩子）。
    pub const 延迟释放: isize = 2015;
}

/// 通知号段。
pub mod 通知号段 {
    /// 下行：宿主 → 扩展。
    pub const 下行起: u32 = 1;
    pub const 下行止: u32 = 999;
    /// 上行：扩展 → 宿主取系统值。
    pub const 上行起: u32 = 1000;
    pub const 上行止: u32 = 1999;
    /// 生命周期：装载 · 卸载 · 退出 · 延迟释放。
    pub const 生命周期起: u32 = 2000;
    pub const 生命周期止: u32 = 2999;
}

/// 契约主结构。宿主读一次即掌握全部可装载性（宪法第 2 条）。
#[repr(C)]
pub struct 平台信息 {
    /// 格式的身份证，不是版本号。
    pub 声明格式号: u32,
    /// 本构建的目标字宽（32 或 64）。**唯一随目标变宽的是表指针**，宿主据此决定按几字节读。
    pub 目标字宽: u16,
    pub 保留: u16,
    /// 32 位十六进制标识串 + NUL。
    pub 标识串: *const u8,
    pub 实现版本: 版本三元组,
    /// 我需要什么宿主；不满足即拒绝载入。
    pub 要求宿主版本: 版本三元组,
    /// 我需要什么内核；不满足即拒绝载入。
    pub 要求内核版本: 版本三元组,
    pub 名称: *const u8,
    pub 说明: *const u8,
    pub 状态位: u32,
    pub 类型表: 表段<数据类型信息>,
    pub 命令表: 表段<命令信息>,
    /// 与命令表一一对应的执行函数表。缺项用占位函数，**不许留空指针**。
    pub 函数表: *const 执行函数,
    pub 常量表: 表段<常量信息>,
    pub 通知函数: Option<通知函数>,
    pub 依赖清单: 表段<*const u8>,
}
