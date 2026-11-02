use serde_json::Value;

use crate::业务实现::{取对象文本, 拼装聊天片段, 转义网页文本};
use crate::编号与码面::错误码;
use crate::组件树::外观属性::{
    取形态变量, 气泡外观映射, 选中属性文本, 筛选属性与状态,
};
use crate::组件树::{拼通用样式, 渲染状态};

pub(crate) fn 拼装图标(节点: &Value, _深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 名称文本 = 取对象文本(节点, "名称");
    let 图形文本 = 取对象文本(节点, "图形");
    let 打开地址 = 取对象文本(节点, "打开地址");
    if !打开地址.is_empty()
        && (!打开地址.starts_with('/')
            || 打开地址.starts_with("//")
            || 打开地址.contains("..")
            || 打开地址.contains(':'))
    {
        return Err(错误码::内容不合法);
    }
    let 图形片段 = if 图形文本.starts_with('/') {
        if 图形文本.starts_with("//") || 图形文本.contains("..") || 图形文本.contains(':')
        {
            return Err(错误码::内容不合法);
        }
        if 图形文本.ends_with(".svg") {
            // SVG 走遮罩：图形跟随节点文字颜色，颜色仍由声明决定
            format!(
                "<span class=\"hs-tree-icon-mask\" style=\"-webkit-mask-image:url('{}');mask-image:url('{}')\"></span>",
                转义网页文本(&图形文本),
                转义网页文本(&图形文本)
            )
        } else {
            format!(
                "<img class=\"hs-tree-icon-img\" src=\"{}\" alt=\"\">",
                转义网页文本(&图形文本)
            )
        }
    } else {
        format!(
            "<span class=\"hs-tree-icon-glyph\">{}</span>",
            转义网页文本(&图形文本)
        )
    };
    let 名称片段 = if 节点
        .get("显示名称")
        .and_then(|显示项| 显示项.as_bool())
        .unwrap_or(true)
    {
        let mut 标签样式 = String::new();
        if let Some(颜色) = 节点
            .get("标签颜色")
            .and_then(|取值项| 取值项.as_str())
        {
            标签样式.push_str(&format!("color:{颜色};"));
        }
        if let Some(字号) = 节点.get("标签字号").and_then(|取值项| 取值项.as_f64())
        {
            标签样式.push_str(&format!("font-size:{字号}px;"));
        }
        if 标签样式.is_empty() {
            format!(
                "<span class=\"hs-tree-icon-label\">{}</span>",
                转义网页文本(&名称文本)
            )
        } else {
            format!(
                "<span class=\"hs-tree-icon-label\" style=\"{}\">{}</span>",
                转义网页文本(&标签样式),
                转义网页文本(&名称文本)
            )
        }
    } else {
        String::new()
    };
    let 可选中 = 节点
        .get("可选中")
        .and_then(|开关项| 开关项.as_bool())
        .unwrap_or(false);
    let mut 样式 = 拼通用样式(
        节点,
        "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;text-decoration:none;padding:6px 4px",
    );
    let mut 选中属性 = String::new();
    if 可选中 {
        选中属性 = 选中属性文本(节点, &mut 样式, 状态)?;
    }
    let 图标筛选 = 筛选属性与状态(节点, 状态)?;Ok(
    if 打开地址.is_empty() {
        format!(
            "<div class=\"hs-tree-node hs-tree-icon\" style=\"{}\"{}{}>{}{}</div>",
            转义网页文本(&样式),
            选中属性,
            图标筛选,
            图形片段,
            名称片段
        )
    } else {
        format!(
            "<a class=\"hs-tree-node hs-tree-icon\" href=\"{}\" title=\"{}\" style=\"{}\">{}{}</a>",
            转义网页文本(&打开地址),
            转义网页文本(&名称文本),
            转义网页文本(&样式),
            图形片段,
            名称片段
        )
    })
}

pub(crate) fn 拼装文字(节点: &Value, _深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let mut 样式 = 拼通用样式(节点, "white-space:pre-wrap;word-break:break-word");
    let 文字选中 = 选中属性文本(节点, &mut 样式, 状态)?;
    let 文本内容 = 转义网页文本(&取对象文本(节点, "文本"));
    let 打开地址 = 取对象文本(节点, "打开地址");
    if !打开地址.is_empty()
        && (!打开地址.starts_with('/')
            || 打开地址.starts_with("//")
            || 打开地址.contains("..")
            || 打开地址.contains(':'))
    {
        return Err(错误码::内容不合法);
    }
    Ok(if 打开地址.is_empty() {
        format!(
            "<div class=\"hs-tree-node hs-tree-text\" style=\"{}\"{}>{}</div>",
            转义网页文本(&样式),
            文字选中,
            文本内容
        )
    } else {
        format!(
            "<a class=\"hs-tree-node hs-tree-text hs-tree-link\" href=\"{}\" style=\"{}\"{}>{}</a>",
            转义网页文本(&打开地址),
            转义网页文本(&样式),
            文字选中,
            文本内容
        )
    })
}

pub(crate) fn 拼装分隔条(节点: &Value, _深度: u16, _状态: &mut 渲染状态) -> Result<String, u32> {
    let 样式 = 拼通用样式(节点, "");Ok(
    format!(
        "<div class=\"hs-tree-node hs-tree-divider\" style=\"{}\"></div>",
        转义网页文本(&样式)
    ))
}

pub(crate) fn 拼装聊天流(节点: &Value, _深度: u16, _状态: &mut 渲染状态) -> Result<String, u32> {
    let 消息表 = match 节点.get("消息").and_then(|消息项| 消息项.as_array()) {
        Some(消息项) => 消息项.clone(),
        None => Vec::new(),
    };
    let 空态文本 = 取对象文本(节点, "空态文案");
    let 气泡变量 = 取形态变量(节点, "气泡外观", &气泡外观映射)?;Ok(
    format!(
        "<div class=\"hs-tree-node\" style=\"{}\">{}</div>",
        转义网页文本(&气泡变量),
        拼装聊天片段(&消息表, &空态文本)?
    ))
}

pub(crate) fn 拼装原样(节点: &Value, _深度: u16, _状态: &mut 渲染状态) -> Result<String, u32> {
    let 片段文本 = 取对象文本(节点, "html");
    if 片段文本.len() > 200_000 {
        return Err(错误码::资源受限);
    }
    Ok(片段文本)
}

pub(crate) fn 拼装标题(节点: &Value, _深度: u16, _状态: &mut 渲染状态) -> Result<String, u32> {
    Ok(format!(
        "<h2 class=\"hs-tree-node hs-tree-title\">{}</h2>",
        转义网页文本(&取对象文本(节点, "文本"))
    ))
}
