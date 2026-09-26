//! 语法树定义 —— 语法树 · 子区间 · 子树止 · 校验。
//!
//! 源出 `语言面.rs` 第 464–661 行（第二节「语法树」的后半），**逐字搬家**。
//!
//! `校验` 里那五条语法树不变量与它们的反向样本（`形状测试/语法树.rs`）是**一对**：
//! 拆的时候刻意没把它们分到两个不相干的文件里（见返回说明第 4 条）。

use super::{记号流, 节点, 形状错误};

/// 语法树：**记号流 + 节点表 + 根下标**。
///
/// 节点表按**深度优先先序**排列（见 [`语法树::校验`] 的「先序连续」一条）：
/// 于是任一节点的整棵子树占据节点表的一段连续区间，`子区间` 是它的直接子节点。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 语法树 {
    /// 记号流（含全文原文）。1102 的产物自带 1101 的产物，自足。
    pub 记号流: 记号流,
    pub 节点表: Vec<节点>,
    /// 根节点在 `节点表` 里的下标。通常为 0，但**不写死为 0**。
    pub 根: u32,
}

impl 语法树 {
    pub fn 新建(记号流: 记号流, 节点表: Vec<节点>, 根: u32) -> Self {
        Self { 记号流, 节点表, 根 }
    }

    pub fn 全文(&self) -> &[u8] {
        &self.记号流.原文
    }

    pub fn 全文长(&self) -> u32 {
        self.记号流.全文长()
    }

    /// 根节点。空节点表返回 `None`。
    pub fn 根节点(&self) -> Option<&节点> {
        self.节点表.get(self.根 as usize)
    }

    /// 某节点的直接子节点下标区间。
    pub fn 子区间(&self, 下标: u32) -> Option<(u32, u32)> {
        Some(self.节点表.get(下标 as usize)?.子区间)
    }

    /// 某节点的原文切片。区间越界返回 `None`。
    pub fn 原文切片(&self, 下标: u32) -> Option<&[u8]> {
        let n = self.节点表.get(下标 as usize)?;
        self.记号流.原文.get(n.起() as usize..n.止() as usize)
    }

    /// 子树终止下标（不含）：从本节点出发，一路走「最后一个子节点」到底，再 +1。
    ///
    /// 只对**先序连续**的节点表有意义。用循环而非递归，避免深树爆栈；
    /// 步数上限为节点数，超出即返回 `None`（防环）。
    pub fn 子树止(&self, 起于: u32) -> Option<u32> {
        let 上限 = self.节点表.len() as u32;
        let mut 当前 = 起于;
        let mut 步 = 0u32;
        loop {
            步 += 1;
            if 步 > 上限 {
                return None;
            }
            let n = self.节点表.get(当前 as usize)?;
            let (起, 止) = n.子区间;
            if 起 >= 止 {
                return Some(当前 + 1);
            }
            当前 = 止 - 1;
        }
    }

