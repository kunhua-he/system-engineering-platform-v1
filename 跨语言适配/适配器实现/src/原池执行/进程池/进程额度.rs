//! 活进程许可：所有首次启动与重拉共用同一原子额度。
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};
use super::进程池错误;

pub(crate) struct 进程额度租约(Arc<AtomicU32>);
impl Drop for 进程额度租约 {
    fn drop(&mut self) { self.0.fetch_sub(1, Ordering::AcqRel); }
}

pub(crate) fn 申请进程额度(活进程数: &Arc<AtomicU32>, 上限: u32) -> Result<进程额度租约, 进程池错误> {
    活进程数.fetch_update(Ordering::AcqRel, Ordering::Acquire, |已占用| {
        if 已占用 < 上限 { Some(已占用 + 1) } else { None }
    }).map_err(|_| 进程池错误::子进程数已满)?;
    Ok(进程额度租约(Arc::clone(活进程数)))
}
