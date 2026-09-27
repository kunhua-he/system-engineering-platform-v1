//! 注册表 —— 三张入参表（命令表 / 常量表 / 类型表）的**边界编码**与查询。
//!
//! # 为什么这里要定一个编码
//!
//! `能力声明/1103.json` 的参数表第 1–3 行是**字节集**（类型标签 5），说明写着
//! 「载荷＝本库的注册表边界编码（形状未冻）」。跨边界只有定长数据槽 ⇒ 三张表过边界
//! 必须先编成字节集，**不许无形状就接**（`说明/使用说明.md` 的同一条规矩）。
//!
//! 本件定的就是那条边界编码，与 `结构编码` / `原生路编码` **同一条规矩**：
//! 只搬字段、不含业务知识；三张表结构同构，故**只有这一处**编解码，不按表各写一套。
//!
//! # 载荷形状（小端）
//!
//! ```text
//! 注册表：u32 项数 · 每项 ( u32 名长 + 名字节 · u16 号 )
//! ```
//!
//! 名字是**原始字节**（不做编码假设：GBK 与 UTF-8 都装得下），比对照**原字节**
//! （`说明/语言面形状.md` §六待办 6）。空字节集 = **空表**（0 项，不是非法）——
//! 调用方没有这一类表时传空槽即可；空表下任何引用都落到 `名字未声明`（fail-closed）。
//!
//! # 与 `声明记录区实测.md` 的关系（如实划界）
//!
//! 三张表的号**不是** `.e` 声明记录区里那些 4 字节令牌的号 —— 令牌的字段语义是**不判项**
//! （该文 §七 第 1 条），本件一个字节都不替它编。这里定的只是**本库过边界用的**编码。

/// 一张「名字 → 号」的表。项数 ≤ `u32`，号 ≤ `u16`（见 `形状.rs` 的号宽口径）。
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct 注册表 {
    项: Vec<(Vec<u8>, u16)>,
}

impl 注册表 {
    pub fn 空() -> Self {
        Self { 项: Vec::new() }
    }

    /// 直接给项（库内与测试构造用；顺序即盘面顺序，**不排序、不去重**）。
    pub fn 从项(项: Vec<(Vec<u8>, u16)>) -> Self {
        Self { 项 }
    }

    pub fn 项数(&self) -> usize {
        self.项.len()
    }

    pub fn 项(&self) -> &[(Vec<u8>, u16)] {
        &self.项
    }

    /// 按名字（**原始字节**）找号。同名取**先出现的那一项**。
    pub fn 找(&self, 名: &[u8]) -> Option<u16> {
        self.项
            .iter()
            .find(|(表名, _)| 表名.as_slice() == 名)
            .map(|(_, 号)| *号)
    }

    /// 逐项编成字节集（本件是唯一的编码处）。
    pub fn 编码(&self) -> Vec<u8> {
        let mut 出 = Vec::new();
        出.extend_from_slice(&(self.项.len() as u32).to_le_bytes());
        for (名, 号) in &self.项 {
            出.extend_from_slice(&(名.len() as u32).to_le_bytes());
            出.extend_from_slice(名);
            出.extend_from_slice(&号.to_le_bytes());
        }
        出
    }

    /// 字节集 → 表。`None` = 编码非法（截断 / 尾部有多余字节 / 项数或名长越界）。
    ///
    /// **空字节集 = 空表**（见文件头）；非空字节集必须**正好**解完，不许「尽力而为」。
    pub fn 解码(字节: &[u8]) -> Option<Self> {
        if 字节.is_empty() {
            return Some(Self::空());
        }
        let mut 读 = 读器 { 字节, 位: 0 };
        let 项数 = 读.u32()? as usize;
        // 每项至少 4 字节名长 + 2 字节号 = 6 字节 ⇒ 项数不可能超过 字节.len()/6。
        // 先卡这一条，免得下面 `Vec::with_capacity` 被一个伪造的大项数撑爆内存。
        if 项数 > 字节.len() / 6 {
            return None;
        }
        let mut 项 = Vec::with_capacity(项数);
        for _ in 0..项数 {
            let 名长 = 读.u32()? as usize;
            let 名 = 读.取字节(名长)?.to_vec();
            let 号 = 读.u16()?;
            项.push((名, 号));
        }
        // 尾部有多余字节 ⇒ 非法（不许静默忽略）。
        if 读.位 != 字节.len() {
            return None;
        }
        Some(Self { 项 })
    }
}

/// 顺序读器：每个 `取字节` 都查边界，越界给 `None`（不 panic）。
struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    fn 取字节(&mut self, 数: usize) -> Option<&'a [u8]> {
        let 尾 = self.位.checked_add(数)?;
        if 尾 > self.字节.len() {
            return None;
        }
        let 片 = &self.字节[self.位..尾];
        self.位 = 尾;
        Some(片)
    }

    fn u16(&mut self) -> Option<u16> {
        Some(u16::from_le_bytes(self.取字节(2)?.try_into().ok()?))
    }

    fn u32(&mut self) -> Option<u32> {
        Some(u32::from_le_bytes(self.取字节(4)?.try_into().ok()?))
    }
}
