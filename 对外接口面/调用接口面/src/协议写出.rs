//! JSON 写出 —— 手写，零第三方依赖。
//!
//! **缩进版（两空格）**，与 `项目文档/设计文档/接口面形状.md` 里的示例同形：
//! 根端点的返回是给人也是给 agent 读的「说明书」，压成一行就丢掉了这层用途。
//!
//! # 两条确定性
//!
//! 1. **键序 = 插入序**（对象是 `Vec`，不是哈希表）⇒ 同一份数据两次序列化逐字节相同。
//! 2. **非有限浮点写 `null`**：`NaN` / `±Infinity` 不是合法 JSON，写出去就是给出一个
//!    调用方解析不了的东西。宁可写 `null`（= 无值），也不产出非法 JSON。

use crate::协议值::协议值;

/// 序列化为缩进版 JSON 文本（**不含**结尾换行）。
pub fn 写(值: &协议值) -> String {
    let mut 出 = String::new();
    写值(&mut 出, 值, 0);
    出
}

fn 缩进(出: &mut String, 层: usize) {
    出.push('\n');
    for _ in 0..层 {
        出.push_str("  ");
    }
}

fn 写值(出: &mut String, 值: &协议值, 层: usize) {
    match 值 {
        协议值::空 => 出.push_str("null"),
        协议值::真 => 出.push_str("true"),
        协议值::假 => 出.push_str("false"),
        协议值::整数(数) => 出.push_str(&数.to_string()),
        协议值::无符号(数) => 出.push_str(&数.to_string()),
        协议值::小数(数) => {
            if 数.is_finite() {
                出.push_str(&数.to_string());
            } else {
                // 非有限值不是合法 JSON（见文件头）。
                出.push_str("null");
            }
        }
        协议值::文本(文) => 写文本(出, 文),
        协议值::数组(项) => {
            if 项.is_empty() {
                出.push_str("[]");
                return;
            }
            出.push('[');
            for (序, 一) in 项.iter().enumerate() {
                if 序 > 0 {
                    出.push(',');
                }
                缩进(出, 层 + 1);
                写值(出, 一, 层 + 1);
            }
            缩进(出, 层);
            出.push(']');
        }
        协议值::对象(成员) => {
            if 成员.is_empty() {
                出.push_str("{}");
                return;
            }
            出.push('{');
            for (序, (键, 一)) in 成员.iter().enumerate() {
                if 序 > 0 {
                    出.push(',');
                }
                缩进(出, 层 + 1);
                写文本(出, 键);
                出.push_str(": ");
                写值(出, 一, 层 + 1);
            }
            缩进(出, 层);
            出.push('}');
        }
    }
}

/// 写一个 JSON 字符串。非 ASCII 原样走 UTF-8（响应头声明 `charset=utf-8`），
/// 不转成 `\uXXXX`——转了体积大三倍且更难读。
fn 写文本(出: &mut String, 文: &str) {
    出.push('"');
    for 字 in 文.chars() {
        match 字 {
            '"' => 出.push_str("\\\""),
            '\\' => 出.push_str("\\\\"),
            '\n' => 出.push_str("\\n"),
            '\r' => 出.push_str("\\r"),
            '\t' => 出.push_str("\\t"),
            '\u{08}' => 出.push_str("\\b"),
            '\u{0C}' => 出.push_str("\\f"),
            // 其余控制字符必须转义（裸控制字符不是合法 JSON）。
            字 if (字 as u32) < 0x20 => {
                出.push_str(&format!("\\u{:04x}", 字 as u32));
            }
            字 => 出.push(字),
        }
    }
    出.push('"');
}

#[cfg(test)]
mod 写出测试 {
    use super::*;

    #[test]
    fn 转义_引号反斜杠控制字符都转() {
        assert_eq!(写(&协议值::文本("a\"b\\c\nd\u{1}".to_owned())), r#""a\"b\\c\nd\u0001""#);
        // 非 ASCII 原样走 UTF-8。
        assert_eq!(写(&协议值::文本("接口".to_owned())), "\"接口\"");
    }

    #[test]
    fn 空容器与嵌套_形状对() {
        assert_eq!(写(&协议值::数组(Vec::new())), "[]");
        assert_eq!(写(&协议值::对象(Vec::new())), "{}");
        let 值 = 协议值::对象(vec![
            ("甲".to_owned(), 协议值::整数(1)),
            ("乙".to_owned(), 协议值::数组(vec![协议值::真])),
        ]);
        assert_eq!(写(&值), "{\n  \"甲\": 1,\n  \"乙\": [\n    true\n  ]\n}");
    }

    #[test]
    fn 非有限浮点写空值_不产出非法协议体() {
        assert_eq!(写(&协议值::小数(f64::NAN)), "null");
        assert_eq!(写(&协议值::小数(f64::INFINITY)), "null");
    }
}
