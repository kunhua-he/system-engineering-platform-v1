//! 受控修复面 —— 3120–3123 受控 Git 事务：仓外临时工作区 · 唯一文本替换 · 受控验证 · 回滚挑拣。
//!
//! 四个能力号共用同一条读槽腿（`读槽与调用`）与同一条 git 调用腿（`基础件`），
//! 单条作业各住一件（`开发规范.md` 第六节：一个关注点一件）。
//!
//! | 件 | 职责 | 能力号 |
//! | --- | --- | --- |
//! | `基础件.rs` | JSON 转义/对象 · git 命令 · 工作区标识与归属验证 | 各组共用 |
//! | `读槽与调用.rs` | 入参槽校验与返回槽写回 | 各组共用 |
//! | `工作区事务.rs` | 创建/关闭仓外临时工作区 | 3120 |
//! | `路径与参数解析.rs` | 根内安全相对路径 · JSON 数组参数 | 各组共用 |
//! | `唯一替换.rs` | 唯一旧文本原子替换 | 3121 |
//! | `验证执行.rs` | 按参数列表与超时执行验证 | 3122 |
//! | `回滚与挑拣.rs` | 干净状态下回滚/挑拣合入 | 3123 |
//!
//! 3124 受控创建提交住 `受控提交面.rs`，它复用本件的 `命令` · `验证工作区` ·
//! `路径内文件` · `解析参数数组` · `转义JSON` · `调用处理`。

use crate::{能力号, 错误码};
use v1_contract::数据槽;

#[path = "受控修复面/基础件.rs"]
mod 基础件;
#[path = "受控修复面/读槽与调用.rs"]
mod 读槽与调用;
#[path = "受控修复面/工作区事务.rs"]
mod 工作区事务;
#[path = "受控修复面/路径与参数解析.rs"]
mod 路径与参数解析;
#[path = "受控修复面/唯一替换.rs"]
mod 唯一替换;
#[path = "受控修复面/验证执行.rs"]
mod 验证执行;
#[path = "受控修复面/回滚与挑拣.rs"]
mod 回滚与挑拣;

// 跨件与跨文件取用口：`受控提交面` 直接用这几个名字，故仍是 pub(crate)。
pub(crate) use 基础件::{命令, 转义JSON, 验证工作区};
pub(crate) use 读槽与调用::调用处理;
pub(crate) use 路径与参数解析::{路径内文件, 解析参数数组};
pub(crate) use 工作区事务::工作区事务;
// 3121–3123 三条作业只由 `执行业务口` 分派（测试另取），不再往外抛。
use 唯一替换::唯一文本替换;
use 验证执行::受控验证;
use 回滚与挑拣::受控回滚;

pub fn 执行业务口(编号: u32, 参数: &[&str]) -> Result<Vec<u8>, u32> {
    match 编号 {
        3120 => 工作区事务(参数),
        3121 => 唯一文本替换(参数),
        3122 => 受控验证(参数),
        3123 => 受控回滚(参数),
        3124 => crate::受控提交面::受控创建提交(参数),
        _ => Err(错误码::参数不合法),
    }
}

pub unsafe extern "C-unwind" fn 受控工作区入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控工作区) }
}
pub unsafe extern "C-unwind" fn 唯一文本替换入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::唯一文本替换) }
}
pub unsafe extern "C-unwind" fn 受控验证入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控验证) }
}
pub unsafe extern "C-unwind" fn 受控回滚入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控回滚) }
}

