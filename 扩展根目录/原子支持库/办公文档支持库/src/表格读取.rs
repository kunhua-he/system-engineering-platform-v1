//! 表格读取（XLSX → JSON 块）：**只做模块声明与解析入口**，实现按关注点住同名字文件夹
//! `src/表格读取/`（`开发规范.md` 第六节「改一处不必读全件」）。
//!
//! | 件 | 职责 |
//! | --- | --- |
//! | `基础件.rs` | XML 属性取值 · 嵌套深度上限 |
//! | `工作簿解析.rs` | zip 归档取件（styles / workbook / rels / worksheets）· 表名↔部件路径 |
//! | `样式解析.rs` | styles.xml → 字体 / 填充 / 数字格式 / 单元格格式四张表 |
//! | `单元格读取.rs` | 单元值转换 · A1 引用取行列 · 单格可见样式组装 |
//! | `工作表附加.rs` | 工作表正文附加扫描（合并区 · 带格式格） |
//!
//! 读者路径：改解析口径看 `单元格读取`；改样式判定看 `样式解析`；改取件范围看 `工作簿解析`。

use calamine::{Data as 单元值, Reader as 工作簿读取接口, Xlsx as 工作簿读取器};
use serde_json::{Value as 数据值, json as 构造数据};

use crate::办公资源;
use crate::编号与码面::错误码;
use crate::表格边界::{读取表格文件, 核矩形预算, 最大工作表数, 最大回读字节};

#[path = "表格读取/基础件.rs"]
mod 基础件;
#[path = "表格读取/单元格读取.rs"]
mod 单元格读取;
#[path = "表格读取/工作簿解析.rs"]
mod 工作簿解析;
#[path = "表格读取/工作表附加.rs"]
mod 工作表附加;
#[path = "表格读取/样式解析.rs"]
mod 样式解析;

use 工作簿解析::{取部件文本, 读取工作簿部件};
use 单元格读取::转换单元值;
use 工作表附加::解析工作表附加;

pub fn 解析表格(文件路径: &str) -> Result<String, u32> {
    let 文件字节 = 读取表格文件(文件路径)?;
    let 工作簿部件 = 读取工作簿部件(&文件字节)?;
    let 图片清单 = 办公资源::枚举图片资源(文件路径, "xl/media/")?;
    let 资源节点 = 办公资源::组装资源JSON(&图片清单);
    let mut 读取器 = 工作簿读取器::new(std::io::Cursor::new(文件字节)).map_err(|_| 错误码::内容不合法)?;
    let 表名清单 = 读取器.sheet_names().to_vec();
    if 表名清单.is_empty() || 表名清单.len() > 最大工作表数 { return Err(错误码::内容不合法); }
    let mut 块列表 = Vec::new();
    let mut 累计格数 = 0usize;
    let mut 累计文本字节 = 0usize;
    for (表序位, 表名文本) in 表名清单.into_iter().enumerate() {
        let 数据区域 = 读取器.worksheet_range(&表名文本).map_err(|_| 错误码::内容不合法)?;
        let 公式区域 = 读取器.worksheet_formula(&表名文本).map_err(|_| 错误码::内容不合法)?;
        let 末格位序 = match (数据区域.end(), 公式区域.end()) {
            (Some(数据末格), Some(公式末格)) => Some((数据末格.0.max(公式末格.0), 数据末格.1.max(公式末格.1))),
            (数据末格, 公式末格) => 数据末格.or(公式末格),
        };
        let mut 表格数据 = Vec::new();
        if let Some((末行位序, 末列位序)) = 末格位序 {
            核矩形预算(末行位序 as usize + 1, 末列位序 as usize + 1, &mut 累计格数, 错误码::内容不合法)?;
            for 行位序 in 0..=末行位序 {
                let mut 单行数据 = Vec::new();
                for 列位序 in 0..=末列位序 {
                    let 单元数据 = if let Some(公式文本) = 公式区域.get_value((行位序, 列位序)).filter(|公式文本| !公式文本.is_empty()) {
                        数据值::String(format!("={公式文本}"))
                    } else {
                        转换单元值(数据区域.get_value((行位序, 列位序)).unwrap_or(&单元值::Empty))?
                    };
                    if let Some(单元文本) = 单元数据.as_str() {
                        累计文本字节 = 累计文本字节.checked_add(单元文本.len()).ok_or(错误码::内容不合法)?;
                        if 累计文本字节 > 最大回读字节 { return Err(错误码::内容不合法); }
                    }
                    单行数据.push(单元数据);
                }
                表格数据.push(单行数据);
            }
        }
        let 部件路径 = 工作簿部件.表名到路径.get(&表名文本).cloned()
            .unwrap_or_else(|| format!("xl/worksheets/sheet{}.xml", 表序位 + 1));
        let (合并列表, 样式网格) = match 取部件文本(&工作簿部件, &部件路径) {
            Some(工作表文本) => 解析工作表附加(工作表文本, &工作簿部件.样式表)?,
            None => (Vec::new(), Vec::new()),
        };
        块列表.push(构造数据!({
            "类型":"工作表",
            "文本":"",
            "表格数据":表格数据,
            "来源位置":{"工作表":表名文本},
            "合并列表":合并列表,
            "样式网格":样式网格
        }));
    }
    let 返回文本 = 构造数据!({"工作表数":块列表.len(),"块列表":块列表,"资源列表":资源节点}).to_string();
    if 返回文本.len() > 最大回读字节 { return Err(错误码::内容不合法); }
    Ok(返回文本)
}
