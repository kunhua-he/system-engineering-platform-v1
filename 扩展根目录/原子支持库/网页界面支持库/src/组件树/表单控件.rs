use serde_json::Value;

use crate::业务实现::{取对象文本, 拼装表单字段, 转义网页文本};
use crate::编号与码面::错误码;
use crate::组件树::外观属性::{
    选中属性文本, 筛选属性与状态,
};
use crate::组件树::{控件样式文本, 拼子节点, 拼通用样式, 渲染状态};

pub(crate) fn 拼装表单容器(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 提交地址文本 = 取对象文本(节点, "提交地址");
    if !提交地址文本.starts_with('/')
        || 提交地址文本.starts_with("//")
        || 提交地址文本.contains("..")
    {
        return Err(错误码::内容不合法);
    }
    let 提交方式文本 = match 取对象文本(节点, "方式").as_str() {
        "" | "POST" => "post",
        "GET" => "get",
        _ => return Err(错误码::内容不合法),
    };
    let 标识文本 = 取对象文本(节点, "标识");
    let 辨识属性 = if 标识文本.is_empty() {
        String::new()
    } else {
        format!(" id=\"{}\"", 转义网页文本(&标识文本))
    };
    let 样式 = 拼通用样式(
        节点,
        "display:flex;flex-direction:column;box-sizing:border-box",
    );Ok(
    format!(
        "<form class=\"hs-tree-node hs-tree-form\"{} method=\"{}\" action=\"{}\" style=\"{}\">{}</form>",
        辨识属性,
        提交方式文本,
        转义网页文本(&提交地址文本),
        转义网页文本(&样式),
        拼子节点(节点, 深度, 状态)?
    ))
}

pub(crate) fn 拼装输入(节点: &Value, _深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 输入类型文本 = match 取对象文本(节点, "种类").as_str() {
        "" | "文本框" => "text",
        "密码框" => "password",
        "数字框" => "number",
        "邮箱" => "email",
        _ => return Err(错误码::内容不合法),
    };
    let 名称文本 = 取对象文本(节点, "名称");
    if 名称文本.is_empty() {
        return Err(错误码::内容不合法);
    }
    let 标签文本 = 取对象文本(节点, "标签");
    let 显示标签文本 = if 标签文本.is_empty() {
        名称文本.clone()
    } else {
        标签文本
    };
    let 必填属性 = if 节点
        .get("必填")
        .and_then(|必填项| 必填项.as_bool())
        .unwrap_or(false)
    {
        " required"
    } else {
        ""
    };
    let 自动填充文本 = 取对象文本(节点, "自动填充");
    let 自动填充属性 = if 自动填充文本.is_empty() {
        String::new()
    } else {
        format!(" autocomplete=\"{}\"", 转义网页文本(&自动填充文本))
    };
    let 输入筛选 = 筛选属性与状态(节点, 状态)?;Ok(
    format!(
        "<div class=\"hs-tree-node hs-form-item\"><label class=\"hs-form-label\">{}</label><input class=\"hs-input\" type=\"{}\" name=\"{}\" placeholder=\"{}\"{}{} style=\"{}\"{} /></div>",
        转义网页文本(&显示标签文本),
        输入类型文本,
        转义网页文本(&名称文本),
        转义网页文本(&取对象文本(节点, "占位文本")),
        必填属性,
        自动填充属性,
        转义网页文本(&控件样式文本(节点)),
        输入筛选
    ))
}

pub(crate) fn 拼装按钮(节点: &Value, _深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 样式类文本 = match 取对象文本(节点, "样式").as_str() {
        "" | "默认" => "hs-button",
        "主要" => "hs-button hs-button-primary",
        "成功" => "hs-button hs-button-success",
        "警告" => "hs-button hs-button-warning",
        "危险" => "hs-button hs-button-danger",
        _ => return Err(错误码::内容不合法),
    };
    let 提交属性 = if 节点
        .get("提交")
        .and_then(|提交项| 提交项.as_bool())
        .unwrap_or(false)
    {
        " type=\"submit\""
    } else {
        " type=\"button\""
    };
    let 表单标识文本 = 取对象文本(节点, "表单");
    let 表单属性 = if 表单标识文本.is_empty() {
        String::new()
    } else {
        format!(" form=\"{}\"", 转义网页文本(&表单标识文本))
    };
    let mut 按钮样式 = 控件样式文本(节点);
    let 按钮选中 = 选中属性文本(节点, &mut 按钮样式, 状态)?;
    let 按钮筛选 = 筛选属性与状态(节点, 状态)?;Ok(
    format!(
        "<button class=\"{}\"{} data-action=\"{}\"{}{} style=\"{}\"{}>{}</button>",
        样式类文本,
        提交属性,
        转义网页文本(&取对象文本(节点, "动作")),
        表单属性,
        按钮选中,
        转义网页文本(&按钮样式),
        按钮筛选,
        转义网页文本(&取对象文本(节点, "文字"))
    ))
}

pub(crate) fn 拼装表单(节点: &Value, _深度: u16, _状态: &mut 渲染状态) -> Result<String, u32> {
    let 字段定义 = 节点
        .get("字段")
        .and_then(|字段项| 字段项.as_array())
        .ok_or(错误码::内容不合法)?;
    let 缺省值 = 节点
        .get("值")
        .cloned()
        .unwrap_or_else(|| Value::Object(serde_json::Map::new()));Ok(
    format!(
        "<div class=\"hs-tree-node hs-card\">{}</div>",
        拼装表单字段(字段定义, &缺省值)?
    ))
}
