//! 调用留痕 —— 谁 · 调什么 · 入参指纹 · 结果 · 耗时。
//!
//! **不进关键路径**：留痕缺席时调用照样成功，留痕存在时调用不变慢。
//! 所以是本地环形缓冲 + 满了按策略丢弃并计数，不是同步落盘。
//!
//! # 落点（`现代架构落点.md` 第六节 · `开发规范.md` B7）
//!
//! | 要求 | 本 crate 的做法 |
//! |---|---|
//! | 不阻塞调用 | [`留痕缓冲::记`] 只做原子操作与一次字段写入，**不取锁、不等待、不分配** |
//! | 满了按策略丢弃并计数 | 环形缓冲满了：`丢最旧` 覆盖最旧一条、`丢最新` 丢掉新来的一条；两者都把 [`留痕缓冲::已丢弃`] 加一 |
//! | 丢痕不许静默 | 丢弃数**必须能读到**（[`留痕缓冲::已丢弃`]），这是本 crate 的核心判据 |
//! | 状态显式持有 | 缓冲是普通值，随实例持有，**不落进程级全局**（`开发规范.md` B6） |
//!
//! # 并发形状
//!
//! `记` 取 `&self`，多个写者与读者可同时进来：
//!
//! - 写者先用一次 `fetch_add` 原子领号（**唯一的共享写点，常数时间**），再落到 `号 % 容量` 那格；
//! - 每格内容**逐字段原子**，写者写完字段后用 `就绪` 发布，读者按顺序锁（读 `就绪` → 读字段 → 复读 `就绪`）校验，
//!   因此**不需要 `unsafe`**，也不存在数据竞争；
//! - 同格的多个写者用一次 CAS 认领串行化；认领与读取都用**有界重试**，
//!   宁可丢一条也**绝不转圈等待**——留痕永远不许把调用拖住。
//!
//! 硬约束：零第三方依赖 · 标识符中文 · 跨边界形状 [`留痕`] 只用定宽整数（无 `usize`/`isize`）·
//! [`留痕缓冲::记`] **不 panic、不返回 `Result`**。

use core::sync::atomic::{AtomicI32, AtomicU32, AtomicU64, Ordering};

/// 一条留痕。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct 留痕 {
    pub 实例: u64,
    pub 能力号: u32,
    pub 入参指纹: u64,
    pub 结果码: i32,
    pub 耗时微秒: u64,
    pub 追踪号: u64,
}

/// 丢弃策略。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 丢弃策略 {
    /// 丢最旧的。
    丢最旧,
    /// 丢最新的（保历史）。
    丢最新,
}

/// 「没有」的哨兵：写入序号从 0 起，`u64::MAX` 永不作为真实序号。
const 无: u64 = u64::MAX;

/// 认领 / 读取的有界重试上限。
///
/// **必须有界**：留痕永不阻塞调用，宁可丢一条也不许转圈等待。
const 重试上限: u32 = 64;

/// 一个槽：一条留痕 + 它的发布状态。
///
/// 字段各自原子 ⇒ 读写都无数据竞争（不借 `unsafe`）。写者先认领 `在写`，
/// 落完字段后把序号写进 `就绪` 发布；读者用 `就绪` 前后夹一次校验（顺序锁）。
struct 槽 {
    /// 已发布内容对应的写入序号；[`无`] = 空。
    就绪: AtomicU64,
    /// 正在写的写入序号；[`无`] = 空闲。同格写者靠它串行化。
    在写: AtomicU64,
    实例: AtomicU64,
    能力号: AtomicU32,
    入参指纹: AtomicU64,
    结果码: AtomicI32,
    耗时微秒: AtomicU64,
    追踪号: AtomicU64,
}

impl 槽 {
    fn 新建() -> Self {
        Self {
            就绪: AtomicU64::new(无),
            在写: AtomicU64::new(无),
            实例: AtomicU64::new(0),
            能力号: AtomicU32::new(0),
            入参指纹: AtomicU64::new(0),
            结果码: AtomicI32::new(0),
            耗时微秒: AtomicU64::new(0),
            追踪号: AtomicU64::new(0),
        }
    }

