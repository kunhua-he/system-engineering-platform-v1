//! 容器结构的边界编码。
//!
//! 跨边界只有定长数据槽，所以 `容器.rs` 的 `容器` 结构要过边界必须先编成字节集。
//! 本件**只做字段搬运**，不含任何 `.e` 格式知识（段头偏移 · 名称区异或全在 `容器.rs`）——
//! 它不是「第二套反解/生成」，是那个结构的一份编码。段内容那一层是 `记录流.rs`，不是这里。
//!
//! 编码（一律小端）：
//!   u32 段数
//!   每段：u32 校验和 · u8 段类型 · 27 字节名称区 · u32 段名长 + 段名字节 · u64 数据长 + 数据字节
//!
//! 名称区与段名都带上：名称区是反解侧对盘面的快照，段名是它的明文，两个都带才与
//! `容器.rs` 的结构逐字段等价（`生成` 只读段名重算名称区，但等价性判据要全字段）。
//!
//! 从 `src/lib.rs` 搬来（那是路由：声明子模块 · 再导出公开面 · 零实现）；函数体一字不改。

use crate::容器::{容器段, 段头, 容器};

/// 结构 → 字节集。
pub fn 编码容器(容器: &容器) -> Vec<u8> {
    let mut 出 = Vec::new();
    出.extend_from_slice(&(容器.段表.len() as u32).to_le_bytes());
    for 一段 in &容器.段表 {
        出.extend_from_slice(&一段.头.校验和.to_le_bytes());
        出.push(一段.头.段类型);
        出.extend_from_slice(&一段.头.名称区);
        出.extend_from_slice(&(一段.头.段名.len() as u32).to_le_bytes());
        出.extend_from_slice(&一段.头.段名);
        出.extend_from_slice(&(一段.数据.len() as u64).to_le_bytes());
        出.extend_from_slice(&一段.数据);
    }
    出
}

/// 字节集 → 结构。`None` = 编码非法（长度字段与实到字节数不符，或尾部有多余字节）。
pub fn 解码容器(字节: &[u8]) -> Option<容器> {
    let mut 读 = 读器 { 字节, 位: 0 };
    let 段数 = 读.读四字节()?;
    let mut 段表 = Vec::new();
    for _ in 0..段数 {
        let 校验和 = 读.读四字节()?;
        let 段类型 = 读.读单字节()?;
        let mut 名称区 = [0u8; 27];
        名称区.copy_from_slice(读.取字节(27)?);
        let 名长 = 读.读四字节()? as usize;
        let 段名 = 读.取字节(名长)?.to_vec();
        let 数长 = 读.读八字节()? as usize;
        let 数据 = 读.取字节(数长)?.to_vec();
        段表.push(容器段 {
            头: 段头 { 校验和, 段类型, 名称区, 段名 },
            数据,
        });
    }
    // 尾部有多余字节 ⇒ 非法（不许"尽力而为"地忽略）。
    if 读.位 != 字节.len() {
        return None;
    }
    Some(容器 { 段表 })
}

/// 顺序读器：每个 `取字节` 都查边界，越界给 `None`。
struct 读器<'a> {
    字节: &'a [u8],
    位: usize,
}

impl<'a> 读器<'a> {
    fn 取字节(&mut self, 个数: usize) -> Option<&'a [u8]> {
        let 尾 = self.位.checked_add(个数)?;
        if 尾 > self.字节.len() {
            return None;
        }
        let 片 = &self.字节[self.位..尾];
        self.位 = 尾;
        Some(片)
    }

    fn 读单字节(&mut self) -> Option<u8> {
        self.取字节(1).map(|片| 片[0])
    }

    fn 读四字节(&mut self) -> Option<u32> {
        Some(u32::from_le_bytes(self.取字节(4)?.try_into().ok()?))
    }

    fn 读八字节(&mut self) -> Option<u64> {
        Some(u64::from_le_bytes(self.取字节(8)?.try_into().ok()?))
    }
}
