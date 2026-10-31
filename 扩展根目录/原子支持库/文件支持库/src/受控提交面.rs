//! 受控提交面 —— 3124 受控创建提交：在受控工作区里按显式文件清单落一次提交。
//!
//! **为什么单独一件**（`开发规范.md` 第六节：单源文件 800 行硬数）：3120–3123 的
//! `受控修复面.rs` 已是六百多行的多关注点件（工作区事务 · 替换 · 验证 · 回滚），
//! 把「按清单暂存并提交」再塞进去会顶破硬数 ⇒ 一个关注点一件，这里只装 3124 的入参校验、
//! 暂存区比对与提交后回读。
//!
//! 助手**只此一份、不另写第二套**：`验证工作区` · `命令` · `路径内文件` · `解析参数数组` ·
//! `转义JSON` · `调用处理` 全部从 `受控修复面` 引用（同一套读槽与同一条 git 调用腿）。
//!
//! 失败语义：边界 / 路径 / 清单为空 / 文件不存在 / 暂存区与清单不一致 / 提交后工作区不干净
//! 一律 `提交范围不合法`（3020）；`git commit` 本身失败是 `提交执行失败`（3021）；
//! `git add` 写不动索引是 `写入失败`（3014，可重试的环境问题）。三者都不算「已提交」。

use crate::受控修复面::{
    命令, 解析参数数组, 调用处理, 路径内文件, 转义JSON, 验证工作区
};
use crate::{能力号, 错误码};
use std::path::{Component, Path};
use std::process::Command;
use v1_contract::数据槽;

fn 校验提交说明(提交说明: &str) -> Result<(), u32> {
    if 提交说明.is_empty() || 提交说明.chars().count() > 200 {
        return Err(错误码::提交范围不合法);
    }
    if 提交说明.chars().any(|字| 字.is_control()) {
        return Err(错误码::提交范围不合法);
    }
    Ok(())
}
fn 解析提交清单(清单文本: &str) -> Result<Vec<String>, u32> {
    let 相对路径表 = 解析参数数组(清单文本).map_err(|_| 错误码::提交范围不合法)?;
    if 相对路径表.is_empty() || 相对路径表.len() > 100 {
        return Err(错误码::提交范围不合法);
    }
    for 相对路径 in &相对路径表 {
        let 候选路径 = Path::new(相对路径);
        if 相对路径.is_empty()
            || 相对路径.contains('\0')
            || 候选路径.is_absolute()
            || 候选路径.components().any(|片段| {
                matches!(
                    片段,
                    Component::ParentDir | Component::RootDir | Component::Prefix(_)
                )
            })
        {
            return Err(错误码::提交范围不合法);
        }
    }
    let mut 排重表 = 相对路径表.clone();
    排重表.sort();
    排重表.dedup();
    if 排重表.len() != 相对路径表.len() {
        return Err(错误码::提交范围不合法);
    }
    Ok(相对路径表)
}
// `core.quotePath=false`：不让 git 把非 ASCII 路径转成引号包裹的八进制转义 ——
// 否则中文文件名在暂存区回读时形态与清单不同，集合比对会假红（那不是调用方的错）。
fn 读暂存清单(工作区根: &Path) -> Result<Vec<String>, u32> {
    let 暂存清单文本 = 命令(
        工作区根,
        [
            "-c",
            "core.quotePath=false",
            "diff",
            "--cached",
            "--name-only",
        ],
    )
    .map_err(|_| 错误码::提交范围不合法)?;
    let mut 结果清单: Vec<String> = Vec::new();
    for 行文本 in 暂存清单文本.lines() {
        if !行文本.is_empty() {
            结果清单.push(行文本.to_owned());
        }
    }
    结果清单.sort();
    Ok(结果清单)
}
pub(crate) fn 受控创建提交(参数: &[&str]) -> Result<Vec<u8>, u32> {
    let 工作区根 = 验证工作区(Path::new(参数[0])).map_err(|_| 错误码::提交范围不合法)?;
    let 提交说明 = 参数[1];
    校验提交说明(提交说明)?;
    let 相对路径表 = 解析提交清单(参数[2])?;
    for 相对路径 in &相对路径表 {
        路径内文件(&工作区根, 相对路径).map_err(|_| 错误码::提交范围不合法)?;
    }
    let mut 暂存参数: Vec<&str> = vec!["add", "--"];
    暂存参数.extend(相对路径表.iter().map(|相对路径| 相对路径.as_str()));
    命令(&工作区根, 暂存参数)?;
    let 暂存清单 = 读暂存清单(&工作区根)?;
    let mut 清单副本 = 相对路径表.clone();
    清单副本.sort();
    if 清单副本 != 暂存清单 {
        return Err(错误码::提交范围不合法);
    }
    // 不用 shell 拼接：说明只经参数数组进 git，引号与空格都不会被二次解释。
    let 提交输出 = Command::new("git")
        .arg("-C")
        .arg(&工作区根)
        .arg("commit")
        .arg("-q")
        .arg("-m")
        .arg(提交说明)
        .output()
        .map_err(|_| 错误码::提交执行失败)?;
    if !提交输出.status.success() {
        return Err(错误码::提交执行失败);
    }
    let 提交摘要 =
        命令(&工作区根, ["rev-parse", "HEAD"]).map_err(|_| 错误码::提交范围不合法)?;
    let 工作区状态 =
        命令(&工作区根, ["status", "--porcelain"]).map_err(|_| 错误码::提交范围不合法)?;
    if !工作区状态.is_empty() {
        return Err(错误码::提交范围不合法);
    }
    let 分支名 = 命令(&工作区根, ["rev-parse", "--abbrev-ref", "HEAD"])
        .map_err(|_| 错误码::提交范围不合法)?;
    // `文件数` 是**整数**（不是带引号的文本）：字段值按 JSON 原生类型给出，调用方不必再转型。
    let 响应文本 = format!(
        "{{\"状态\":\"已提交\",\"提交\":\"{}\",\"提交说明\":\"{}\",\"文件数\":{},\"分支\":\"{}\",\"工作区状态\":\"{}\"}}",
        转义JSON(&提交摘要),
        转义JSON(提交说明),
        相对路径表.len(),
        转义JSON(&分支名),
        转义JSON(&工作区状态),
    );
    Ok(响应文本.into_bytes())
}
pub unsafe extern "C-unwind" fn 受控创建提交入口(
    返回槽: *mut 数据槽,
    参数数: u32,
    参数槽: *const 数据槽,
) {
    unsafe { 调用处理(返回槽, 参数数, 参数槽, 能力号::受控创建提交) }
}

