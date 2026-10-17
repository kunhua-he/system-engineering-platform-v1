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
pub fn 执行文本操作(编号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
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
