//! `KEY=VALUE` 环境文件解析（3114）。

use crate::编号与码面::错误码;
use v1_contract::复合值载荷::{复合元素, 复合值, 编码复合值载荷};


pub(super) fn 剥离成对引号(待剥文本: &str) -> String {
    let 字节表 = 待剥文本.as_bytes();
    if 字节表.len() >= 2 {
        let 首字节 = 字节表[0];
        let 尾字节 = 字节表[字节表.len() - 1];
        if (首字节 == b'"' && 尾字节 == b'"') || (首字节 == b'\'' && 尾字节 == b'\'') {
            return 待剥文本[1..待剥文本.len() - 1].to_string();
        }
    }
    待剥文本.to_string()
}


pub(super) fn 解析环境文本(全文: &str) -> Result<(u32, Vec<u8>), u32> {
    let mut 环境表: Vec<复合元素> = Vec::new();
    for 环境行 in 全文.lines() {
        let 行去空 = 环境行.trim();
        if 行去空.is_empty() || 行去空.starts_with('#') {
            continue;
        }
        let 切分结果 = match 行去空.split_once('=') {
            Some(切分对) => 切分对,
            None => continue,
        };
        let 键名 = 切分结果.0.trim();
        if 键名.is_empty() {
            continue;
        }
        let 去引号值 = 剥离成对引号(切分结果.1.trim());
        环境表.retain(|已有项| 已有项.名称 != 键名);
        环境表.push(复合元素 {
            名称: 键名.to_string(),
            值: 复合值::文本载荷(去引号值),
        });
        if 环境表.len() > 10000 {
            return Err(错误码::资源受限);
        }
    }
    let 条目数 = 环境表.len() as i64;
    let 外层表 = vec![
        复合元素 {
            名称: "环境".into(),
            值: 复合值::复合 {
                标签: 101,
                元素表: 环境表,
            },
        },
        复合元素 {
            名称: "条目数".into(),
            值: 复合值::整数值(条目数),
        },
    ];
    Ok((
        103,
        编码复合值载荷(103, &外层表).map_err(|_| 错误码::资源受限)?,
    ))
}

