use super::*;
use std::path::{Path, PathBuf};

/// 语料根目录。不存在时往返测试跳过（不失败）。
pub(crate) const 语料根目录: &str = "/tmp/易语言源码";

// 段数据里的库中文名是 **GBK** 字节（不是 UTF-8），字节串字面量放不下非 ASCII 字符，
// 故这里直接写出实测得到的 GBK 字节（与容器层测试同一串）。
pub(crate) const GBK系统核心支持库: &[u8] =
    &[0xCF, 0xB5, 0xCD, 0xB3, 0xBA, 0xCB, 0xD0, 0xC4, 0xD6, 0xA7, 0xB3, 0xD6, 0xBF, 0xE2];

pub(crate) fn 首个不一致(原文: &[u8], 产物: &[u8]) -> u64 {
    let 上限 = 原文.len().min(产物.len());
    for 位 in 0..上限 {
        if 原文[位] != 产物[位] {
            return 位 as u64;
        }
    }
    上限 as u64
}

/// 大小写不敏感地认 `.e` / `.ec`。
pub(crate) fn 是语料文件(路: &Path) -> bool {
    match 路.extension().and_then(|扩展| 扩展.to_str()) {
        Some(扩展) => {
            let 小写 = 扩展.to_ascii_lowercase();
            小写 == "e" || 小写 == "ec"
        }
        None => false,
    }
}

/// 递归收集语料。用 `file_type()` 不追符号链接，避免环。
pub(crate) fn 收集语料(根: &Path, 出: &mut Vec<PathBuf>) {
    let Ok(项集) = std::fs::read_dir(根) else {
        return;
    };
    for 项 in 项集.flatten() {
        let Ok(类型) = 项.file_type() else { continue };
        let 路 = 项.path();
        if 类型.is_dir() {
            收集语料(&路, 出);
        } else if 类型.is_file() && 是语料文件(&路) {
            出.push(路);
        }
    }
}

/// 造一条合法记录流：1 条支持库引用（5 段）+ 4 字节其余载荷。
pub(crate) fn 样例流() -> 记录流 {
    记录流 {
        头: 段数据头 {
            段序号: 4,
            保留: 0,
            校验值: 0x0A06_CD88,
            体长: 0,
            补零: [0; 40],
        },
        体头: 段体头 { 首字段: 0x0001_0064 },
        支持库: 支持库表 {
            首数组: vec![193],
            次数组: vec![5],
            末数组: vec![0],
            引用表: vec![支持库引用::由字段(vec![
                b"KRNLN".to_vec(),
                b"d09f2340818511d396f6aaf844c7e325".to_vec(),
                b"4".to_vec(),
                b"2".to_vec(),
                GBK系统核心支持库.to_vec(),
            ])],
        },
        其余载荷: vec![0x01, 0x00, 0x01, 0x52],
    }
}

pub(crate) fn 样例字节() -> Vec<u8> {
    let mut 流 = 样例流();
    流.重算体长();
    生成段数据(&流).expect("样例应能生成")
}
