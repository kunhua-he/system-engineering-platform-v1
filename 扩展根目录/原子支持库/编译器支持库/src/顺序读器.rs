//! 顺序读器 —— 按位次逐字节读一份字节集：**每个取字节都查边界，越界给 `None`（不 panic）**。
//!
//! # 为什么单列一件
//!
//! `能力包件/接口段编码.rs`（接口说明段）· `语义/注册表定义.rs`（名号表）· `边界编码/结构编码.rs`
//! （容器结构）都要解一段字节集，三处曾**各写一份同形状的读器**（结构 + `取字节` 等逐字相同）——
//! 那是第二套实现。按「同一职责只许一个落点」，读器收在本件（三处方法的**并集**），三处都改用它。
//!
//! # 容错约定（改行为 = 破契约）
//!
//! 所有 `读*` 一律返回 `Option`：截断 / 越界 / 不是合法 UTF-8 ⇒ `None`，**绝不 panic**。
//! 调用方的口径是「非空字节集必须**正好**解完，剩余一字节即 `None`」—— 故 `位` 对调用方可见，
//! 用来核对「读完没」。`取剩余长度` 供调用方先卡「项数不可能超过 剩余长度 / 每项最小字节数」，
//! 免得 `Vec::with_capacity` 被一个伪造的大项数撑爆内存。
//!
//! 本件只做字节搬运，不含任何段格式知识（段里怎么排字节在各自那件里）。

/// 顺序读器：每个 `取字节` 都查边界，越界给 `None`（不 panic）。
pub(crate) struct 顺序读器<'a> {
    pub(crate) 字节: &'a [u8],
    pub(crate) 位: usize,
}

impl<'a> 顺序读器<'a> {
    /// 还没读的字节数。
    pub(crate) fn 取剩余长度(&self) -> usize {
        self.字节.len().saturating_sub(self.位)
    }

    pub(crate) fn 取字节(&mut self, 个数: usize) -> Option<&'a [u8]> {
        let 尾部 = self.位.checked_add(个数)?;
        if 尾部 > self.字节.len() {
            return None;
        }
        let 片段 = &self.字节[self.位..尾部];
        self.位 = 尾部;
        Some(片段)
    }

    /// 一字节（`结构编码` 的段类型用）。
    pub(crate) fn 读单字节(&mut self) -> Option<u8> {
        self.取字节(1).map(|片段| 片段[0])
    }

    pub(crate) fn 读双字节(&mut self) -> Option<u16> {
        Some(u16::from_le_bytes(self.取字节(2)?.try_into().ok()?))
    }

    pub(crate) fn 读四字节(&mut self) -> Option<u32> {
        Some(u32::from_le_bytes(self.取字节(4)?.try_into().ok()?))
    }

    pub(crate) fn 读八字节(&mut self) -> Option<u64> {
        Some(u64::from_le_bytes(self.取字节(8)?.try_into().ok()?))
    }

    pub(crate) fn 文本(&mut self) -> Option<String> {
        let 长度 = self.读四字节()? as usize;
        let 片段 = self.取字节(长度)?;
        Some(core::str::from_utf8(片段).ok()?.to_owned())
    }

    pub(crate) fn 逻辑型值(&mut self) -> Option<bool> {
        Some(match self.取字节(1)?[0] {
            0 => false,
            1 => true,
            _ => return None,
        })
    }

    pub(crate) fn 读数据槽(&mut self) -> Option<v1_contract::数据槽> {
        let 类型标签 = self.读四字节()?;
        let 标志 = self.读双字节()?;
        let 保留 = self.读双字节()?;
        let 长度 = self.读八字节()?;
        let 待处理值 = self.读八字节()?;
        Some(v1_contract::数据槽 {
            类型标签: v1_contract::类型标签::新建(类型标签),
            标志,
            保留,
            长度,
            值: 待处理值,
        })
    }
}
