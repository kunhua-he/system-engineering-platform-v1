use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合值, 复合元素, 编码复合值载荷};
fn 解析文本(原文: &str) -> Result<serde_json::Value, u32> {
    if 原文.len() > 65536 {
        return Err(错误码::JSON资源受限);
    }
    let (mut 深度, mut 字符串内, mut 转义中) = (0usize, false, false);
    for 字节值 in 原文.bytes() {
        if 字符串内 {
            if 转义中 {
                转义中 = false;
            } else if 字节值 == b'\\' {
                转义中 = true;
            } else if 字节值 == b'"' {
                字符串内 = false;
            }
        } else {
            match 字节值 {
                b'"' => 字符串内 = true,
                b'[' | b'{' => {
                    深度 += 1;
                    if 深度 > 64 {
                        return Err(错误码::JSON资源受限);
                    }
                }
                b']' | b'}' => 深度 = 深度.saturating_sub(1),
                _ => {}
            }
        }
    }
    crate::JSON树解析::解析JSON树(原文).map_err(|_| 错误码::JSON参数不合法)
}
fn 指针取值<'载荷生命期>(
    解析值: &'载荷生命期 serde_json::Value,
    选择指针: &str,
) -> Result<&'载荷生命期 serde_json::Value, u32> {
    if 选择指针.len() > 4096 {
        return Err(错误码::JSON资源受限);
    }
    if !选择指针.is_empty() && !选择指针.starts_with('/') {
        return Err(错误码::JSON参数不合法);
    }
    let mut 字符迭代 = 选择指针.chars();
    while let Some(字符值) = 字符迭代.next() {
        if 字符值 == '~' && !matches!(字符迭代.next(), Some('0' | '1')) {
            return Err(错误码::JSON参数不合法);
        }
    }
    解析值.pointer(选择指针).ok_or(错误码::JSON路径不存在)
}
pub fn 执行文本操作(编号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    let 解析值 = 解析文本(文本参数表[0])?;
    if 编号 == 能力号::提取摘要 {
        let (类型名称, 成员数量) = match &解析值 {
            serde_json::Value::Null => ("空值", 0),
            serde_json::Value::Bool(_) => ("逻辑", 0),
            serde_json::Value::Number(_) => ("数值", 0),
            serde_json::Value::String(_) => ("文本", 0),
            serde_json::Value::Array(列表值) => ("列表", 列表值.len()),
            serde_json::Value::Object(成员表) => ("对象", 成员表.len()),
        };
        let 元素表 = vec![
            复合元素 {
                名称: "类型名称".into(),
                值: 复合值::文本载荷(类型名称.into()),
            },
            复合元素 {
                名称: "成员数量".into(),
                值: 复合值::整数值(成员数量 as i64),
            },
            复合元素 {
                名称: "规范文本".into(),
                值: 复合值::文本载荷(解析值.to_string()),
            },
        ];
        return Ok((
            103,
            编码复合值载荷(103, &元素表).map_err(|_| 错误码::JSON资源受限)?,
        ));
    }
    let 返回文本 = match 编号 {
        能力号::规范化JSON => 解析值.to_string(),
        能力号::按指针取值 => 指针取值(&解析值, 文本参数表[1])?.to_string(),
        能力号::按指针取文本 => 指针取值(&解析值, 文本参数表[1])?
            .as_str()
            .ok_or(错误码::JSON类型不符)?
            .to_owned(),
        _ => return Err(错误码::JSON参数不合法),
    };
    if 返回文本.len() > 65536 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回文本.into_bytes()))
}
#[cfg(test)]
mod 验证样本 {
    use super::*;
    #[test]
    fn 保留引擎私有同名对象键() {
        let 原文 = r#"{"$serde_json::private::Number":"123"}"#;
        assert_eq!(执行文本操作(5201, &[原文]).unwrap().1, 原文.as_bytes());
    }
    #[test]
    fn 大数空值和路径不混淆() {
        let 原文 = r#"{"金额":123456789012345678901234567890,"空":null,"假":false,"零":0,"空文":"","a/b":{"~":"中文\u0000"}}"#;
        for (路径, 期望) in [
            ("/金额", "123456789012345678901234567890"),
            ("/空", "null"),
            ("/假", "false"),
            ("/零", "0"),
            ("/空文", "\"\""),
        ] {
            assert_eq!(
                执行文本操作(5202, &[原文, 路径]).unwrap().1,
                期望.as_bytes()
            );
        }
        assert_eq!(
            执行文本操作(5203, &[原文, "/a~1b/~0"]).unwrap().1,
            "中文\0".as_bytes()
        );
        assert_eq!(执行文本操作(5202, &[原文, "/不存在"]), Err(5202));
        assert_eq!(执行文本操作(5203, &[原文, "/零"]), Err(5203));
        assert_eq!(执行文本操作(5202, &[原文, "/~2"]), Err(5201));
        assert_eq!(执行文本操作(5201, &["NaN"]), Err(5201));
        assert_eq!(
            执行文本操作(5201, &[&("[".repeat(65) + &"]".repeat(65))]),
            Err(5204)
        );
    }
}
