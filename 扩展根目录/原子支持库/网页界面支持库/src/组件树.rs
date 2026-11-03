//! 组件树：窗口内容与整页都由一棵可递归嵌套的节点树描述。
//!
//! 容器（行 / 列 / 网格 / 侧栏 / 分区 / 画布）可以无限嵌套，叶子出真正的界面元素。
//! 产品语义上不限制嵌套层数；工程上拦两道闸（深度 32 层、节点 2000 个），
//! 只防「写错了的树把渲染拖死」，正常界面远远用不到。

use serde_json::Value;

use crate::业务实现::{取对象文本, 拼装整页外壳, 转义网页文本};
use crate::交互运行时::脚本合集;
use crate::编号与码面::错误码;
use crate::视觉基准::中性样式文本;
use 数据表格::拼装表格;

#[path = "组件树/外观属性.rs"]
mod 外观属性;
#[path = "组件树/应用窗口.rs"]
mod 应用窗口;
#[path = "组件树/数据表格.rs"]
mod 数据表格;
pub(crate) use 数据表格::{固化表格列宽, 定位表格页码};
#[path = "组件树/句柄挂载.rs"]
mod 句柄挂载;
#[path = "组件树/条目列表.rs"]
mod 条目列表;
#[path = "组件树/树型框.rs"]
mod 树型框;
#[path = "组件预设.rs"]
mod 组件预设;

#[path = "组件树/叶面.rs"]
mod 叶面;
#[path = "组件树/容器.rs"]
mod 容器;
#[path = "组件树/表单控件.rs"]
mod 表单控件;

use 外观属性::{
    取尺寸, 合法标识, 拼外观样式, 校验外观属性, 校验节点颜色, 背景样式文本
};

thread_local! {
    /// 当前这次渲染的归属串：拉起时随句柄一起登记，释放与回收都按它。
    static 渲染归属: std::cell::RefCell<String> = const { std::cell::RefCell::new(String::new()) };
    /// 正在渲染的节点的父组件句柄：登记子组件时记下父子关系，改动才能同步回父容器。
    static 渲染父句柄: std::cell::Cell<Option<u64>> = const { std::cell::Cell::new(None) };
}

/// 取当前渲染归属（未设置时为空串，句柄照常可用，只是无法按归属批量释放）。
pub(crate) fn 当前归属() -> String {
    渲染归属.with(|单元| 单元.borrow().clone())
}

/// 取当前正在渲染的父组件句柄。
pub(crate) fn 当前父句柄() -> Option<u64> {
    渲染父句柄.with(|单元| 单元.get())
}

/// 给这次渲染挂一个归属串。
pub(crate) fn 设置归属(归属文本: &str) {
    渲染归属.with(|单元| {
        *单元.borrow_mut() = 归属文本.to_string();
    });
}

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
    pub(crate) 需要组件引导脚本: bool,
    pub(crate) 需要提示脚本: bool,
    pub(crate) 需要确认脚本: bool,
    pub(crate) 需要右键脚本: bool,
    pub(crate) 需要拖放脚本: bool,
}

impl 渲染状态 {
    /// 一次渲染的干净起点：所有脚本开关都是关的，遇到什么才开什么。
    pub(crate) fn 新() -> 渲染状态 {
        渲染状态 {
            计数: 0,
            需要显隐脚本: false,
            需要窗口脚本: false,
            需要选中脚本: false,
            需要放大脚本: false,
            需要筛选脚本: false,
            需要组件引导脚本: false,
            需要提示脚本: false,
            需要确认脚本: false,
            需要右键脚本: false,
            需要拖放脚本: false,
        }
    }
}

// 控件自身尺寸与描边：宽 / 高 / 圆角 / 边框颜色 / 背景色。

/// 通用样式：所有节点都能带，拼成 style 属性值。
pub(crate) fn 拼通用样式(节点: &Value, 基础: &str) -> String {
    // 基础为空时不带前导分号，免得 style 里出现 `;width:…` 这种脏开头。
    let mut 样式 = String::from(基础);
    let 起头 = 样式.clone();
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
    let 去头 = 样式.trim_start_matches(';');
    if 去头.is_empty() {
        return String::new();
    }
    if 起头.is_empty() {
        去头.to_string()
    } else {
        样式
    }
}