    /// 校验全部语法树不变量。返回**第一条**违反。
    pub fn 校验(&self) -> Result<(), 形状错误> {
        use 形状错误::*;
        let 全文长 = self.全文长();
        let 节点数 = self.节点表.len() as u32;

        if self.节点表.is_empty() {
            return Err(节点表为空);
        }
        if self.根 >= 节点数 {
            return Err(根下标越界 { 根: self.根, 节点数 });
        }

        // ── 每个节点的两个区间自身合法 ──
        for (i, n) in self.节点表.iter().enumerate() {
            let 下标 = i as u32;
            if n.起() > n.止() {
                return Err(节点区间倒置 { 下标, 起: n.起(), 止: n.止() });
            }
            if n.止() > 全文长 {
                return Err(节点区间越界 { 下标, 止: n.止(), 全文长 });
            }
            let (子起, 子止) = n.子区间;
            if 子起 > 子止 {
                return Err(子区间倒置 { 下标, 起: 子起, 止: 子止 });
            }
            if 子止 > 节点数 {
                return Err(子区间越界 { 下标, 止: 子止, 节点数 });
            }
            if 子起 <= 下标 && 下标 < 子止 {
                return Err(节点是自身子节点 { 下标 });
            }
        }

        // ── 不变量 T1：根节点的原文区间 == 全文 ──
        let 根 = &self.节点表[self.根 as usize];
        if 根.起() != 0 || 根.止() != 全文长 {
            return Err(根区间不等于全文 { 起: 根.起(), 止: 根.止(), 全文长 });
        }

        // ── 不变量 T4：父引用唯一（根无父、无孤儿、无重复父）──
        let mut 父表: Vec<Option<u32>> = vec![None; self.节点表.len()];
        for (i, n) in self.节点表.iter().enumerate() {
            let 父 = i as u32;
            let (子起, 子止) = n.子区间;
            for 子 in 子起..子止 {
                if 子 == self.根 {
                    return Err(根被当作子节点 { 节点: 子, 父 });
                }
                if let Some(已有) = 父表[子 as usize] {
                    return Err(同一节点有两个父 { 节点: 子, 甲父: 已有, 乙父: 父 });
                }
                父表[子 as usize] = Some(父);
            }
        }
        for (i, 父) in 父表.iter().enumerate() {
            let 下标 = i as u32;
            if 下标 != self.根 && 父.is_none() {
                return Err(节点是孤儿 { 节点: 下标 });
            }
        }

        // ── 不变量 T4 续：从根可达全部节点（唯一父 + 全覆盖 ⇒ 是树，无环）──
        {
            let mut 到过 = vec![false; self.节点表.len()];
            let mut 栈 = vec![self.根];
            let mut 计数 = 0u32;
            while let Some(当前) = 栈.pop() {
                if 到过[当前 as usize] {
                    return Err(节点被重复到达 { 节点: 当前 });
                }
                到过[当前 as usize] = true;
                计数 += 1;
                let (子起, 子止) = self.节点表[当前 as usize].子区间;
                for 子 in 子起..子止 {
                    栈.push(子);
                }
            }
            if 计数 != 节点数 {
                for (i, 到) in 到过.iter().enumerate() {
                    if !到 {
                        return Err(节点从根不可达 { 节点: i as u32 });
                    }
                }
            }
        }

        // ── 不变量 T2：父节点原文区间包住每个子节点 ──
        // ── 不变量 T3：兄弟原文区间按序两两不重叠 ──
        for (i, n) in self.节点表.iter().enumerate() {
            let 父 = i as u32;
            let (子起, 子止) = n.子区间;
            let mut 前一止 = 0u32;
            for (k, 子) in (子起..子止).enumerate() {
                let c = &self.节点表[子 as usize];
                if !n.包住(c.起(), c.止()) {
                    return Err(父未包住子 { 父, 子 });
                }
                if k > 0 && c.起() < 前一止 {
                    return Err(兄弟重叠 { 父, 前: 子 - 1, 后: 子 });
                }
                前一止 = c.止();
            }
        }

        // ── 布局不变量 T5：先序连续 ──
        // 相邻兄弟 c_j、c_{j+1} 必须满足 子树止(c_j) == c_{j+1}。
        // 有了它，同一棵树只有一种节点表写法，且子树可 O(1) 切出。
        for (i, n) in self.节点表.iter().enumerate() {
            let 父 = i as u32;
            let (子起, 子止) = n.子区间;
            if 子止.saturating_sub(子起) < 2 {
                continue;
            }
            for 子 in 子起..子止 - 1 {
                let Some(到) = self.子树止(子) else {
                    return Err(非先序连续 { 父, 子, 子树止: u32::MAX });
                };
                if 到 != 子 + 1 {
                    return Err(非先序连续 { 父, 子, 子树止: 到 });
                }
            }
        }

        Ok(())
    }

    /// 合法的语法树：校验通过才交出。
    pub fn 校验过(记号流: 记号流, 节点表: Vec<节点>, 根: u32) -> Result<Self, 形状错误> {
        let 树 = Self::新建(记号流, 节点表, 根);
        树.校验()?;
        Ok(树)
    }
}
