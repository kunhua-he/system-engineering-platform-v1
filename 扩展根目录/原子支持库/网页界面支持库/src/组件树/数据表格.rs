//! 数据表格：斑马纹、吸顶表头、单元格内边距都由声明给；外观值走 CSS 变量。

use serde_json::Value;

use crate::业务实现::{取对象文本, 转义网页文本, 拼装表格行};
use crate::编号与码面::错误码;
use crate::组件树::外观属性::{取形态变量, 表格外观映射, 校验颜色值};
use crate::组件树::渲染状态;

/// 拼装一张表格卡片。
pub(crate) fn 拼装表格(节点: &Value, _状态: &mut 渲染状态) -> Result<String, u32> {
    let 列定义 = 节点
        .get("列")
        .and_then(|列项| 列项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 行数据 = 节点
        .get("行")
        .and_then(|行项| 行项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 斑马纹 = 节点
        .get("斑马纹")
        .and_then(|开关项| 开关项.as_bool())
        .unwrap_or(false);
    let 表头固定 = 节点
        .get("表头固定")
        .and_then(|开关项| 开关项.as_bool())
        .unwrap_or(false);
    let 外观变量 = 取形态变量(节点, "表格外观", &表格外观映射)?;
    let mut 容器样式 = 外观变量;
    if 表头固定 {
        let 最大高度 = 节点
            .get("最大高度")
            .and_then(|高度项| 高度项.as_f64())
            .unwrap_or(0.0);
        if !(80.0..=4000.0).contains(&最大高度) {
            return Err(错误码::内容不合法);
        }
        容器样式.push_str(&format!(";max-height:{最大高度}px;overflow:auto"));
    }
    let 斑马色 = 取对象文本(节点, "斑马纹色");
    if !斑马色.is_empty() {
        校验颜色值(&斑马色)?;
        容器样式.push_str(&format!(";--hs-row-alt:{斑马色}"));
    }
    let 容器类 = format!(
        "hs-tree-node hs-card{}{}",
        if 斑马纹 { " is-stripe" } else { "" },
        if 表头固定 { " is-sticky" } else { "" }
    );
    Ok(format!(
        "<div class=\"{}\" style=\"{}\">{}</div>",
        容器类,
        转义网页文本(&容器样式),
        拼装表格行(列定义, 行数据)?
    ))
}