/// 递归出口：子节点表
pub(crate) fn 拼子节点(
    节点: &Value, 深度: u16, 状态: &mut 渲染状态
) -> Result<String, u32> {
    let 子节点表 = match 节点.get("子").and_then(|子项| 子项.as_array()) {
        Some(子项) => 子项,
        None => return Ok(String::new()),
    };
    let 本节点句柄 = 节点.get("__组件句柄").and_then(|项| 项.as_u64());
    let 旧父 = 当前父句柄();
    if let Some(键) = 本节点句柄 {
        渲染父句柄.with(|单元| 单元.set(Some(键)));
    }
    let mut 子文本 = String::new();
    let 结果 = (|| -> Result<String, u32> {
        for 子节点 in 子节点表 {
            子文本.push_str(&拼装树节点(子节点, 深度 + 1, 状态)?);
        }
        Ok(子文本)
    })();
    渲染父句柄.with(|单元| 单元.set(旧父));
    结果
}

/// 渲染一个节点，并给它的根元素挂上组件句柄。
///
/// 句柄是「操作哪个组件」的唯一凭据：每个渲染出来的节点都发一个，
/// 调用方后续拿句柄传参就能单独重渲染这一个组件。
pub(crate) fn 拼装树节点(
    节点: &Value, 深度: u16, 状态: &mut 渲染状态
) -> Result<String, u32> {
    // 先签发句柄，再带着句柄渲染：组件自身要拿句柄去挂操作属性（表头点一下、
    // 分页按钮点一下，都是把「句柄 + 操作 + 参数」交回宿主），渲染完再往根元素写属性。
    let mut 规范节点 = 组件预设::应用预设(节点)?;
    crate::组件实例::规范表格声明(&mut 规范节点);
    固化表格列宽(&mut 规范节点)?;
    let 节点 = &规范节点;
    let 句柄 = crate::组件实例::登记实例(节点, &当前归属(), 当前父句柄());
    let mut 带句柄节点 = 节点.clone();
    if let Some(对象) = 带句柄节点.as_object_mut() {
        对象.insert("__组件句柄".to_string(), Value::from(句柄));
    }
    let 片段文本 = 拼装树节点内层(&带句柄节点, 深度, 状态)?;
    if 句柄挂载::首标签带句柄(&片段文本) {
        return Ok(片段文本);
    }
    Ok(句柄挂载::注入句柄属性(&片段文本, 句柄))
}

fn 拼装树节点内层(
    节点: &Value, 深度: u16, 状态: &mut 渲染状态
) -> Result<String, u32> {
    // 预设先铺底：内置字段 + 节点自身字段，之后整条链路只看合并结果。
    let 合并节点 = 组件预设::应用预设(节点)?;
    let 节点 = &合并节点;
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
        "树型框" => 树型框::拼装树型框(节点, 状态)?,
        "列表" => 条目列表::拼装条目列表(节点, 状态)?,
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
            "<div class=\"hs-tree-toggle\" data-窗口打开=\"{}\" style=\"display:contents\">{}</div>",
            转义网页文本(&窗口标识),
            片段文本
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
    // 声明式交互挂载：提示 / 确认 / 右键菜单 / 拖放只在节点上多挂一层 data-*，脚本按属性接管。
    let mut 挂载属性 = String::new();
    let 提示文本 = 取对象文本(节点, "提示文案");
    if !提示文本.is_empty() {
        状态.需要提示脚本 = true;
        挂载属性.push_str(&format!(" data-toast=\"{}\"", 转义网页文本(&提示文本)));
    }
    let 确认文本 = 取对象文本(节点, "确认文案");
    if !确认文本.is_empty() {
        状态.需要确认脚本 = true;
        挂载属性.push_str(&format!(" data-confirm=\"{}\"", 转义网页文本(&确认文本)));
    }
    if 节点
        .get("右键菜单")
        .map(|项| 项.is_array())
        .unwrap_or(false)
    {
        状态.需要右键脚本 = true;
        let 菜单原文 = 节点
            .get("右键菜单")
            .map(|项| 项.to_string())
            .unwrap_or_default();
        挂载属性.push_str(&format!(" data-menu=\"{}\"", 转义网页文本(&菜单原文)));
    }
    if 节点
        .get("可拖")
        .and_then(|项| 项.as_bool())
        .unwrap_or(false)
    {
        状态.需要拖放脚本 = true;
        挂载属性.push_str(" data-draggable=\"1\"");
        let 拖动键 = 取对象文本(节点, "拖动键");
        if !拖动键.is_empty() {
            挂载属性.push_str(&format!(" data-drag-key=\"{}\"", 转义网页文本(&拖动键)));
        }
    }
    let 拖放组 = 取对象文本(节点, "拖放组");
    if !拖放组.is_empty() {
        if !合法标识(&拖放组) {
            return Err(错误码::内容不合法);
        }
        状态.需要拖放脚本 = true;
        挂载属性.push_str(&format!(" data-drop-group=\"{}\"", 转义网页文本(&拖放组)));
        let 回传地址 = 取对象文本(节点, "顺序回传地址");
        if !回传地址.is_empty() && !回传地址.starts_with('/') {
            return Err(错误码::内容不合法);
        }
        if !回传地址.is_empty() {
            挂载属性.push_str(&format!(" data-order-url=\"{}\"", 转义网页文本(&回传地址)));
        }
    }
    if 挂载属性.is_empty() {
        return Ok(片段文本);
    }
    Ok(format!(
        "<div class=\"hs-tree-hook\" style=\"display:contents\"{挂载属性}>{片段文本}</div>"
    ))
}

