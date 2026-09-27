//! 缓冲 —— 环形缓冲留痕：不进关键路径 · 满了按策略丢弃并计数 · 状态随实例持有。
//!
//! 裁决与五判据对比见 `项目文档/决策记录/2026-09-27_留痕形状装两个号.md`。

use core::sync::atomic::{AtomicI32, AtomicU32, AtomicU64, AtomicU8, Ordering};

use v1_contract::{能力号, 操作号, 资源号};

use crate::形状::{留痕, 调用类};

/// 「没有」的哨兵：写入序号从 0 起，`u64::MAX` 永不作为真实序号。
const 无序号: u64 = u64::MAX;

/// 认领 / 读取的有界重试上限。
///
/// **必须有界**：留痕永不阻塞调用，宁可丢一条也不许转圈等待。
const 重试上限: u32 = 64;

/// 一个槽：一条留痕 + 它的发布状态。
///
/// 字段各自原子 ⇒ 读写都无数据竞争（不借 `unsafe`）。写者先认领 `在写`，
/// 落完字段后把序号写进 `就绪` 发布；读者用 `就绪` 前后夹一次校验（顺序锁）。
struct 留痕槽 {
    /// 已发布内容对应的写入序号；[`无序号`] = 空。
    就绪: AtomicU64,
    /// 正在写的写入序号；[`无序号`] = 空闲。同格写者靠它串行化。
    在写: AtomicU64,
    实例: AtomicU64,
    /// 号空间存的都是内层 `u32`（原子量不认 newtype）——存取处用 `新` / `取` 一转，
    /// **号空间在类型层立住**（不是把记录退回裸 `u32`，只是原子字段存不了 newtype）。
    能力号: AtomicU32,
    入参指纹: AtomicU64,
    结果码: AtomicI32,
    耗时微秒: AtomicU64,
    追踪号: AtomicU64,
    /// [`调用类`] 的判别值（`0` = 能力 · `1` = 资源）。
    调用类: AtomicU8,
    资源号: AtomicU32,
    操作号: AtomicU32,
}

impl 留痕槽 {
    fn 新建() -> Self {
        Self {
            就绪: AtomicU64::new(无序号),
            在写: AtomicU64::new(无序号),
            实例: AtomicU64::new(0),
            能力号: AtomicU32::new(0),
            入参指纹: AtomicU64::new(0),
            结果码: AtomicI32::new(0),
            耗时微秒: AtomicU64::new(0),
            追踪号: AtomicU64::new(0),
            调用类: AtomicU8::new(调用类::能力 as u8),
            资源号: AtomicU32::new(0),
            操作号: AtomicU32::new(0),
        }
    }

    /// 落字段。发布由调用方在落完之后写 `就绪` 完成。
    fn 落字段(&self, 一条: &留痕) {
        self.实例.store(一条.实例, Ordering::Relaxed);
        self.能力号.store(一条.能力号.取号值(), Ordering::Relaxed);
        self.入参指纹.store(一条.入参指纹, Ordering::Relaxed);
        self.结果码.store(一条.结果码, Ordering::Relaxed);
        self.耗时微秒.store(一条.耗时微秒, Ordering::Relaxed);
        self.追踪号.store(一条.追踪号, Ordering::Relaxed);
        self.调用类.store(一条.调用类 as u8, Ordering::Relaxed);
        self.资源号.store(一条.资源号.取号值(), Ordering::Relaxed);
        self.操作号.store(一条.操作号.取号值(), Ordering::Relaxed);
    }

    /// 读字段。调用方须用 `就绪` 校验前后一致（顺序锁）。
    fn 读字段(&self) -> 留痕 {
        留痕 {
            实例: self.实例.load(Ordering::Relaxed),
            能力号: 能力号::新建(self.能力号.load(Ordering::Relaxed)),
            入参指纹: self.入参指纹.load(Ordering::Relaxed),
            结果码: self.结果码.load(Ordering::Relaxed),
            耗时微秒: self.耗时微秒.load(Ordering::Relaxed),
            追踪号: self.追踪号.load(Ordering::Relaxed),
            // 判别值只可能由本 crate 写（0 或 1）；读到别的值按「能力」兜底，**不 panic**
            //（留痕永不许把调用拖住，也不许因为一条痕崩）。顺序锁保证它与其余字段同批。
            调用类: match self.调用类.load(Ordering::Relaxed) {
                0 => 调用类::能力,
                _ => 调用类::资源,
            },
            资源号: 资源号::新建(self.资源号.load(Ordering::Relaxed)),
            操作号: 操作号::新建(self.操作号.load(Ordering::Relaxed)),
        }
    }
}

/// 丢弃策略。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum 丢弃策略 {
    /// 丢最旧的。
    丢最旧,
    /// 丢最新的（保历史）。
    丢最新,
}