    /// 落字段。发布由调用方在落完之后写 `就绪` 完成。
    fn 落字段(&self, 一条: &留痕) {
        self.实例.store(一条.实例, Ordering::Relaxed);
        self.能力号.store(一条.能力号, Ordering::Relaxed);
        self.入参指纹.store(一条.入参指纹, Ordering::Relaxed);
        self.结果码.store(一条.结果码, Ordering::Relaxed);
        self.耗时微秒.store(一条.耗时微秒, Ordering::Relaxed);
        self.追踪号.store(一条.追踪号, Ordering::Relaxed);
    }

    /// 读字段。调用方须用 `就绪` 校验前后一致（顺序锁）。
    fn 读字段(&self) -> 留痕 {
        留痕 {
            实例: self.实例.load(Ordering::Relaxed),
            能力号: self.能力号.load(Ordering::Relaxed),
            入参指纹: self.入参指纹.load(Ordering::Relaxed),
            结果码: self.结果码.load(Ordering::Relaxed),
            耗时微秒: self.耗时微秒.load(Ordering::Relaxed),
            追踪号: self.追踪号.load(Ordering::Relaxed),
        }
    }
}

/// 环形缓冲留痕。
pub struct 留痕缓冲 {
    /// 容量。槽表长度恒等于它。
    容量: u32,
    策略: 丢弃策略,
    槽表: Box<[槽]>,
    /// 已发起的写入次数。`fetch_add` 一次即领到一个唯一序号。
    写序号: AtomicU64,
    /// 未写进缓冲的条数（满而丢 + 认领超时）。**必须能读到**。
    丢弃数: AtomicU64,
}

impl 留痕缓冲 {
    /// `容量` 条。容量是契约里的常量，不是拍脑袋的数。
    ///
    /// 容量为 0 也合法：此后每条都计入 [`已丢弃`](Self::已丢弃)，[`取最近`](Self::取最近) 恒空。
    pub fn 新建(容量: u32, 策略: 丢弃策略) -> Self {
        let 槽表: Vec<槽> = (0..容量).map(|_| 槽::新建()).collect();
        Self {
            容量,
            策略,
            槽表: 槽表.into_boxed_slice(),
            写序号: AtomicU64::new(0),
            丢弃数: AtomicU64::new(0),
        }
    }

    /// 记一条。**永不阻塞、永不失败**（失败也不许影响调用）。
    ///
    /// 常数时间 · 无分配 · 不取锁 · 不等待。满而丢时，丢弃数加一后照常返回。
    pub fn 记(&self, 一条: 留痕) {
        // 唯一的共享写点：原子领号。拿到唯一序号后，落格互不相干。
        let 序 = self.写序号.fetch_add(1, Ordering::Relaxed);
        let 容量 = self.容量 as u64;
        if 容量 == 0 {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }

        let 满 = 序 >= 容量;
        // 丢最新：保历史。满了之后新来的一律丢弃，不入槽。
        if 满 && self.策略 == 丢弃策略::丢最新 {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }

        let Some(槽) = self.槽表.get((序 % 容量) as usize) else {
            // 槽表与容量不一致（不应发生）。**不 panic**，按丢弃处理。
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        };

        // 认领：同格写者串行化，保证发布出去的一条内部自洽。有界重试，绝不等待。
        if !Self::认领(槽, 序) {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }
        // 认领后再看一眼：若该格已被更新的序号占住，本条已过时，让位（丢最旧下重并发才会出现）。
        let 就绪 = 槽.就绪.load(Ordering::Acquire);
        if 就绪 != 无 && 就绪 >= 序 {
            槽.在写.store(无, Ordering::Release);
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }

        槽.落字段(&一条);
        槽.就绪.store(序, Ordering::Release);
        槽.在写.store(无, Ordering::Release);

        // 丢最旧：满了 ⇒ 本条覆盖掉了最旧的一条，计一次丢弃。
        if 满 {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
        }
    }

