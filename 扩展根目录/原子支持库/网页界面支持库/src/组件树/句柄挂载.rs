//! 句柄挂载：把组件句柄写进片段的首个标签，不改片段结构、不套包装层。
//!
//! 为什么不做外包一层 `<div data-hs-h>`：网格与行列靠直接子元素选择器排版，
//! 多套一层 `display:contents` 会改变选择器命中关系，界面会歪。
//! 所以做法是字符串手术：找到首个标签的结束尖括号，在它前面插一个属性。

/// 在片段首个标签里插入 `data-hs-h` 属性。
///
/// 片段不以 `<` 开头（纯文本）时原样返回 —— 这类节点没有可替换的根元素，
/// 也就不该发句柄。自闭合标签（`<img … />`）插在斜杠之前。
pub(crate) fn 注入句柄属性(片段: &str, 句柄: u64) -> String {
    let 起点 = match 片段.find('<') {
        Some(位置) => 位置,
        None => return 片段.to_string(),
    };
    let 尾部 = &片段[起点..];
    // 注释与闭标签不挂：注释 `<!--` 与 `</` 都不是元素开始。
    if 尾部.starts_with("<!--") || 尾部.starts_with("</") {
        return 片段.to_string();
    }
    let mut 引号: Option<char> = None;
    for (偏移, 字符) in 尾部.char_indices() {
        match 字符 {
            '"' | '\'' => match 引号 {
                Some(已开) if 已开 == 字符 => 引号 = None,
                None => 引号 = Some(字符),
                _ => {}
            },
            '>' if 引号.is_none() => {
                let 绝对 = 起点 + 偏移;
                let mut 插入点 = 跳过尾部空白(片段, 绝对);
                let 属性文本 = if 片段[..插入点].ends_with('/') {
                    // 自闭合：属性插在斜杠前，斜杠后的空格留给 `/>`。
                    插入点 -= 1;
                    let 前面有空白 = 片段[..插入点]
                        .chars()
                        .last()
                        .map(|字| 字.is_whitespace())
                        .unwrap_or(false);
                    if 前面有空白 {
                        format!("data-hs-h=\"{句柄}\" ")
                    } else {
                        format!(" data-hs-h=\"{句柄}\" ")
                    }
                } else {
                    format!(" data-hs-h=\"{句柄}\"")
                };
                let mut 结果 = String::with_capacity(片段.len() + 32);
                结果.push_str(&片段[..插入点]);
                结果.push_str(&属性文本);
                结果.push_str(&片段[插入点..]);
                return 结果;
            }
            _ => {}
        }
    }
    片段.to_string()
}

/// 从标签结束位置往前跳过空白，得到「插属性」的位置。
///
/// 自闭合标签的斜杠由调用方判断：斜杠前的空白已经留下，属性插在空白处、
/// 自带尾空格，就得到 `<img … data-hs-h="7" />` 这种干净形状。
fn 跳过尾部空白(片段: &str, 结束位置: usize) -> usize {
    let 字节 = 片段.as_bytes();
    let mut 位置 = 结束位置;
    while 位置 > 0 {
        let 前一字节 = 字节[位置 - 1];
        if 前一字节 == b' ' || 前一字节 == b'\t' || 前一字节 == b'\n' || 前一字节 == b'\r'
        {
            位置 -= 1;
            continue;
        }
        break;
    }
    位置
}

/// 片段首个标签是否已经带了组件句柄（表格这类组件在自身渲染里挂过）。
///
/// 只看首标签的属性区，不看整段片段：容器片段里必然含子组件的句柄，
/// 拿整段判会把容器自身误判成「已挂过」。
pub(crate) fn 首标签带句柄(片段: &str) -> bool {
    let 起点 = match 片段.find('<') {
        Some(位置) => 位置,
        None => return false,
    };
    let 尾部 = &片段[起点..];
    if 尾部.starts_with("<!--") || 尾部.starts_with("</") {
        return false;
    }
    let 结束 = 尾部.find('>').unwrap_or(尾部.len());
    尾部[..结束].contains("data-hs-h=")
}

#[cfg(test)]
mod 测试 {
    use super::*;

    #[test]
    fn 普通标签插在结束尖括号前() {
        let 结果 = 注入句柄属性("<div class=\"a\">x</div>", 100000);
        assert_eq!(结果, "<div class=\"a\" data-hs-h=\"100000\">x</div>");
    }

    #[test]
    fn 自闭合标签插在斜杠前() {
        let 结果 = 注入句柄属性("<img src=\"a.png\" />", 7);
        assert_eq!(结果, "<img src=\"a.png\" data-hs-h=\"7\" />");
    }

    #[test]
    fn 属性值里带尖括号不误判() {
        let 结果 = 注入句柄属性("<div title=\"a>b\">y</div>", 9);
        assert_eq!(结果, "<div title=\"a>b\" data-hs-h=\"9\">y</div>");
    }

    #[test]
    fn 首标签判据只看首标签() {
        assert!(首标签带句柄(
            "<div data-hs-h=\"1\"><div data-hs-h=\"2\"></div></div>"
        ));
        assert!(!首标签带句柄(
            "<div class=\"a\"><div data-hs-h=\"2\"></div></div>"
        ));
        assert!(!首标签带句柄("纯文字"));
    }

    #[test]
    fn 纯文本与闭标签原样返回() {
        assert_eq!(注入句柄属性("纯文字", 1), "纯文字");
        assert_eq!(注入句柄属性("</div>", 1), "</div>");
    }
}
