//! 外观属性：组件树节点的观感值（字号、字重、行高、字距、模糊、阴影、裁剪行数、层级）。
//!
//! 这些是"从底座搬出来的 V3 观感"的落点：底座只认字段名与取值范围，具体数值由调用方在声明里给。
//! 类型或范围不对一律明确失败，不静默忽略、不截断。

use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本};
use crate::编号与码面::错误码;

/// 尺寸类字段：数字当像素，字符串原样（"100%"、"auto"）。
pub(crate) fn 取尺寸(节点: &Value, 字段名: &str) -> String {
    match 节点.get(字段名) {
        Some(Value::Number(数值)) => format!("{数值}px"),
        Some(Value::String(文本)) => 文本.clone(),
        _ => String::new(),
    }
}

/// 对齐词：居中 / 起点 / 终点 / 两端。
pub(crate) fn 取对齐(节点: &Value, 字段名: &str) -> &'static str {
    match 取对象文本(节点, 字段名).as_str() {
        "居中" => "center",
        "终点" => "flex-end",
        "两端" => "space-between",
        _ => "flex-start",
    }
}

/// 标识合法性：字母、数字、`-`、`_` 与汉字，长度不超过 32（标识只作为 data-* 的值，输出仍转义）。
pub(crate) fn 合法标识(文本: &str) -> bool {
    !文本.is_empty()
        && 文本.chars().count() <= 32
        && 文本.chars().all(|字符| {
            字符.is_ascii_alphanumeric()
                || 字符 == '-'
                || 字符 == '_'
                || ('\u{4e00}'..='\u{9fff}').contains(&字符)
        })
}

/// 颜色值：#RGB / #RRGGBB / #RRGGBBAA，其他一律拒绝，避免把任意样式当颜色注入。
pub(crate) fn 校验颜色值(颜色文本: &str) -> Result<(), u32> {
    let 形状相符 = matches!(颜色文本.len(), 4 | 7 | 9)
        && 颜色文本.starts_with('#')
        && 颜色文本[1..].chars().all(|字符| 字符.is_ascii_hexdigit());
    if 形状相符 {
        Ok(())
    } else {
        Err(错误码::内容不合法)
    }
}

/// 颜色字段校验：背景（纯色写字符串 / 渐变写对象 / 图片写同源路径）、文字颜色、边框颜色。
pub(crate) fn 校验节点颜色(节点: &Value) -> Result<(), u32> {
    for 颜色字段 in ["文字颜色", "边框颜色"] {
        let 颜色文本 = 取对象文本(节点, 颜色字段);
        if !颜色文本.is_empty() {
            校验颜色值(&颜色文本)?;
        }
    }
    match 节点.get("背景") {
        None | Some(Value::Null) => Ok(()),
        Some(Value::String(纯色)) => 校验颜色值(纯色),
        Some(Value::Object(背景表)) => {
            let 背景值 = Value::Object(背景表.clone());
            match 取对象文本(&背景值, "类型").as_str() {
                "线性渐变" => {
                    let 角度越界 = 背景值
                        .get("角度")
                        .and_then(|角度项| 角度项.as_f64())
                        .map(|角度数值| !(-360.0..=360.0).contains(&角度数值))
                        .unwrap_or(false);
                    if 角度越界 {
                        return Err(错误码::内容不合法);
                    }
                    let 颜色节点 = 背景值
                        .get("颜色节点")
                        .and_then(|节点项| 节点项.as_array())
                        .ok_or(错误码::内容不合法)?;
                    if !(2..=16).contains(&颜色节点.len()) {
                        return Err(错误码::内容不合法);
                    }
                    let mut 上次位置 = -1.0_f64;
                    for 颜色项 in 颜色节点 {
                        let 颜色文本 = 颜色项
                            .get("颜色")
                            .and_then(|颜色项| 颜色项.as_str())
                            .ok_or(错误码::内容不合法)?;
                        校验颜色值(颜色文本)?;
                        let 位置数值 = 颜色项
                            .get("位置")
                            .and_then(|位置项| 位置项.as_f64())
                            .ok_or(错误码::内容不合法)?;
                        if !(0.0..=100.0).contains(&位置数值) || 位置数值 < 上次位置 {
                            return Err(错误码::内容不合法);
                        }
                        上次位置 = 位置数值;
                    }
                    Ok(())
                }
                "图片" => {
                    let 资源文本 = 取对象文本(&背景值, "资源");
                    if !资源文本.starts_with('/')
                        || 资源文本.starts_with("//")
                        || 资源文本.contains("..")
                        || 资源文本.contains(':')
                    {
                        return Err(错误码::内容不合法);
                    }
                    Ok(())
                }
                _ => Err(错误码::内容不合法),
            }
        }
        _ => Err(错误码::内容不合法),
    }
}

