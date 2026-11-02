//! 共用基础件：XML 属性取值与嵌套深度上限。

use quick_xml::events::BytesStart as 起始标签;
use quick_xml::XmlVersion::Implicit1_0 as 默认XML版本;

pub(super) const XML嵌套深度上限: usize = 64;

pub(super) fn 取属性文本(标签值: &起始标签<'_>, 键名: &str) -> Option<String> {
    for 属性结果 in 标签值.attributes() {
        let 属性项 = 属性结果.ok()?;
        if 属性项.key.local_name().as_ref() == 键名 {
            return 属性项.normalized_value(默认XML版本).ok().map(|文本值| 文本值.into_owned());
        }
    }
    None
}

pub(super) fn 取开关属性(标签值: &起始标签<'_>) -> Result<bool, u32> {
    match 取属性文本(标签值, "val") {
        None => Ok(true),
        Some(取值文本) => Ok(!(取值文本 == "0" || 取值文本.eq_ignore_ascii_case("false"))),
    }
}
