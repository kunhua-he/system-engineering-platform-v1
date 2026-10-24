//! 进程池 · 回收 —— 进程组的强杀与池的析构收尾。
//!
//! 从 `进程池.rs` 拆出（单源 ≤ 400 行 · `开发规范.md` 第六节）。拆法按**关注点**：
//! 父件管**活着的域**（建格 · 取格 · 退避账 · 重拉），本件管**收尾**（不留孤儿）。
//!
//! 两件事分开写是有意的：这些路径都「不出现在正常调用路上」—— 只在不变量被破坏
//! 或池要死了的时候跑。混在父件里，它们会把正常路淹掉。
//!
//! 子件能读父件的私有项（Rust 隐私：子模块看得见祖先的私项）。

use std::process::ExitStatus;
use std::time::{Duration, Instant};

use crate::线程安全::取锁;

use super::{域格, 工作进程, 进程池};

unsafe extern "C" {
    fn kill(进程组号: i32, 信号编号: i32) -> i32;
}

/// 确认子进程退出的一次等待预算（毫秒）：强杀之后最多等这么久收尸。
pub(crate) const 默认确认预算毫秒: u64 = 200;

/// 一次回收的**退出确认结局** —— 正常退出 / 被信号杀 / 超时强杀（另加「没确认上」）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum 回收结局 {
    /// 子进程正常退出（有退出码）且已收尸。
    正常退出,
    /// 子进程被信号杀死（无退出码、有终止信号）。
    被信号杀,
    /// 确认预算内没退 ⇒ 由本侧强杀。
    超时强杀,
    /// 预算耗尽仍未能确认退出。
    未确认退出,
}

/// 按子进程退出状态分档：有退出码 ⇒ 正常退出；无退出码 ⇒ 被信号杀。
pub(crate) fn 按退出状态分档(状态: ExitStatus) -> 回收结局 {
    if 状态.code().is_some() {
        回收结局::正常退出
    } else {
        回收结局::被信号杀
    }
}

/// **强杀进程组并在预算内确认退出** —— 回收路径唯一的「杀 + 收尸」口。
///
/// 三档：等到子进程退出 ⇒ 按退出状态分档；预算内没退 ⇒ `超时强杀`；
/// 收尸本身出错 ⇒ `未确认退出`（**不假装收干净了**）。
pub(crate) fn 击杀并确认退出(工作: &mut 工作进程, 确认预算毫秒: u64) -> 回收结局 {
    if 工作.回收已确认 { return 回收结局::正常退出; }
    击杀进程组(工作.进程组号);
    let _ = 工作.子进程.kill();
    let 期限 = Instant::now() + Duration::from_millis(确认预算毫秒);
    loop {
        match 工作.子进程.try_wait() {
            Ok(Some(状态)) => {
                工作.回收已确认 = true;
                工作.额度租约.take();
                return 按退出状态分档(状态);
            },
            Err(_) => return 回收结局::未确认退出,
            Ok(_) => {}
        }
        if Instant::now() >= 期限 {
            return 回收结局::超时强杀;
        }
        std::thread::sleep(Duration::from_millis(1));
    }
}

/// 按进程组强杀一个执行域的全部进程（含后代）。
pub(crate) fn 击杀进程组(进程组号: i32) {
    // SAFETY: 负进程组号 = 整组；信号 9 = SIGKILL。组号取自被拉起的子进程，必然存在或被回收。
    unsafe {
        kill(-进程组号, 9);
    }
}

/// 回收一份没插进表的域格（进程组强杀 + 收尸），并报退出确认结局。
pub(crate) fn 回收孤儿(格子: &域格) -> 回收结局 {
    let mut 工作 = 取锁(&格子.工作);
    击杀并确认退出(&mut 工作, 默认确认预算毫秒)
}

impl Drop for 进程池 {
    /// 池析构即回收全部工作进程组（不留孤儿）。
    fn drop(&mut self) {
        for 格子 in 取锁(&self.域表).iter() {
            let mut 工作 = 取锁(&格子.工作);
            let _ = 击杀并确认退出(&mut 工作, 默认确认预算毫秒);
        }
    }
}

impl 进程池 {
    /// 域租约已排除新请求后，正常回收并摘掉活进程槽。
    pub(crate) fn 回收空闲域(&self, 标识: &super::执行域标识) -> bool {
        self.移除一域(标识)
    }

    /// **移除一域**：停止旧通道 → 按归属强杀并确认退出 → 摘格；未确认则保留归属及额度。
    ///
    /// 与 [`进程池::击杀一域`] 分开：击杀只杀进程、**留格**（下次调用走「保证域在」重拉）；
    /// 移除是**摘表 + 杀**（部署下架 / 切换后回收旧版用）。返回是否真摘了一格。
    pub fn 移除一域(&self, 标识: &super::执行域标识) -> bool {
        self.移除一域按回收(标识, |工作| 击杀并确认退出(工作, 默认确认预算毫秒))
    }

    fn 移除一域按回收(&self, 标识: &super::执行域标识, 回收动作: impl FnOnce(&mut 工作进程) -> 回收结局) -> bool {
        let Some(句柄) = self.取域句柄(标识) else { return false; };
        {
            let mut 工作 = 句柄.互斥锁();
            工作.运行中 = false;
            let _ = 工作.流通道.shutdown(std::net::Shutdown::Both);
            let _ = 回收动作(&mut 工作);
            if !工作.回收已确认 { return false; }
        }
        let mut 域表锁 = 取锁(&self.域表);
        let Some(序号) = 域表锁.iter().position(|格子| &格子.标识 == 标识 && std::sync::Arc::ptr_eq(&格子.工作, &句柄.工作)) else { return false; };
        let 工作 = match 句柄.工作.try_lock() {
            Ok(工作) => 工作,
            Err(std::sync::TryLockError::Poisoned(中毒)) => 中毒.into_inner(),
            Err(std::sync::TryLockError::WouldBlock) => return false,
        };
        if !工作.回收已确认 { return false; }
        域表锁.remove(序号);
        true
    }
}

#[cfg(test)]
#[test]
fn 移除未确认不得丢归属或归还额度() {
    use super::{执行域标识, 进程池配置};
    let 执行池 = 进程池::创建(进程池配置::default());
    let 域标识 = 执行域标识 { 适配器实例号: 92, 扩展标识串: String::from("回收归属验证"), 制品版本: (1,0,0) };
    执行池.保证域在(&域标识, "/bin/cat", &[]).unwrap();
    let 域引用 = 执行池.取域句柄(&域标识).unwrap();
    let 移除结局 = 执行池.移除一域按回收(&域标识, |_| 回收结局::未确认退出);
    let 保留归属 = 执行池.含域(&域标识);
    let 保留额度 = 执行池.活进程数();
    if !保留归属 { let _ = 域引用.击杀并报结局(); }
    assert!(!移除结局 && 保留归属 && 保留额度 == 1, "未确认退出不能假装移除成功、也不能丢失归属");
    drop(域引用);
    assert!(执行池.移除一域(&域标识));
    assert_eq!(执行池.活进程数(), 0);
    assert_eq!(执行池.已建域数(), 0);
}