/// 背景样式：调用前必须已过 `校验背景`。
pub(crate) fn 背景样式文本(节点: &Value) -> String {
    match 节点.get("背景") {
        Some(Value::String(纯色)) => format!(";background:{纯色}"),
        Some(Value::Object(背景表)) => {
            let 背景值 = Value::Object(背景表.clone());
            if 取对象文本(&背景值, "类型") == "图片" {
                return format!(
                    ";background-image:url(\"{}\");background-size:cover;background-position:center",
                    转义网页文本(&取对象文本(&背景值, "资源"))
                );
            }
            let 角度 = 背景值
                .get("角度")
                .and_then(|角度项| 角度项.as_f64())
                .unwrap_or(135.0);
            let mut 节点文本 = String::new();
            for 颜色项 in 背景值
                .get("颜色节点")
                .and_then(|节点项| 节点项.as_array())
                .map(|节点表| 节点表.as_slice())
                .unwrap_or(&[])
            {
                if !节点文本.is_empty() {
                    节点文本.push(',');
                }
                节点文本.push_str(&format!(
                    "{} {}%",
                    取对象文本(颜色项, "颜色"),
                    颜色项
                        .get("位置")
                        .and_then(|位置项| 位置项.as_f64())
                        .unwrap_or(0.0)
                ));
            }
            format!(";background:linear-gradient({角度}deg,{节点文本})")
        }
        _ => String::new(),
    }
}

/// 字号取值：`字体大小` 与 `字号` 是同一含义的两个名字，互为回退。
///
/// 收敛口径（2026-11-02 组件收敛裁决）：同一份声明写哪个都生效，值域统一 1 至 200。
pub(crate) fn 字号取值(节点: &Value) -> Option<f64> {
    节点
        .get("字体大小")
        .and_then(|项| 项.as_f64())
        .or_else(|| 节点.get("字号").and_then(|项| 项.as_f64()))
}

/// 外观属性白名单：数值字段（字段名，最小，最大）。
const 数值外观字段: [(&str, f64, f64); 8] = [
    ("字体大小", 1.0, 200.0),
    ("字重", 100.0, 900.0),
    ("行高", 0.8, 3.0),
    ("字距", -5.0, 20.0),
    ("模糊", 0.0, 80.0),
    ("裁剪行数", 1.0, 6.0),
    ("层", 0.0, 200.0),
    ("饱和", 50.0, 300.0),
];

/// 外观属性白名单：枚举字段（字段名，允许取值）。
const 枚举外观字段: [(&str, &[&str]); 2] = [
    ("阴影", &["无", "轻", "中", "重", "浮层", "窗口"]),
    ("文字阴影", &["无", "轻", "中"]),
];

/// 校验外观属性：类型或范围不对一律明确失败，不静默忽略、不截断。
pub(crate) fn 校验外观属性(节点: &Value) -> Result<(), u32> {
    for (字段名, 最小值, 最大值) in 数值外观字段 {
        if let Some(取值项) = 节点.get(字段名) {
            let 数值 = 取值项.as_f64().ok_or(错误码::内容不合法)?;
            if !(最小值..=最大值).contains(&数值) {
                return Err(错误码::内容不合法);
            }
        }
    }
    for 字号字段 in ["字体大小", "字号"] {
        if let Some(取值项) = 节点.get(字号字段) {
            let 数值 = 取值项.as_f64().ok_or(错误码::内容不合法)?;
            if !(1.0..=200.0).contains(&数值) {
                return Err(错误码::内容不合法);
            }
        }
    }
    if let Some(取值项) = 节点.get("标签字号") {
        let 数值 = 取值项.as_f64().ok_or(错误码::内容不合法)?;
        if !(8.0..=48.0).contains(&数值) {
            return Err(错误码::内容不合法);
        }
    }
    if let Some(取值项) = 节点.get("标签颜色") {
        let 文本 = 取值项.as_str().ok_or(错误码::内容不合法)?;
        校验颜色值(文本)?;
    }
    for (字段名, 允许值) in 枚举外观字段.iter() {
        if let Some(取值项) = 节点.get(字段名) {
            let 文本 = 取值项.as_str().ok_or(错误码::内容不合法)?;
            if !允许值.contains(&文本) {
                return Err(错误码::内容不合法);
            }
        }
    }
    Ok(())
}

