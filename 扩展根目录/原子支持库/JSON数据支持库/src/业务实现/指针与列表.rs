//! 指针与列表：JSON 指针寻址（RFC 6901 转义与长度校验）、列表取值、真/假文本判定。

use crate::编号与码面::错误码;

use super::解析文本;

pub(super) fn 指针取值<'载荷生命期>(
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

pub(super) fn 取列表(文本内容: &str) -> Result<Vec<serde_json::Value>, u32> {
    match 解析文本(文本内容)? {
        serde_json::Value::Array(列表值) => {
            if 列表值.len() > 10000 {
                return Err(错误码::JSON资源受限);
            }
            Ok(列表值)
        }
        _ => Err(错误码::JSON类型不符),
    }
}

pub(super) fn 取逻辑文本(文本内容: &str) -> Result<bool, u32> {
    match 文本内容.trim() {
        "真" | "true" => Ok(true),
        "假" | "false" => Ok(false),
        _ => Err(错误码::JSON参数不合法),
    }
}