/// 环形缓冲留痕。
pub struct 留痕缓冲 {
    /// 容量。槽表长度恒等于它。
    容量: u32,
    策略: 丢弃策略,
    槽表: Box<[留痕槽]>,
    /// 已发起的写入次数。`fetch_add` 一次即领到一个唯一序号。
    写序号: AtomicU64,
    /// 未写进缓冲的条数（满而丢 + 认领超时）。**必须能读到**。
    丢弃数: AtomicU64,
    /// 写进来但**号位不自洽**的条数（见 [`留痕::自洽`]）。**必须能读到**。
    不自洽数: AtomicU64,
}

/// 并发判据：留痕缓冲必须能被多线程共享（`Sync`）、能搬到别的线程（`Send`）。
///
/// 这是**编译期**判据，不是声称：`留痕缓冲` 里加一个线程亲和的字段（`Cell` / `Rc` /
/// `RefCell`）或全局可变状态，这一行当场红。它之所以成立，是因为缓冲全部状态都是
/// **实例字段 + 原子量**，模块里没有 `static mut`、没有单例、没有进程级计数
/// ——「多个线程同时 `&留痕缓冲`」是它设计好的用法，调用方**不需要**自身加锁。
const _: fn() = || {
    fn 断言可跨线程<值: Send + Sync>() {}
    断言可跨线程::<留痕缓冲>();
    断言可跨线程::<留痕>();
    断言可跨线程::<调用类>();
};

impl 留痕缓冲 {
    /// `容量` 条。容量是契约里的常量，不是拍脑袋的数。
    ///
    /// 容量为 0 也合法：此后每条都计入 [`已丢弃`](Self::已丢弃)，[`取最近`](Self::取最近) 恒空。
    pub fn 新建(容量: u32, 策略: 丢弃策略) -> Self {
        let 槽表: Vec<留痕槽> = (0..容量).map(|_| 留痕槽::新建()).collect();
        Self {
            容量,
            策略,
            槽表: 槽表.into_boxed_slice(),
            写序号: AtomicU64::new(0),
            丢弃数: AtomicU64::new(0),
            不自洽数: AtomicU64::new(0),
        }
    }

    /// 记一条。**永不阻塞、永不失败**（失败也不许影响调用）。
    ///
    /// 常数时间 · 无分配 · 不取锁 · 不等待。满而丢时，丢弃数加一后照常返回。
    ///
    /// **号位不自洽的记录照样记下**（痕的职责是把这次调用记下来，不许因为形状可疑就把事件抹掉），
    /// 但[`不自洽数`](Self::不自洽数)加一 ⇒ **坏痕不许静默**（与「丢痕不许静默」同一条纪律）。
    pub fn 追加一条(&self, 一条: 留痕) {
        if !一条.自洽() {
            self.不自洽数.fetch_add(1, Ordering::Relaxed);
        }

        // 唯一的共享写点：原子领号。拿到唯一序号后，落格互不相干。
        let 写序号 = self.写序号.fetch_add(1, Ordering::Relaxed);
        let 容量 = self.容量 as u64;
        if 容量 == 0 {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }

        let 满 = 写序号 >= 容量;
        // 丢最新：保历史。满了之后新来的一律丢弃，不入槽。
        if 满 && self.策略 == 丢弃策略::丢最新 {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }

        let Some(槽) = self.槽表.get((写序号 % 容量) as usize) else {
            // 槽表与容量不一致（不应发生）。**不 panic**，按丢弃处理。
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        };

        // 认领：同格写者串行化，保证发布出去的一条内部自洽。有界重试，绝不等待。
        if !Self::认领(槽, 写序号) {
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }
        // 认领后再看一眼：若该格已被更新的序号占住，本条已过时，让位（丢最旧下重并发才会出现）。
        let 就绪 = 槽.就绪.load(Ordering::Acquire);
        if 就绪 != 无序号 && 就绪 >= 写序号 {
            槽.在写.store(无序号, Ordering::Release);
            self.丢弃数.fetch_add(1, Ordering::Relaxed);
            return;
        }

        槽.落字段(&一条);
        槽.就绪.store(写序号, Ordering::Release);
        槽.在写.store(无序号, Ordering::Release);

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

    /// 写进来但号位不自洽的条数（[`留痕::自洽`] 为 `false` 的）。
    ///
    /// **必须能读到**：它非零说明**写侧**把号塞错了位（修掉的那个病），
    /// 而记录本身已经进了缓冲 ⇒ 不报出来就等于把写侧缺陷藏起来。
    pub fn 不自洽数(&self) -> u64 {
        self.不自洽数.load(Ordering::Relaxed)
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

    /// 有界重试地认领一格。成功即持有该格（须由调用方写 `在写 = 无序号` 释放）。
    fn 认领(槽: &留痕槽, 序: u64) -> bool {
        for _ in 0..重试上限 {
            if 槽
                .在写
                .compare_exchange(无序号, 序, Ordering::AcqRel, Ordering::Acquire)
                .is_ok()
            {
                return true;
            }
            core::hint::spin_loop();
        }
        false
    }

    /// 顺序锁读一格。`就绪` 前后一致才认，否则有界重试后放弃（并发覆盖）。
    fn 读一条(槽: &留痕槽, 序: u64) -> Option<留痕> {
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