/// 阴影档位 → CSS（中性灰，不含任何产品观感）。
pub(crate) fn 阴影样式文本(档位: &str) -> &'static str {
    match 档位 {
        "轻" => "0 1px 3px rgba(0,0,0,.06)",
        "中" => "0 4px 12px rgba(0,0,0,.08)",
        "重" => "0 8px 24px rgba(0,0,0,.12)",
        "浮层" => "0 16px 40px rgba(0,0,0,.24),0 0 0 .5px rgba(0,0,0,.08)",
        "窗口" => {
            "0 28px 80px rgba(0,0,0,.36),0 8px 24px rgba(0,0,0,.18),0 0 0 .5px rgba(0,0,0,.2)"
        }
        _ => "",
    }
}

/// 文字阴影档位 → CSS。
pub(crate) fn 文字阴影样式文本(档位: &str) -> &'static str {
    match 档位 {
        "轻" => "0 1px 2px rgba(0,0,0,.28)",
        "中" => "0 1px 3px rgba(0,0,0,.5)",
        _ => "",
    }
}

/// 把校验过的外观属性拼进内联样式。
pub(crate) fn 拼外观样式(节点: &Value) -> String {
    let mut 样式 = String::new();
    if let Some(字号) = 字号取值(节点) {
        样式.push_str(&format!(";font-size:{字号}px"));
    }
    for (字段名, 单位) in [("字重", ""), ("行高", ""), ("字距", "px"), ("层", "")] {
        if let Some(数值) = 节点.get(字段名).and_then(|取值项| 取值项.as_f64()) {
            let 属性名 = match 字段名 {
                "字重" => "font-weight",
                "行高" => "line-height",
                "字距" => "letter-spacing",
                _ => "z-index",
            };
            样式.push_str(&format!(";{属性名}:{数值}{单位}"));
        }
    }
    // 模糊与饱和合成一条 backdrop-filter：只看模糊、只看饱和、两样都给都能成立
    let 模糊值 = 节点
        .get("模糊")
        .and_then(|取值项| 取值项.as_f64())
        .unwrap_or(0.0);
    let 饱和值 = 节点
        .get("饱和")
        .and_then(|取值项| 取值项.as_f64())
        .unwrap_or(0.0);
    if 模糊值 > 0.0 || 饱和值 > 0.0 {
        let mut 滤镜 = String::new();
        if 模糊值 > 0.0 {
            滤镜.push_str(&format!("blur({模糊值}px)"));
        }
        if 饱和值 > 0.0 {
            if !滤镜.is_empty() {
                滤镜.push(' ');
            }
            滤镜.push_str(&format!("saturate({}%)", 饱和值.round() as u32));
        }
        样式.push_str(&format!(
            ";-webkit-backdrop-filter:{滤镜};backdrop-filter:{滤镜}"
        ));
    }
    if let Some(数值) = 节点.get("裁剪行数").and_then(|取值项| 取值项.as_f64()) {
        样式.push_str(&format!(";--hs-clamp:{}", 数值.round() as u32));
    }
    if let Some(档位) = 节点.get("阴影").and_then(|取值项| 取值项.as_str()) {
        let 阴影 = 阴影样式文本(档位);
        if !阴影.is_empty() {
            样式.push_str(&format!(";box-shadow:{阴影}"));
        }
    }
    if let Some(档位) = 节点.get("文字阴影").and_then(|取值项| 取值项.as_str()) {
        let 文字阴影 = 文字阴影样式文本(档位);
        if !文字阴影.is_empty() {
            样式.push_str(&format!(";text-shadow:{文字阴影}"));
        }
    }
    样式
}

