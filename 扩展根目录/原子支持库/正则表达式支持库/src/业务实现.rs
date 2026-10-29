use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合值, 复合元素, 编码复合值载荷};
fn 编译模式(表达式: &str) -> Result<regex::Regex, u32> {
    if 表达式.len() > 4096 {
        return Err(错误码::正则资源受限);
    }
    regex::RegexBuilder::new(表达式)
        .size_limit(1048576)
        .dfa_size_limit(1048576)
        .build()
        .map_err(|错误| match 错误 {
            regex::Error::CompiledTooBig(_) => 错误码::正则资源受限,
            _ => 错误码::正则表达式不合法,
        })
}
fn 装列表(文本列表: Vec<String>) -> Result<(u32, Vec<u8>), u32> {
    let 元素表 = 文本列表
        .into_iter()
        .map(|文本值| 复合元素 {
            名称: String::new(),
            值: 复合值::文本载荷(文本值),
        })
        .collect::<Vec<_>>();
    Ok((
        100,
        编码复合值载荷(100, &元素表).map_err(|_| 错误码::正则资源受限)?,
    ))
}

fn 解析单段(段文本: &str) -> Result<Option<(i64, i64)>, u32> {
    let 去空白 = 段文本.trim();
    if 去空白.is_empty() {
        return Ok(None);
    }
    let 取数 = |片段: &str| -> Result<i64, u32> {
        let 页码值: i64 = 片段
            .trim()
            .parse()
            .map_err(|_| 错误码::正则参数不合法)?;
        if !(1..=1_000_000).contains(&页码值) {
            return Err(错误码::正则参数不合法);
        }
        Ok(页码值)
    };
    if let Some((左段, 右段)) = 去空白.split_once('-') {
        return Ok(Some((取数(左段)?, 取数(右段)?)));
    }
    if let Some((左段, 右段)) = 去空白.split_once('~') {
        return Ok(Some((取数(左段)?, 取数(右段)?)));
    }
    let 单值 = 取数(去空白)?;
    Ok(Some((单值, 单值)))
}

fn 装区间结果(
    是否有效值: bool,
    起始值: i64,
    结束值: i64,
    数值表: Vec<i64>,
) -> Result<(u32, Vec<u8>), u32> {
    let 列表元素 = 数值表
        .into_iter()
        .map(|页码值| 复合元素 {
            名称: String::new(),
            值: 复合值::整数值(页码值),
        })
        .collect::<Vec<_>>();
    let 元素表 = vec![
        复合元素 {
            名称: "是否有效".into(),
            值: 复合值::逻辑型(是否有效值),
        },
        复合元素 {
            名称: "起始".into(),
            值: 复合值::整数值(起始值),
        },
        复合元素 {
            名称: "结束".into(),
            值: 复合值::整数值(结束值),
        },
        复合元素 {
            名称: "数值列表".into(),
            值: 复合值::复合 {
                标签: 100,
                元素表: 列表元素,
            },
        },
    ];
    Ok((
        103,
        编码复合值载荷(103, &元素表).map_err(|_| 错误码::正则资源受限)?,
    ))
}

fn 解析区间操作(文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    let 区间文本 = 文本参数表[0].trim();
    let 模式文本 = 文本参数表[1].trim();
    if 区间文本.len() > 1024 {
        return Err(错误码::正则资源受限);
    }
    let 是范围模式 = match 模式文本 {
        "范围" => true,
        "集合" => false,
        _ => return Err(错误码::正则参数不合法),
    };
    if 区间文本.is_empty() {
        return 装区间结果(false, 0, 0, Vec::new());
    }
    if 是范围模式 {
        if 区间文本.split(',').count() != 1 {
            return Err(错误码::正则参数不合法);
        }
        return match 解析单段(区间文本)? {
            Some((起值, 止值)) if 起值 <= 止值 => 装区间结果(true, 起值, 止值, Vec::new()),
            _ => 装区间结果(false, 0, 0, Vec::new()),
        };
    }
    let mut 数值表: Vec<i64> = Vec::new();
    let mut 有效标记 = false;
    for 段文本 in 区间文本.split(',') {
        let 段结果 = match 解析单段(段文本)? {
            Some(段值) => 段值,
            None => continue,
        };
        let (起值, 止值) = 段结果;
        if 起值 > 止值 {
            continue;
        }
        if (止值 - 起值) as usize + 数值表.len() > 10_000 {
            return Err(错误码::正则资源受限);
        }
        有效标记 = true;
        for 页码值 in 起值..=止值 {
            if !数值表.contains(&页码值) {
                数值表.push(页码值);
            }
        }
    }
    数值表.sort_unstable();
    装区间结果(有效标记, 0, 0, 数值表)
}

