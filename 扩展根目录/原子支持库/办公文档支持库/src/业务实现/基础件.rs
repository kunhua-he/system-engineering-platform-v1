//! 共用基础件：参数取值、JSON 文本转义与入口阈值常量。

use crate::编号与码面::错误码;

pub(super) const 最大公式长度: usize = 4096;
pub(super) const 最大变量个数: usize = 256;
pub(super) const 最大标记长度: usize = 262144;

pub(super) fn 取第几项文本<'a>(参数表: &'a [&'a str], 序位: usize) -> Result<&'a str, u32> {
    match 参数表.get(序位) {
        Some(候选文本) => Ok(*候选文本),
        None => Err(错误码::参数不合法),
    }
}

pub(super) fn 转义文本(输入文本: &str) -> String {
    let mut 输出 = String::new();
    for 当前字元 in 输入文本.chars() {
        match 当前字元 {
            '"' => 输出.push_str("\\\""),
            '\\' => 输出.push_str("\\\\"),
            '\n' => 输出.push_str("\\n"),
            '\r' => 输出.push_str("\\r"),
            '\t' => 输出.push_str("\\t"),
            其他字元 => 输出.push(其他字元),
        }
    }
    输出
}
