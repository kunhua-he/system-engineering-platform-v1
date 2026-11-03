use std::path::{Path, PathBuf};

use super::独占锁;

/// 锁件路径：与回执同目录的 `运行回执.jsonl.锁`。
///
/// ★ 锁必须挂在**不换 inode 的那一份件**上 —— 回执的写回是 `rename`，锁若挂在回执自身，
pub(super) fn 锁件路径(路径: &Path) -> PathBuf {
    路径.with_extension("jsonl.锁")
}

// ★ FFI 与「有界等待取锁」搬进子件（`src/回执/独占锁.rs`）：本件只留声明，
//   临界区一律经 `独占锁::取锁(&锁件路径, 等待毫秒)`，不再有 `Option` 那种「拿不到就降级」的形状。

/// 取锁最多等多久（毫秒）。★ 有界是硬口径：持锁者崩在临界区时，等待方**自身**回失败，
/// 不许把整条跑案例的进程挂死在这里（`独占锁::取锁` 用 `LOCK_NB` 轮询实现）。
pub const 锁等待毫秒: u64 = 2000;

/// **追加一行**。追加不是覆盖：回执是历史，抹掉历史就没法判「回执是不是旧的」。
///
/// 并发安全的口径见文件头：持锁 ⇒ 读全文 ⇒ 追加 ⇒ `rename`。`rename` 之前盘上一直是旧件，
/// 之后是「旧件 + 这一条新行」—— **中间没有半行状态**。拿不到锁 ⇒ 回明确错误、**这条不写**。
pub fn 追加一行(路径: &Path, 源码行: &str) -> Result<(), String> {
    追加一行带等待(路径, 源码行, 锁等待毫秒)
}

/// [`追加一行`] 的本体：等待毫秒由调用方给（单元测试要能把「等多久」压到毫秒级验有界）。
pub(super) fn 追加一行带等待(
    路径: &Path,
    源码行: &str,
    等待毫秒: u64,
) -> Result<(), String> {
    if let Some(父目录) = 路径.parent() {
        std::fs::create_dir_all(父目录)
            .map_err(|错误| format!("建不了 {}：{错误}", 父目录.display()))?;
    }
    // ★ 锁凭据活到函数末 ⇒ 「读全文 → 追加 → rename」整段都在锁里（作用域结束放锁）。
    let _锁凭据 = 独占锁::取锁(&锁件路径(路径), 等待毫秒)
        .map_err(|失败原因| format!("回执没写：{失败原因}"))?;
    let mut 原文 = match std::fs::read(路径) {
        Ok(原文) => 原文,
        Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => Vec::new(),
        Err(错误) => return Err(format!("读不了 {}：{错误}", 路径.display())),
    };
    // 上一次坏写留下的残尾先封口：不然新行会黏在它后面，把一条好行也一起毁掉。
    if !原文.is_empty() && !原文.ends_with(b"\n") {
        原文.push(b'\n');
    }
    原文.extend_from_slice(源码行.as_bytes());
    原文.push(b'\n');
    let 临时路径 = 路径.with_extension("jsonl.写入中");
    std::fs::write(&临时路径, &原文)
        .map_err(|错误| format!("写不进临时件 {}：{错误}", 临时路径.display()))?;
    std::fs::rename(&临时路径, 路径).map_err(|错误| {
        let _ = std::fs::remove_file(&临时路径);
        format!("换不进 {}：{错误}", 路径.display())
    })
}