    /// 因缓冲满而被丢弃的条数。**必须能读到**，否则丢痕是静默的。
    ///
    /// 口径：未写进缓冲的条数——满而丢（`丢最旧` 覆盖掉的、`丢最新` 拒收的）
    /// 加上并发下认领超时放弃的。容量为 0 时等于全部写入次数。
    pub fn 已丢弃(&self) -> u64 {
        self.丢弃数.load(Ordering::Relaxed)
    }

    /// 取最近 `条数` 条。**按时间序**（旧在前、新在后）。
    ///
    /// 边界：`条数 = 0` 恒空；`条数 > 容量` 取全部有效条数。读者不取锁、不阻塞。
    pub fn 取最近(&self, 条数: u32) -> Vec<留痕> {
        let 容量 = self.容量 as u64;
        let 条数 = 条数 as u64;
        if 容量 == 0 || 条数 == 0 {
            return Vec::new();
        }

        let 总 = self.写序号.load(Ordering::Acquire);
        let 有效 = 总.min(容量);
        if 有效 == 0 {
            return Vec::new();
        }
        let 取 = 条数.min(有效);

        // 有效序号区间 [起, 止)：
        // 丢最新保历史 ⇒ 从 0 起；丢最旧覆盖 ⇒ 取最近 有效 条。
        let (止, 起点) = match self.策略 {
            丢弃策略::丢最新 => (有效, 有效 - 取),
            丢弃策略::丢最旧 => (总, 总 - 取),
        };

        let mut 结果 = Vec::with_capacity(取 as usize);
        for 序 in 起点..止 {
            let Some(槽) = self.槽表.get((序 % 容量) as usize) else {
                continue;
            };
            if let Some(一条) = Self::读一条(槽, 序) {
                结果.push(一条);
            }
        }
        结果
    }

    /// 有界重试地认领一格。成功即持有该格（须由调用方写 `在写 = 无` 释放）。
    fn 认领(槽: &槽, 序: u64) -> bool {
        for _ in 0..重试上限 {
            if 槽
                .在写
                .compare_exchange(无, 序, Ordering::AcqRel, Ordering::Acquire)
                .is_ok()
            {
                return true;
            }
            core::hint::spin_loop();
        }
        false
    }

    /// 顺序锁读一格。`就绪` 前后一致才认，否则有界重试后放弃（并发覆盖）。
    fn 读一条(槽: &槽, 序: u64) -> Option<留痕> {
        for _ in 0..重试上限 {
            let 前 = 槽.就绪.load(Ordering::Acquire);
            if 前 != 序 {
                core::hint::spin_loop();
                continue;
            }
            let 一条 = 槽.读字段();
            if 槽.就绪.load(Ordering::Acquire) == 前 {
                return Some(一条);
            }
            core::hint::spin_loop();
        }
        None
    }
}