/// 形态变量的取值类型：颜色必须十六进制，像素是数字，间距是 1–4 段带单位的值。
pub(crate) enum 变量类型 {
    颜色,
    像素,
    间距,
}

/// 间距值合法性：`8px`、`10px 12px`、`0 12px`，最多四段，只认数字 + px/%/em。
pub(super) fn 间距合法(文本: &str) -> bool {
    if 文本.is_empty() || 文本.chars().count() > 40 {
        return false;
    }
    let 段表: Vec<&str> = 文本.split(' ').collect();
    if 段表.len() > 4 {
        return false;
    }
    段表.iter().all(|段| {
        let 去单位 = 段
            .trim_end_matches("px")
            .trim_end_matches('%')
            .trim_end_matches("em")
            .trim_end_matches("rem");
        !去单位.is_empty()
            && 去单位
                .chars()
                .all(|字符| 字符.is_ascii_digit() || 字符 == '.')
    })
}

/// 形态变量：把声明里的外观对象翻成容器上的 CSS 变量。
///
/// 中性样式里用 `var(变量名, 缺省值)` 兜底 —— 底座不知道这些值是给谁的观感，
/// 只负责校验形状并把值挂上去；不写就是缺省，声明里不为默认值付字节。
pub(crate) fn 取形态变量(
    节点: &Value,
    字段名: &str,
    映射表: &[(&str, &str, 变量类型)],
) -> Result<String, u32> {
    let 外观表 = match 节点.get(字段名) {
        None | Some(Value::Null) => return Ok(String::new()),
        Some(Value::Object(表)) => 表.clone(),
        _ => return Err(错误码::内容不合法),
    };
    let 外观值 = Value::Object(外观表);
    let mut 样式 = String::new();
    for (键名, 变量名, 类型) in 映射表 {
        let 原始 = 取对象文本(&外观值, 键名);
        if 原始.is_empty() {
            continue;
        }
        match 类型 {
            变量类型::颜色 => {
                校验颜色值(&原始)?;
                样式.push_str(&format!(";{变量名}:{原始}"));
            }
            变量类型::像素 => {
                let 数值 = 外观值
                    .get(*键名)
                    .and_then(|取值项| 取值项.as_f64())
                    .ok_or(错误码::内容不合法)?;
                if !(0.0..=200.0).contains(&数值) {
                    return Err(错误码::内容不合法);
                }
                样式.push_str(&format!(";{变量名}:{数值}px"));
            }
            变量类型::间距 => {
                if !间距合法(&原始) {
                    return Err(错误码::内容不合法);
                }
                样式.push_str(&format!(";{变量名}:{原始}"));
            }
        }
    }
    Ok(样式)
}

/// 表格外观字段 → 容器变量。
pub(crate) const 表格外观映射: [(&str, &str, 变量类型); 8] = [
    ("表头背景", "--hs-th-bg", 变量类型::颜色),
    ("表头文字颜色", "--hs-th-ink", 变量类型::颜色),
    ("单元格文字颜色", "--hs-td-ink", 变量类型::颜色),
    ("单元格背景", "--hs-td-bg", 变量类型::颜色),
    ("边框颜色", "--hs-td-line", 变量类型::颜色),
    ("行悬停背景", "--hs-row-hover", 变量类型::颜色),
    ("字号", "--hs-table-font", 变量类型::像素),
    ("单元格内边距", "--hs-cell-pad", 变量类型::间距),
];

/// 菜单外观字段 → 侧栏变量。
pub(crate) const 菜单外观映射: [(&str, &str, 变量类型); 7] = [
    ("栏底色", "--hs-menu-panel", 变量类型::颜色),
    ("项文字颜色", "--hs-menu-ink", 变量类型::颜色),
    ("激活背景", "--hs-menu-active-bg", 变量类型::颜色),
    ("激活文字颜色", "--hs-menu-active-ink", 变量类型::颜色),
    ("项字号", "--hs-menu-font", 变量类型::像素),
    ("项圆角", "--hs-menu-radius", 变量类型::像素),
    ("项内边距", "--hs-menu-pad", 变量类型::间距),
];