#[cfg(test)]
mod 提交验证样本 {
    use super::*;
    use crate::受控修复面::{命令, 工作区事务};
    use crate::错误码;
    use std::path::Path;
    use std::process::Command;
    use std::sync::atomic::{AtomicU64, Ordering};

    #[test]
    fn 受控创建提交正反验收() {
        static 序号: AtomicU64 = AtomicU64::new(100);
        let 根 = std::env::temp_dir().join(format!(
            "v1-d4-c-{}-{}",
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
        std::fs::write(仓库.join("附件.txt"), "附件原文\n").unwrap();
        跑(&仓库, &["add", "--", "样本.txt", "附件.txt"]);
        跑(&仓库, &["commit", "-qm", "初始"]);
        let 仓库文本 = 仓库.to_str().unwrap();
        let 临时文本 = 临时根.to_str().unwrap();
        assert!(工作区事务(&["创建", 仓库文本, "commit", 临时文本]).is_ok());
        let 工作区 = std::fs::canonicalize(&临时根).unwrap().join("v1-d4-commit");
        let 工作区文本 = 工作区.to_str().unwrap();

        // ① 伪造工作区：仓根不是 v1-d4- 工作区（无 owner 标记）⇒ 3020
        assert_eq!(
            受控创建提交(&[仓库文本, "说明", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        // 不存在的路径同样拒绝（不许把「读不到」当成「干净」）
        let 幽灵工作区 = 根.join("v1-d4-幽灵");
        assert_eq!(
            受控创建提交(&[幽灵工作区.to_str().unwrap(), "说明", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        // ② 提交说明不合规：空 / 含换行 / 超 200 字符 ⇒ 3020
        assert_eq!(
            受控创建提交(&[工作区文本, "", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "两行\n说明", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, &"长".repeat(201), "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        // ③ 清单不合规：空数组 / 越界 / 绝对路径 / 不存在 / 空串 / 重复 / 非 JSON ⇒ 3020
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "[]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "[\"../越界.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "[\"/etc/passwd\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "[\"不存在.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "[\"\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "[\"样本.txt\",\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            受控创建提交(&[工作区文本, "说明", "git add"]).unwrap_err(),
            错误码::提交范围不合法
        );

        // ④ 正常提交：回读 hash 且分支/文件数/说明都在
        std::fs::write(工作区.join("样本.txt"), "第一版内容\n").unwrap();
        let 首个返回 = 受控创建提交(&[工作区文本, "第一版提交", "[\"样本.txt\"]"]).unwrap();
        let 首个文本 = String::from_utf8(首个返回).unwrap();
        let 提交 = 命令(&工作区, ["rev-parse", "HEAD"]).unwrap();
        assert!(首个文本.contains("\"状态\":\"已提交\""), "{首个文本}");
        assert!(首个文本.contains("\"文件数\":1"), "{首个文本}");
        assert!(
            首个文本.contains("\"提交说明\":\"第一版提交\""),
            "{首个文本}"
        );
        assert!(
            首个文本.contains(&format!("\"提交\":\"{提交}\"")),
            "{首个文本}"
        );
        assert!(首个文本.contains("\"分支\":"), "{首个文本}");
        assert!(首个文本.contains("\"工作区状态\":\"\""), "{首个文本}");
        assert!(命令(&工作区, ["status", "--porcelain"]).unwrap().is_empty());
        assert!(
            命令(&工作区, ["cat-file", "-e", &format!("{提交}^{{commit}}")]).is_ok(),
            "回读的 hash 必须能被 git 校验"
        );
        assert_eq!(
            std::fs::read_to_string(工作区.join("样本.txt")).unwrap(),
            "第一版内容\n"
        );

        // ⑤ 无改动重复提交：暂存区为空 ≠ 清单 ⇒ 3020，且没有新提交
        assert_eq!(
            受控创建提交(&[工作区文本, "重复提交", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(命令(&工作区, ["rev-parse", "HEAD"]).unwrap(), 提交);

        // ⑥ 清单多一件但该件没改动：暂存区比清单少一项 ⇒ 3020，且不 commit
        std::fs::write(工作区.join("样本.txt"), "第二版内容\n").unwrap();
        assert_eq!(
            受控创建提交(&[工作区文本, "清单多一件", "[\"样本.txt\",\"附件.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        assert_eq!(
            命令(&工作区, ["rev-parse", "HEAD"]).unwrap(),
            提交,
            "暂存区与清单不一致时不许 commit"
        );
        命令(&工作区, ["reset", "--hard", "HEAD"]).unwrap();

        // ⑦ 提交落地但工作区仍不干净：不许当成功（返回 3020 且如实回读状态）
        std::fs::write(工作区.join("样本.txt"), "带残留的一版\n").unwrap();
        std::fs::write(工作区.join("残留.txt"), "未跟踪残留\n").unwrap();
        assert_eq!(
            受控创建提交(&[工作区文本, "留下残留", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交范围不合法
        );
        let 残留提交标识 = 命令(&工作区, ["rev-parse", "HEAD"]).unwrap();
        assert_ne!(残留提交标识, 提交);
        assert!(!命令(&工作区, ["status", "--porcelain"]).unwrap().is_empty());
        命令(&工作区, ["reset", "--hard", "HEAD"]).unwrap();
        std::fs::remove_file(工作区.join("残留.txt")).unwrap();
        assert!(命令(&工作区, ["status", "--porcelain"]).unwrap().is_empty());

        // ⑧ commit 本身失败：pre-commit 钩子拒绝 ⇒ 3021（与 3020 分开）
        let 钩子目录 = 仓库.join(".git").join("hooks");
        std::fs::create_dir_all(&钩子目录).unwrap();
        let 钩子文件 = 钩子目录.join("pre-commit");
        std::fs::write(&钩子文件, "#!/bin/sh\nexit 1\n").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&钩子文件, std::fs::Permissions::from_mode(0o755)).unwrap();
        }
        std::fs::write(工作区.join("样本.txt"), "钩子拒绝这一版\n").unwrap();
        assert_eq!(
            受控创建提交(&[工作区文本, "钩子拒绝", "[\"样本.txt\"]"]).unwrap_err(),
            错误码::提交执行失败
        );
        std::fs::remove_file(&钩子文件).unwrap();
        命令(&工作区, ["reset", "--hard", "HEAD"]).unwrap();

        assert!(工作区事务(&["关闭", 仓库文本, "commit", 临时文本]).is_ok());
        assert!(!工作区.exists());
        let _ = std::fs::remove_dir_all(&根);
    }
}