#[cfg(test)]
mod 测试 {
    use super::*;

    /// 造一条可辨别的留痕：`追踪号` 就是它的身份，`耗时微秒` 也带上，便于核对字段完整。
    fn 一条(追踪号: u64) -> 留痕 {
        留痕 {
            实例: 7,
            能力号: 1001,
            入参指纹: 追踪号.wrapping_mul(0x9E37_79B9_7F4A_7C15),
            结果码: 0,
            耗时微秒: 追踪号 * 10,
            追踪号,
        }
    }

    fn 追踪号列(表: &[留痕]) -> Vec<u64> {
        表.iter().map(|条| 条.追踪号).collect()
    }

    #[test]
    fn 容量内不丢() {
        let 缓冲 = 留痕缓冲::新建(8, 丢弃策略::丢最旧);
        for i in 0..5 {
            缓冲.记(一条(i));
        }
        assert_eq!(缓冲.已丢弃(), 0, "容量内不许丢");
        assert_eq!(追踪号列(&缓冲.取最近(8)), vec![0, 1, 2, 3, 4], "按时间序返回");
        // 字段完整（不是只存了个号）。
        let 首条 = 缓冲.取最近(1)[0];
        assert_eq!(首条, 一条(4));
    }

    #[test]
    fn 丢最旧_超容量() {
        let 缓冲 = 留痕缓冲::新建(3, 丢弃策略::丢最旧);
        for i in 0..5 {
            缓冲.记(一条(i));
        }
        assert_eq!(缓冲.已丢弃(), 2, "超出 2 条，丢最旧计数应为 2");
        assert_eq!(追踪号列(&缓冲.取最近(10)), vec![2, 3, 4], "保最近，旧的两条被覆盖");
        assert_eq!(追踪号列(&缓冲.取最近(3)), vec![2, 3, 4]);
        assert_eq!(追踪号列(&缓冲.取最近(2)), vec![3, 4]);
        assert_eq!(追踪号列(&缓冲.取最近(1)), vec![4]);
    }

    #[test]
    fn 丢最新_超容量() {
        let 缓冲 = 留痕缓冲::新建(3, 丢弃策略::丢最新);
        for i in 0..5 {
            缓冲.记(一条(i));
        }
        assert_eq!(缓冲.已丢弃(), 2, "超出 2 条，丢最新计数应为 2");
        assert_eq!(追踪号列(&缓冲.取最近(10)), vec![0, 1, 2], "保历史，最先的 3 条留住");
        assert_eq!(追踪号列(&缓冲.取最近(2)), vec![1, 2]);
        assert_eq!(追踪号列(&缓冲.取最近(1)), vec![2]);
    }

    #[test]
    fn 取最近_边界() {
        let 缓冲 = 留痕缓冲::新建(4, 丢弃策略::丢最旧);
        // 空缓冲：N=0 与 N>容量 都空。
        assert!(缓冲.取最近(0).is_empty());
        assert!(缓冲.取最近(4).is_empty());
        assert!(缓冲.取最近(100).is_empty());

        for i in 0..4 {
            缓冲.记(一条(i));
        }
        assert!(缓冲.取最近(0).is_empty(), "N=0 恒空");
        assert_eq!(追踪号列(&缓冲.取最近(100)), vec![0, 1, 2, 3], "N>容量取全部");
        assert_eq!(追踪号列(&缓冲.取最近(4)), vec![0, 1, 2, 3], "N=容量取全部");
    }

    #[test]
    fn 取最近_丢最新_边界() {
        let 缓冲 = 留痕缓冲::新建(3, 丢弃策略::丢最新);
        assert!(缓冲.取最近(0).is_empty());
        for i in 0..7 {
            缓冲.记(一条(i));
        }
        assert_eq!(缓冲.已丢弃(), 4);
        assert!(缓冲.取最近(0).is_empty(), "N=0 恒空");
        assert_eq!(追踪号列(&缓冲.取最近(100)), vec![0, 1, 2], "N>容量取全部有效");
    }

    #[test]
    fn 容量零() {
        for 策略 in [丢弃策略::丢最旧, 丢弃策略::丢最新] {
            let 缓冲 = 留痕缓冲::新建(0, 策略);
            缓冲.记(一条(1));
            缓冲.记(一条(2));
            assert_eq!(缓冲.已丢弃(), 2, "容量 0：每条都计入丢弃");
            assert!(缓冲.取最近(4).is_empty());
        }
    }

    #[test]
    fn 反复覆盖不崩() {
        // 反复覆盖：只验「记」常数时间、不 panic、计数守恒。
        let 缓冲 = 留痕缓冲::新建(4, 丢弃策略::丢最旧);
        for i in 0..10_000u64 {
            缓冲.记(一条(i));
        }
        assert_eq!(缓冲.已丢弃(), 10_000 - 4);
        assert_eq!(追踪号列(&缓冲.取最近(4)), vec![9_996, 9_997, 9_998, 9_999]);
    }

    #[test]
    fn 多实例互不污染() {
        let 甲 = 留痕缓冲::新建(2, 丢弃策略::丢最旧);
        let 乙 = 留痕缓冲::新建(2, 丢弃策略::丢最旧);
        甲.记(一条(1));
        甲.记(一条(2));
        甲.记(一条(3));
        乙.记(一条(9));
        assert_eq!(甲.已丢弃(), 1);
        assert_eq!(乙.已丢弃(), 0);
        assert_eq!(追踪号列(&甲.取最近(2)), vec![2, 3]);
        assert_eq!(追踪号列(&乙.取最近(2)), vec![9]);
    }
}