#[cfg(test)]
mod 验证样本 {
    use super::*;
    use std::path::Path;
    use std::process::Command;
    use std::sync::atomic::{AtomicU64, Ordering};

    #[test]
    fn 参数数组分项解析() {
        assert_eq!(
            解析参数数组("[\"git\",\"status\",\"--short\"]").unwrap(),
            vec!["git", "status", "--short"]
        );
    }
    #[test]
    fn 参数数组拒绝命令拼接() {
        assert!(解析参数数组("git status").is_err());
    }

    #[test]
    fn 真实Git四原子正反验收() {
        static 序号: AtomicU64 = AtomicU64::new(0);
        let 根 = std::env::temp_dir().join(format!(
            "v1-d4-{}-{}",
            std::process::id(),
            序号.fetch_add(1, Ordering::Relaxed)
        ));
        let 仓库 = 根.join("仓库");
        let 临时根 = 根.join("仓外");
        std::fs::create_dir_all(&仓库).unwrap();
        fn 跑(目录: &Path, 参数: &[&str]) {
            assert!(
                Command::new("git")
                    .current_dir(目录)
                    .args(参数)
                    .status()
                    .unwrap()
                    .success(),
                "git {:?}",
                参数
            )
        }
        跑(&仓库, &["init", "-q"]);
        跑(&仓库, &["config", "user.email", "d4@example.test"]);
        跑(&仓库, &["config", "user.name", "D4 Test"]);
        std::fs::write(仓库.join("样本.txt"), "原始内容\n").unwrap();
        跑(&仓库, &["add", "样本.txt"]);
        跑(&仓库, &["commit", "-qm", "初始"]);
        let 仓库文本 = 仓库.to_str().unwrap();
        let 临时文本 = 临时根.to_str().unwrap();
        let 返回 = 工作区事务(&["创建", 仓库文本, "acceptance", 临时文本]).unwrap();
        let 返回文本 = String::from_utf8(返回).unwrap();
        assert!(返回文本.contains("已创建"));
        let 工作区 = std::fs::canonicalize(&临时根)
            .unwrap()
            .join("v1-d4-acceptance");
        let 工作区文本 = 工作区.to_str().unwrap();
        assert!(唯一文本替换(&[工作区文本, "样本.txt", "原始内容", "第一版内容"]).is_ok());
        assert_eq!(
            std::fs::read_to_string(工作区.join("样本.txt")).unwrap(),
            "第一版内容\n"
        );
        let 原件 = std::fs::read_to_string(工作区.join("样本.txt")).unwrap();
        assert_eq!(
            唯一文本替换(&[工作区文本, "样本.txt", "不存在", "第二版"]).unwrap_err(),
            错误码::精确替换不唯一
        );
        assert_eq!(
            std::fs::read_to_string(工作区.join("样本.txt")).unwrap(),
            原件
        );
        assert!(受控验证(&[工作区文本, "[\"git\",\"status\",\"--short\"]", "1000"]).is_ok());
        assert_eq!(
            受控验证(&[工作区文本, "[\"git\",\"status\",\"--short\"]", "0"]).unwrap_err(),
            错误码::参数不合法
        );
        assert_eq!(
            受控验证(&[工作区文本, "[\"sh\",\"-c\",\"exit 7\"]", "1000"]).unwrap_err(),
            错误码::受控验证失败
        );
        跑(&工作区, &["add", "样本.txt"]);
        跑(&工作区, &["commit", "-qm", "第一版"]);
        let 提交 = 命令(&工作区, ["rev-parse", "HEAD"]).unwrap();
        assert!(受控回滚(&[工作区文本, "回滚", &提交]).is_ok());
        std::fs::write(工作区.join("样本.txt"), "工作区冲突\n").unwrap();
        跑(&工作区, &["add", "样本.txt"]);
        跑(&工作区, &["commit", "-qm", "工作区改动"]);
        跑(&仓库, &["checkout", "-qb", "冲突目标"]);
        std::fs::write(仓库.join("样本.txt"), "目标冲突\n").unwrap();
        跑(&仓库, &["add", "样本.txt"]);
        跑(&仓库, &["commit", "-qm", "目标改动"]);
        let 目标 = 命令(&仓库, ["rev-parse", "HEAD"]).unwrap();
        assert_eq!(
            受控回滚(&[工作区文本, "挑拣合入", &目标]).unwrap_err(),
            错误码::回滚冲突或状态不干净
        );
        assert!(命令(&工作区, ["status", "--porcelain"]).unwrap().is_empty());
        assert!(工作区事务(&["关闭", 仓库文本, "acceptance", 临时文本]).is_ok());
        assert!(!工作区.exists());
        let _ = std::fs::remove_dir_all(&根);
    }
}