pub fn 执行文本操作(编号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 编号 == 能力号::解析区间 {
        return 解析区间操作(文本参数表);
    }
    let 匹配器 = 编译模式(文本参数表[0])?;
    let 原文 = 文本参数表[1];
    if 原文.len() > 65536 {
        return Err(错误码::正则资源受限);
    }
    if 编号 == 能力号::字面替换 {
        let 替换文 = 文本参数表[2];
        if 替换文.len() > 65536 {
            return Err(错误码::正则资源受限);
        }
        let (mut 已到位置, mut 输出长度, mut 匹配数量) = (0usize, 0usize, 0usize);
        // 先预算再分配，不能先展开成巨大结果再判越界；替换文不展开捕获引用。
        for 命中 in 匹配器.find_iter(原文) {
            匹配数量 += 1;
            输出长度 += 命中.start() - 已到位置 + 替换文.len();
            if 输出长度 > 65536 || 匹配数量 > 1000 {
                return Err(错误码::正则资源受限);
            }
            已到位置 = 命中.end();
        }
        输出长度 += 原文.len() - 已到位置;
        if 输出长度 > 65536 {
            return Err(错误码::正则资源受限);
        }
        let mut 输出文本 = String::with_capacity(输出长度);
        已到位置 = 0;
        for 命中 in 匹配器.find_iter(原文) {
            输出文本.push_str(&原文[已到位置..命中.start()]);
            输出文本.push_str(替换文);
            已到位置 = 命中.end();
        }
        输出文本.push_str(&原文[已到位置..]);
        return Ok((4, 输出文本.into_bytes()));
    }
    let mut 文本列表 = Vec::new();
    match 编号 {
        能力号::提取匹配 => {
            for 命中 in 匹配器.find_iter(原文) {
                if 文本列表.len() >= 1000 {
                    return Err(错误码::正则资源受限);
                }
                文本列表.push(命中.as_str().to_owned());
            }
        }
        能力号::分割文本 => {
            for 片段 in 匹配器.split(原文) {
                if 文本列表.len() >= 1000 {
                    return Err(错误码::正则资源受限);
                }
                文本列表.push(片段.to_owned());
            }
        }
        _ => return Err(错误码::正则参数不合法),
    }
    装列表(文本列表)
}
#[cfg(test)]
mod 验证样本 {
    use super::*;
    #[test]
    fn Unicode字面替换及资源界() {
        assert_eq!(
            执行文本操作(4402, &[r"\p{Han}+", "abc中文🙂\0", "$1"])
                .unwrap()
                .1,
            b"abc$1\xf0\x9f\x99\x82\0"
        );
        assert_eq!(执行文本操作(4401, &["(?=x)", "x"]), Err(4402));
        assert_eq!(
            执行文本操作(4402, &["a", "aa", &"x".repeat(65536)]),
            Err(4403)
        );
        assert_eq!(执行文本操作(4401, &["a", &"a".repeat(1001)]), Err(4403));
        let 返回值 = 执行文本操作(4401, &["(a+)+$", &("a".repeat(20000) + "!")]);
        assert!(返回值.is_ok());
    }
}
