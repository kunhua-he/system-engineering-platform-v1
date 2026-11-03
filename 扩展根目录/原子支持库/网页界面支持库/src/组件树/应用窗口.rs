//! 应用窗口：窗口容器把应用内容装进桌面同一棵组件树。
//!
//! 外观与行为全部由声明给：标题栏高度/底色/文字色、三个按钮的可见性/直径/颜色/位置/间距、可移动。
//! 底座不认识「macOS」「V3」这类产品语义，只认字段名与取值范围。

use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本};
use crate::组件树::{拼子节点, 拼通用样式, 渲染状态};
use crate::编号与码面::错误码;

use super::外观属性::{合法标识, 校验颜色值};

/// 三键定义：(开关, 类名后缀, 数据属性, 符号形态的图形, 读屏说明, 圆点颜色字段)。
type 按钮定义项 = (
    bool,
    &'static str,
    &'static str,
    &'static str,
    &'static str,
    &'static str,
);

/// 拼装一扇窗口：标题栏（按钮 + 标题）+ 正文。
pub(crate) fn 拼装窗口(
    节点: &Value, 深度: u16, 状态: &mut 渲染状态
) -> Result<String, u32> {
    let 标识文本 = 取对象文本(节点, "标识");
    if !合法标识(&标识文本) {
        return Err(错误码::内容不合法);
    }
    let 标题文本 = 取对象文本(节点, "标题");
    let 初始隐藏 = 节点
        .get("初始隐藏")
        .and_then(|隐藏项| 隐藏项.as_bool())
        .unwrap_or(true);

    let mut 标题栏样式 = String::from("height:38px");
    if let Some(Value::Number(栏高)) = 节点.get("标题栏高") {
        let 栏高值 = 栏高.as_f64().unwrap_or(0.0);
        if !(24.0..=64.0).contains(&栏高值) {
            return Err(错误码::内容不合法);
        }
        标题栏样式 = format!("height:{栏高值}px");
    }
    for (字段名, 样式属性) in [("标题栏背景", "background"), ("标题栏文字颜色", "color")]
    {
        let 取值 = 取对象文本(节点, 字段名);
        if 取值.is_empty() {
            continue;
        }
        校验颜色值(&取值)?;
        标题栏样式.push_str(&format!(";{样式属性}:{取值}"));
    }

    // 行为开关：缺省只留关闭、窗口可拖
    let 取开关 = |字段名: &str, 缺省值: bool| {
        节点
            .get(字段名)
            .and_then(|开关项| 开关项.as_bool())
            .unwrap_or(缺省值)
    };
    let 可关闭 = 取开关("可关闭", true);
    let 可最小化 = 取开关("可最小化", false);
    let 可最大化 = 取开关("可最大化", false);
    let 可移动 = 取开关("可移动", true);

    // 圆点形态：给了按钮直径就按圆点渲染，颜色来自声明；否则退回符号形态
    let 按钮直径 = match 节点.get("按钮直径").and_then(|直径项| 直径项.as_f64()) {
        Some(直径值) => {
            if !(6.0..=24.0).contains(&直径值) {
                return Err(错误码::内容不合法);
            }
            Some(直径值)
        }
        None => None,
    };
    // 按钮位置：起点＝窗口左上（macOS 惯例），终点＝右上
    let 按钮在起点 = match 取对象文本(节点, "按钮位置").as_str() {
        "" | "终点" => false,
        "起点" => true,
        _ => return Err(错误码::内容不合法),
    };
    let 按钮间距 = match 节点.get("按钮间距").and_then(|间距项| 间距项.as_f64()) {
        Some(间距值) => {
            if !(0.0..=32.0).contains(&间距值) {
                return Err(错误码::内容不合法);
            }
            间距值
        }
        None => 8.0,
    };
    let 按钮边框颜色 = 取对象文本(节点, "按钮边框颜色");
    if !按钮边框颜色.is_empty() {
        校验颜色值(&按钮边框颜色)?;
    }
    let 标题字重 = match 节点.get("标题字重").and_then(|字重项| 字重项.as_f64()) {
        Some(字重值) => {
            if !(100.0..=900.0).contains(&字重值) {
                return Err(错误码::内容不合法);
            }
            Some(字重值)
        }
        None => None,
    };

    // 数组按 macOS 顺序写（关闭、最小化、最大化）；放在右端时按 DOM 顺序倒过来，视觉仍是 最小化/最大化/关闭
    let 全部按钮: [按钮定义项; 3] = [
        (可关闭, "close", "data-窗口-close", "✕", "关闭", "关闭颜色"),
        (
            可最小化,
            "min",
            "data-窗口最小化",
            "—",
            "最小化",
            "最小化颜色",
        ),
        (
            可最大化,
            "max",
            "data-窗口最大化",
            "▢",
            "最大化",
            "最大化颜色",
        ),
    ];
    let 按钮序列: Vec<按钮定义项> = if 按钮在起点 {
        全部按钮.to_vec()
    } else {
        全部按钮.iter().rev().copied().collect()
    };
    let mut 按钮片段 = String::new();
    for (开关, 类名后缀, 数据属性, 符号, 说明, 颜色字段) in 按钮序列 {
        if !开关 {
            continue;
        }
        let 按钮样式 = match 按钮直径 {
            Some(直径值) => {
                let 颜色文本 = 取对象文本(节点, 颜色字段);
                let mut 样式 = format!(
                    "width:{直径值}px;height:{直径值}px;border-radius:50%;padding:0;flex:none;box-sizing:border-box"
                );
                if !颜色文本.is_empty() {
                    校验颜色值(&颜色文本)?;
                    样式.push_str(&format!(
                        ";--hs-wc:{颜色文本};background:var(--hs-wc,transparent)"
                    ));
                }
                if !按钮边框颜色.is_empty() {
                    样式.push_str(&format!(";border:0.5px solid {按钮边框颜色}"));
                }
                样式
            }
            None => String::new(),
        };
        let 内容片段 = if 按钮直径.is_some() {
            String::new()
        } else {
            format!("<span aria-hidden=\"true\">{符号}</span>")
        };
        按钮片段.push_str(&format!(
            "<button class=\"hs-tree-window-{类名后缀}\" type=\"button\" {数据属性}=\"{}\" style=\"{}\" aria-label=\"{说明}\">{内容片段}</button>",
            转义网页文本(&标识文本),
            转义网页文本(&按钮样式),
        ));
    }

    let 标题样式 = match 标题字重 {
        Some(字重值) => format!(" style=\"font-weight:{}\"", 字重值 as u32),
        None => String::new(),
    };
    let 标题片段 = format!(
        "<span class=\"hs-tree-window-title\"{标题样式}>{}</span>",
        转义网页文本(&标题文本)
    );
    let (栏首片段, 栏尾片段) = if 按钮在起点 {
        (按钮片段, 标题片段)
    } else {
        (标题片段, 按钮片段)
    };
    标题栏样式.push_str(&format!(";gap:{按钮间距}px"));
    let 栏修饰类 = if 按钮在起点 { " 标题居中" } else { "" };

    let 样式 = 拼通用样式(
        节点,
        "position:relative;display:flex;flex-direction:column;overflow:hidden;width:100%;height:100%",
    );
    状态.需要窗口脚本 = true;
    // 窗口状态（位置/尺寸/开合）摆到 data-* 上：底座只报初值，存与取都归调用方
    let 初值 = serde_json::json!({
        "左": 节点.get("左").cloned().unwrap_or(Value::Null),
        "上": 节点.get("上").cloned().unwrap_or(Value::Null),
        "宽": 节点.get("宽").cloned().unwrap_or(Value::Null),
        "高": 节点.get("高").cloned().unwrap_or(Value::Null),
        "开合": !初始隐藏,
    });
    Ok(format!(
        "<div class=\"hs-tree-node hs-tree-window{}\" data-窗口=\"{}\" data-可拖动=\"{}\" data-窗口状态=\"{}\" style=\"{}\"><div class=\"hs-tree-window-bar{}\" style=\"{}\">{}{}</div><div class=\"hs-tree-window-body\">{}</div></div>",
        if 初始隐藏 { " 已隐藏" } else { "" },
        转义网页文本(&标识文本),
        if 可移动 { "1" } else { "0" },
        转义网页文本(&初值.to_string()),
        转义网页文本(&样式),
        栏修饰类,
        转义网页文本(&标题栏样式),
        栏首片段,
        栏尾片段,
        拼子节点(节点, 深度, 状态)?
    ))
}
