//! 组件树：窗口内容与整页都由一棵可递归嵌套的节点树描述。
//!
//! 容器（行 / 列 / 网格 / 侧栏 / 分区 / 画布）可以无限嵌套，叶子出真正的界面元素。
//! 产品语义上不限制嵌套层数；工程上拦两道闸（深度 32 层、节点 2000 个），
//! 只防「写错了的树把渲染拖死」，正常界面远远用不到。

use serde_json::Value;

use crate::业务实现::{取对象文本, 拼装整页外壳, 转义网页文本};
use crate::交互运行时::{显隐切换脚本, 放大脚本, 筛选脚本, 选中脚本, 窗口脚本};
use crate::编号与码面::错误码;
use crate::视觉基准::中性样式文本;
use 数据表格::拼装表格;

#[path = "组件树/外观属性.rs"]
mod 外观属性;
#[path = "组件树/应用窗口.rs"]
mod 应用窗口;
#[path = "组件树/数据表格.rs"]
mod 数据表格;

pub(crate) use 外观属性::控件样式文本;
#[path = "组件树/容器.rs"]
mod 容器;
#[path = "组件树/叶面.rs"]
mod 叶面;
#[path = "组件树/表单控件.rs"]
mod 表单控件;

use 外观属性::{
    取尺寸, 合法标识, 校验节点颜色, 背景样式文本, 校验外观属性, 拼外观样式, };


pub(crate) const 树最大深度: u16 = 32;
pub(crate) const 树最大节点数: usize = 2000;

/// 渲染过程中的累积状态：节点计数 + 是否需要附通用显隐脚本。
pub(crate) struct 渲染状态 {
    pub(crate) 计数: usize,
    pub(crate) 需要显隐脚本: bool,
    pub(crate) 需要窗口脚本: bool,
    pub(crate) 需要选中脚本: bool,
    pub(crate) 需要放大脚本: bool,
    pub(crate) 需要筛选脚本: bool,
}


/// 控件自身尺寸与描边：宽 / 高 / 圆角 / 边框颜色 / 背景色。

/// 通用样式：所有节点都能带，拼成 style 属性值。
pub(crate) fn 拼通用样式(节点: &Value, 基础: &str) -> String {
    let mut 样式 = String::from(基础);
    let 宽 = 取尺寸(节点, "宽");
    let 高 = 取尺寸(节点, "高");
    if !宽.is_empty() {
        样式.push_str(&format!(";width:{宽}"));
    }
    if !高.is_empty() {
        样式.push_str(&format!(";height:{高}"));
    }
    if let Some(Value::Number(数值)) = 节点.get("间距") {
        样式.push_str(&format!(";gap:{数值}px"));
    }
    let 内边距 = 取尺寸(节点, "内边距");
    if !内边距.is_empty() {
        样式.push_str(&format!(";padding:{内边距}"));
    }
    样式.push_str(&背景样式文本(节点));
    let 文字颜色 = 取对象文本(节点, "文字颜色");
    if !文字颜色.is_empty() {
        样式.push_str(&format!(";color:{文字颜色}"));
    }
    let 边框颜色 = 取对象文本(节点, "边框颜色");
    if !边框颜色.is_empty() {
        样式.push_str(&format!(";border-color:{边框颜色}"));
    }
    let 圆角 = 取尺寸(节点, "圆角");
    if !圆角.is_empty() {
        样式.push_str(&format!(";border-radius:{圆角}"));
    }
    let 边框 = 取对象文本(节点, "边框");
    if !边框.is_empty() {
        样式.push_str(&format!(";border:{边框}"));
    }
    let 溢出 = 取对象文本(节点, "溢出");
    if !溢出.is_empty() {
        样式.push_str(&format!(";overflow:{溢出}"));
    }
    let 最小高 = 取尺寸(节点, "最小高");
    if !最小高.is_empty() {
        样式.push_str(&format!(";min-height:{最小高}"));
    }
    样式.push_str(&拼外观样式(节点));
    样式
}

/// 递归出口：子节点表
pub(crate) fn 拼子节点(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    let 子节点表 = match 节点.get("子").and_then(|子项| 子项.as_array()) {
        Some(子项) => 子项,
        None => return Ok(String::new()),
    };
    let mut 子文本 = String::new();
    for 子节点 in 子节点表 {
        子文本.push_str(&拼装树节点(子节点, 深度 + 1, 状态)?);
    }
    Ok(子文本)
}