/// 渲染一个节点（4929 操作组件重渲染用）：只出一段片段，不附整页外壳与脚本。
pub(crate) fn 渲染单节点(节点: &Value) -> Result<String, u32> {
    let mut 状态 = 渲染状态::新();
    拼装树节点(节点, 0, &mut 状态)
}

/// 整页模式自带的宿主实现：`window.hs组件操作({句柄, 操作, 参数})` → POST → 原位替换。
///
/// 为什么放在底座：每个项目都各自写一遍这段，等于把「交互」这件事的实现散成多份。
/// 默认地址是同源的 `/组件操作`（V4 就是这个）；要换地址在树定义里给 `组件操作地址`。
fn 默认宿主脚本(操作地址: &str) -> String {
    let 地址 = 转义网页文本(操作地址);
    format!(
        "<script>(function(){{if(typeof window.hs组件操作==='function'){{return}}window.hs组件操作=function(请求){{return fetch('{地址}',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(请求)}}).then(function(回){{return 回.json()}}).then(function(回执){{if(!回执||!回执.片段){{return}}var 旧=document.querySelector('[data-hs-h=\"'+请求.句柄+'\"]');if(!旧){{return}}var 盒=document.createElement('div');盒.innerHTML=回执.片段;var 新=盒.firstElementChild;if(新){{旧.replaceWith(新);if(请求.操作==='选中'||请求.操作==='选择表项'){{var 聚焦目标=新.querySelector('table');if(聚焦目标){{聚焦目标.focus()}}}}window.__未刷新=1}}}})}}}})();</script>"
    )
}

/// 4928 渲染组件树：一棵可无限嵌套的节点树 → HTML 片段。
pub(crate) fn 渲染组件树(树定义原文: &str) -> Result<(u32, Vec<u8>), u32> {
    let 树定义值: Value =
        serde_json::from_str(树定义原文).map_err(|_| 错误码::内容不合法)?;
    let 根节点 = 树定义值.get("根").ok_or(错误码::内容不合法)?;
    let 归属文本 = 取对象文本(&树定义值, "页面标识");
    let 归属文本 = if 归属文本.is_empty() {
        format!("渲染-{}", crate::组件实例::新归属标记())
    } else {
        归属文本
    };
    设置归属(&归属文本);
    let mut 状态 = 渲染状态::新();
    let 根文本 = 拼装树节点(根节点, 0, &mut 状态)?;
    if 树定义值
        .get("整页")
        .and_then(|整页项| 整页项.as_bool())
        .unwrap_or(false)
    {
        let 页面标题文本 = 取对象文本(&树定义值, "页面标题");
        // 整页自带一份宿主实现：把点表头 / 翻页 POST 回同源的 组件操作地址，
        // 回来只替换这一段的片段。没有它，整页里的交互按钮点了没反应。
        let 操作地址 = 取对象文本(&树定义值, "组件操作地址");
        let 操作地址 = if 操作地址.is_empty() {
            "/组件操作".to_string()
        } else {
            操作地址
        };
        let 宿主脚本 = 默认宿主脚本(&操作地址);
        let 主体文本 = 根文本 + &脚本合集(&状态) + &宿主脚本;
        return Ok((
            4,
            拼装整页外壳(&页面标题文本, "", &主体文本, &中性样式文本()),
        ));
    }
    let 样式 = 取对象文本(根节点, "容器样式");
    let 脚本文本 = 脚本合集(&状态);
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