/// 气泡外观字段 → 聊天流变量。
pub(crate) const 气泡外观映射: [(&str, &str, 变量类型); 6] = [
    ("气泡背景", "--hs-chat-bg", 变量类型::颜色),
    ("用户气泡背景", "--hs-chat-user-bg", 变量类型::颜色),
    ("气泡文字颜色", "--hs-chat-ink", 变量类型::颜色),
    ("用户气泡文字颜色", "--hs-chat-user-ink", 变量类型::颜色),
    ("气泡圆角", "--hs-chat-radius", 变量类型::像素),
    ("字号", "--hs-chat-font", 变量类型::像素),
];

/// 可选中节点的公共属性：给了 `可选中` 才出 data-select，同片区由选中脚本保证单选。
pub(crate) fn 选中属性文本(
    节点: &Value,
    样式: &mut String,
    状态: &mut crate::组件树::渲染状态,
) -> Result<String, u32> {
    let 可选中 = 节点
        .get("可选中")
        .and_then(|开关项| 开关项.as_bool())
        .unwrap_or(false);
    if !可选中 {
        return Ok(String::new());
    }
    for (字段名, 变量名) in [
        ("选中背景", "--hs-sel-bg"),
        ("选中描边", "--hs-sel-line"),
        ("选中文字颜色", "--hs-sel-ink"),
    ] {
        let 取值 = 取对象文本(节点, 字段名);
        if 取值.is_empty() {
            continue;
        }
        校验颜色值(&取值)?;
        样式.push_str(&format!(";{变量名}:{取值}"));
    }
    状态.需要选中脚本 = true;
    Ok(" data-select=\"1\"".to_string())
}

/// 放大容器属性：`放大` 对象里的峰值与半径决定悬停放大曲线，脚本按它算邻域衰减。
pub(crate) fn 放大属性文本(
    节点: &Value,
    状态: &mut crate::组件树::渲染状态,
) -> Result<String, u32> {
    let 放大表 = match 节点.get("放大") {
        None | Some(Value::Null) => return Ok(String::new()),
        Some(Value::Object(表)) => 表.clone(),
        _ => return Err(错误码::内容不合法),
    };
    let 放大值 = Value::Object(放大表);
    let 峰值 = 放大值
        .get("峰值")
        .and_then(|取值项| 取值项.as_f64())
        .unwrap_or(1.0);
    if !(1.0..=2.5).contains(&峰值) {
        return Err(错误码::内容不合法);
    }
    let 半径 = 放大值
        .get("半径")
        .and_then(|取值项| 取值项.as_f64())
        .unwrap_or(120.0);
    if !(20.0..=400.0).contains(&半径) {
        return Err(错误码::内容不合法);
    }
    状态.需要放大脚本 = true;
    Ok(format!(" data-magnify=\"{峰值},{半径}\""))
}

/// 筛选属性：`筛选值` 让节点可被筛；`筛选目标`（输入）与 `筛选分类`（按钮）指向被筛容器。
pub(crate) fn 筛选属性文本(节点: &Value) -> Result<String, u32> {
    for (字段名, 属性名) in [
        ("筛选区", "data-filter-scope"),
        ("筛选值", "data-filter-value"),
        ("筛选目标", "data-filter-target"),
        ("筛选分类", "data-filter-cat"),
    ] {
        let 取值 = 取对象文本(节点, 字段名);
        if 取值.is_empty() {
            continue;
        }
        if 取值.chars().count() > 64 || 取值.contains('"') || 取值.contains('<') {
            return Err(错误码::内容不合法);
        }
        return Ok(format!(" {属性名}=\"{}\"", 取值));
    }
    Ok(String::new())
}

/// 筛选属性 + 状态位：给了筛选相关字段才需要筛选脚本。
pub(crate) fn 筛选属性与状态(
    节点: &Value,
    状态: &mut crate::组件树::渲染状态,
) -> Result<String, u32> {
    let 属性 = 筛选属性文本(节点)?;
    if !属性.is_empty() {
        状态.需要筛选脚本 = true;
    }
    Ok(属性)
}

/// 容器属性：放大与筛选都写在容器上，两者可同时生效。
pub(crate) fn 容器属性文本(
    节点: &Value,
    状态: &mut crate::组件树::渲染状态,
) -> Result<String, u32> {
    let mut 属性 = 放大属性文本(节点, 状态)?;
    属性.push_str(&筛选属性与状态(节点, 状态)?);
    Ok(属性)
}