pub(crate) fn 拼装树节点(节点: &Value, 深度: u16, 状态: &mut 渲染状态) -> Result<String, u32> {
    校验外观属性(节点)?;
    if 深度 > 树最大深度 {
        return Err(错误码::资源受限);
    }
    状态.计数 += 1;
    if 状态.计数 > 树最大节点数 {
        return Err(错误码::资源受限);
    }
    let 类型文本 = 取对象文本(节点, "类型");
    校验节点颜色(节点)?;
    let 片段文本 = match 类型文本.as_str() {
"表单容器" => 表单控件::拼装表单容器(节点, 深度, 状态)?,
"输入" => 表单控件::拼装输入(节点, 深度, 状态)?,
"按钮" => 表单控件::拼装按钮(节点, 深度, 状态)?,
"行" => 容器::拼装行(节点, 深度, 状态)?,
"列" => 容器::拼装列(节点, 深度, 状态)?,
"网格" => 容器::拼装网格(节点, 深度, 状态)?,
"侧栏" => 容器::拼装侧栏(节点, 深度, 状态)?,
"分区" => 容器::拼装分区(节点, 深度, 状态)?,
"画布" => 容器::拼装画布(节点, 深度, 状态)?,
"标题" => 叶面::拼装标题(节点, 深度, 状态)?,
"图标" => 叶面::拼装图标(节点, 深度, 状态)?,
"文字" => 叶面::拼装文字(节点, 深度, 状态)?,
"分隔条" => 叶面::拼装分隔条(节点, 深度, 状态)?,
        "表格" => 拼装表格(节点, 状态)?,
"表单" => 表单控件::拼装表单(节点, 深度, 状态)?,
"聊天流" => 叶面::拼装聊天流(节点, 深度, 状态)?,
        "窗口" => 应用窗口::拼装窗口(节点, 深度, 状态)?,
"悬浮层" => 容器::拼装悬浮层(节点, 深度, 状态)?,
"原样" => 叶面::拼装原样(节点, 深度, 状态)?,
        _ => return Err(错误码::内容不合法),
    };
    let 窗口标识 = 取对象文本(节点, "打开窗口");
    if !窗口标识.is_empty() {
        if !合法标识(&窗口标识) {
            return Err(错误码::内容不合法);
        }
        状态.需要窗口脚本 = true;
        return Ok(format!(
            "<div class=\"hs-tree-toggle\" data-window-open=\"{}\" style=\"display:contents\">{}</div>",
            转义网页文本(&窗口标识), 片段文本
        ));
    }
    let 切换标识 = 取对象文本(节点, "切换显隐");
    if !切换标识.is_empty() {
        if !合法标识(&切换标识) || 类型文本 == "悬浮层" {
            return Err(错误码::内容不合法);
        }
        状态.需要显隐脚本 = true;
        return Ok(format!(
            "<div class=\"hs-tree-toggle\" data-toggle=\"{}\" style=\"display:contents\">{}</div>",
            转义网页文本(&切换标识),
            片段文本
        ));
    }
    Ok(片段文本)
}

/// 4928 渲染组件树：一棵可无限嵌套的节点树 → HTML 片段。
pub(crate) fn 渲染组件树(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 树定义原文 = crate::业务实现::取文本参数(参数表, 0)?;
    let 树定义值: Value =
        serde_json::from_str(&树定义原文).map_err(|_| 错误码::内容不合法)?;
    let 根节点 = 树定义值.get("根").ok_or(错误码::内容不合法)?;
    let mut 状态 = 渲染状态 {
        计数: 0,
        需要显隐脚本: false,
        需要窗口脚本: false,
        需要选中脚本: false,
        需要放大脚本: false,
        需要筛选脚本: false,
    };
    let 根文本 = 拼装树节点(根节点, 0, &mut 状态)?;
    if 树定义值
        .get("整页")
        .and_then(|整页项| 整页项.as_bool())
        .unwrap_or(false)
    {
        let 页面标题文本 = 取对象文本(&树定义值, "页面标题");
        let mut 主体文本 = 根文本;
        if 状态.需要显隐脚本 {
            主体文本.push_str(显隐切换脚本);
        }
        if 状态.需要筛选脚本 {
            主体文本.push_str(筛选脚本);
        }
        if 状态.需要放大脚本 {
            主体文本.push_str(放大脚本);
        }
        if 状态.需要选中脚本 {
            主体文本.push_str(选中脚本);
        }
        if 状态.需要窗口脚本 {
            主体文本.push_str(窗口脚本);
        }
        return Ok((4, 拼装整页外壳(&页面标题文本, "", &主体文本, &中性样式文本())));
    }
    let 样式 = 取对象文本(根节点, "容器样式");
    let mut 脚本文本 = String::new();
    if 状态.需要显隐脚本 {
        脚本文本.push_str(显隐切换脚本);
    }
    if 状态.需要筛选脚本 {
        脚本文本.push_str(筛选脚本);
    }
    if 状态.需要放大脚本 {
        脚本文本.push_str(放大脚本);
    }
    if 状态.需要选中脚本 {
        脚本文本.push_str(选中脚本);
    }
    if 状态.需要窗口脚本 {
        脚本文本.push_str(窗口脚本);
    }
    Ok((
        4,
        format!(
            "<div class=\"hs-tree\" data-tree=\"1\" style=\"{}\">{}{}</div>",
            转义网页文本(&样式),
            根文本,
            脚本文本
        )
        .into_bytes(),
    ))
}

/// 空串兜底的小工具（画布定位用）。
pub(crate) trait 空值兜底 {
    fn if_empty(self, 兜底: &str) -> String;
}

impl 空值兜底 for String {
    fn if_empty(self, 兜底: &str) -> String {
        if self.is_empty() {
            兜底.to_string()
        } else {
            self
        }
    }
}
