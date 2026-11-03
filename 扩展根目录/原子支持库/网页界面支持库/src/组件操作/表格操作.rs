//! 超级列表框的行、列与事件原子操作，仍由 4929 统一入口调度。

use serde_json::{Value, json};

use crate::组件实例;
use crate::编号与码面::错误码;

#[path = "表格行列.rs"]
mod 表格行列;
use 表格行列::*;
#[path = "表格查询.rs"]
mod 表格查询;
use 表格查询::*;
#[path = "表格编辑.rs"]
mod 表格编辑;
use 表格编辑::*;
#[path = "表格图片.rs"]
mod 表格图片;
use 表格图片::调整图片坐标;

fn 取正整数参数(参数: &Value, 键名: &str) -> Result<usize, u32> {
    参数
        .get(键名)
        .and_then(Value::as_u64)
        .and_then(|数值| usize::try_from(数值).ok())
        .ok_or(错误码::参数不合法)
}

fn 取数组字段(节点: &Value, 键名: &str) -> Result<Vec<Value>, u32> {
    节点
        .get(键名)
        .and_then(Value::as_array)
        .cloned()
        .ok_or(错误码::内容不合法)
}

fn 取选择值(节点: &Value) -> Value {
    节点.get("__选中").cloned().unwrap_or_else(|| json!([]))
}

fn 调整选择序号(原选择: &Value, 位置: usize, 插入: bool) -> Value {
    let 选择序号表: Vec<usize> = match 原选择 {
        Value::String(单项) if !单项.is_empty() => 单项.parse().ok().into_iter().collect(),
        Value::Array(多项) => 多项
            .iter()
            .filter_map(Value::as_str)
            .filter_map(|文本| 文本.parse::<usize>().ok())
            .collect(),
        _ => Vec::new(),
    };
    let 调整后: Vec<Value> = 选择序号表
        .into_iter()
        .filter_map(|序号| {
            if 插入 {
                Some(if 序号 >= 位置 { 序号 + 1 } else { 序号 })
            } else if 序号 == 位置 {
                None
            } else {
                Some(if 序号 > 位置 { 序号 - 1 } else { 序号 })
            }
        })
        .map(|序号| Value::from(序号.to_string()))
        .collect();
    if 原选择.is_string() {
        调整后.first().cloned().unwrap_or_else(|| Value::from(""))
    } else {
        Value::Array(调整后)
    }
}

fn 调整行属性字段(节点: &Value, 位置: usize, 插入: bool) -> Vec<(String, Value)> {
    [
        "__表项数值",
        "__表项图片",
        "__表项状态图片",
        "__表项缩进",
        "__检查状态",
        "检查框状态",
        "图片组",
        "状态图片组",
        "表项数值",
        "表项缩进",
        "__表项提示",
    ]
    .iter()
    .filter_map(|字段名| {
        let mut 属性数组 = 节点.get(*字段名)?.as_array()?.clone();
        if 插入 {
            属性数组.insert(位置, Value::Null);
        } else if 位置 < 属性数组.len() {
            属性数组.remove(位置);
        }
        Some(((*字段名).to_string(), Value::Array(属性数组)))
    })
    .collect()
}

fn 更新表格字段(
    句柄: u64, mut 字段表: Vec<(String, Value)>
) -> Result<(u32, Vec<u8>), u32> {
    if 字段表.iter().any(|(键名, _)| 键名 == "行" || 键名 == "列") {
        if !字段表.iter().any(|(键名, _)| 键名 == "__编辑单元格") {
            字段表.push(("__编辑单元格".to_string(), Value::Null));
        }
        字段表.push(("__滚动目标".to_string(), Value::Null));
    }
    let mut 待验节点 = 组件实例::取节点(句柄)?;
    for (键名, 字段值) in &字段表 {
        待验节点[键名] = 字段值.clone();
    }
    crate::组件树::渲染单节点(&待验节点)?;
    let 新节点 = 组件实例::改节点(句柄, |对象| {
        for (键名, 字段值) in 字段表 {
            对象.insert(键名, 字段值);
        }
    })?;
    super::回执(&新节点, Vec::new())
}

fn 校验行数据(节点: &Value, 行数据: &Value) -> Result<(), u32> {
    let 列数 = 节点
        .get("列")
        .and_then(Value::as_array)
        .ok_or(错误码::内容不合法)?
        .len();
    let 单元格表 = 行数据.as_array().ok_or(错误码::参数不合法)?;
    if 单元格表.len() != 列数 {
        return Err(错误码::内容不合法);
    }
    Ok(())
}

pub(crate) fn 尝试执行(
    句柄: u64,
    操作名: &str,
    参数: &Value,
) -> Result<Option<(u32, Vec<u8>)>, u32> {
    let 节点 = 组件实例::取节点(句柄)?;
    if 节点.get("类型").and_then(Value::as_str) != Some("表格") {
        return Ok(None);
    }
    if let Some(查询回执) = 查询表格原子(句柄, 操作名, 参数)? {
        return Ok(Some(查询回执));
    }
    let 回执 = match 操作名 {
        "追加" => Some(插入表格行(句柄, 参数, true)?),
        "插入行" | "插入表项" => Some(插入表格行(句柄, 参数, false)?),
        "删除" | "删除行" | "删除表项" => Some(删除表格行(句柄, 参数)?),
        "全部删除" | "清空表格" => Some(清空表格数据(句柄)?),
        "设置单元格" | "置标题" => Some(设置表格单元格(句柄, 参数)?),
        "设置表项数值" | "置表项数值" => {
            Some(设置行属性(句柄, 参数, "__表项数值", "表项数值")?)
        }
        "设置表项图片" | "置图片" => {
            Some(设置行属性(句柄, 参数, "__表项图片", "图片索引")?)
        }
        "设置状态图片" | "置状态图片" => {
            if 节点.get("勾选列").and_then(Value::as_bool) == Some(true)
                && 参数
                    .get("图片索引")
                    .is_some_and(|图片值| 图片值.is_number() || 图片值.is_boolean())
            {
                Some(设置检查状态(句柄, 参数)?)
            } else {
                Some(设置行属性(句柄, 参数, "__表项状态图片", "图片索引")?)
            }
        }
        "设置表项缩进" | "置缩进数目" => {
            Some(设置行属性(句柄, 参数, "__表项缩进", "缩进数目")?)
        }
        "插入列" => Some(插入表格列(句柄, 参数)?),
        "删除列" => Some(删除表格列(句柄, 参数)?),
        "设置列宽" | "置列宽" => Some(设置表格列属性(句柄, 参数, "列宽", "列宽")?),
        "设置行高" | "置行高" => Some(设置表格行高(句柄, 参数)?),
        "设置表项提示" | "置表项提示" => Some(设置表项提示(句柄, 参数)?),
        "设置列提示" | "置列提示" => Some(设置列提示(句柄, 参数)?),
        "设置列对齐" => Some(设置表格列属性(句柄, 参数, "列对齐方式", "对齐方式")?),
        "设置列标题" | "置列标题" => Some(设置列标题(句柄, 参数)?),
        "移动列" => Some(移动表格列(句柄, 参数)?),
        "选择表项" => Some(修改表格选择(句柄, 参数, true)?),
        "取消表项选择" => Some(修改表格选择(句柄, 参数, false)?),
        "设置列图片" | "置列图片" => {
            Some(设置列图片属性(句柄, 参数, "__列图片", "图片索引")?)
        }
        "设置列图片居右" => Some(设置列图片属性(
            句柄,
            参数,
            "__列图片居右",
            "图片居右",
        )?),
        "查找表项" => Some(查找表格行(句柄, 参数, false)?),
        "查找表项数值" => Some(查找表格行(句柄, 参数, true)?),
        "保证显示" => {
            let 行序号 = 取正整数参数(参数, "表项索引")?;
            let 目标页码 = crate::组件树::定位表格页码(&节点, 行序号)?;
            Some(更新表格字段(
                句柄,
                vec![
                    ("__滚动目标".to_string(), Value::from(行序号 as u64)),
                    ("__页码".to_string(), Value::from(目标页码 as u64)),
                ],
            )?)
        }
        "排列图标" => {
            let 排列方式 = 参数.get("排列方式").and_then(Value::as_str).unwrap_or("上");
            if !matches!(排列方式, "上" | "左" | "中" | "右") {
                return Err(错误码::参数不合法);
            }
            Some(更新表格字段(
                句柄,
                vec![
                    ("__排列方式".to_string(), Value::from(排列方式)),
                    ("图标对齐方式".to_string(), Value::from(排列方式)),
                    ("自动排列图标".to_string(), Value::from(true)),
                ],
            )?)
        }
        "进入编辑" => Some(开始表格编辑(句柄, 参数)?),
        "结束编辑" => Some(结束表格编辑(句柄, 参数)?),
        "取消编辑" => Some(更新表格字段(
            句柄,
            vec![("__编辑单元格".to_string(), Value::Null)],
        )?),
        "切换检查" => Some(翻转检查状态(句柄, 参数)?),
        "设置检查状态" => Some(设置检查状态(句柄, 参数)?),
        "记录事件" => Some(记录表格事件(句柄, 参数)?),
        _ => None,
    };
    Ok(回执)
}

#[cfg(test)]
mod 测试 {
    use super::*;
    use serde_json::json;

    fn 建立表格句柄() -> u64 {
        组件实例::登记实例(
            &json!({"类型":"表格","列":["名称","数量"],"行":[["面膜",1],["精华",2]],"选择模式":"多选","__选中":["1"]}),
            "表格操作测试",
            None,
        )
    }

    #[test]
    fn 插入删除行保持选择身份() {
        let 句柄 = 建立表格句柄();
        let 插入回执 =
            尝试执行(句柄, "插入行", &json!({"插入位置":0,"行数据":["新行",0]})).unwrap();
        assert!(插入回执.is_some());
        let 删除回执 = 尝试执行(句柄, "删除行", &json!({"表项索引":0})).unwrap();
        assert!(删除回执.is_some());
        let 状态 = 组件实例::读状态(句柄).unwrap();
        assert_eq!(状态["选中项"], json!(["1"]));
        assert!(组件实例::释放(句柄));
    }

    #[test]
    fn 插入删除列同步所有行() {
        let 句柄 = 建立表格句柄();
        尝试执行(句柄, "插入列", &json!({"插入位置":1,"标题":"备注"}))
            .unwrap_or_else(|码| panic!("插入列失败 码={码}"));
        尝试执行(句柄, "删除列", &json!({"列索引":1})).unwrap();
        let 节点 = 组件实例::取节点(句柄).unwrap();
        assert_eq!(节点["列"], json!(["名称", "数量"]));
        assert_eq!(节点["行"][0], json!(["面膜", 1]));
        assert!(组件实例::释放(句柄));
    }

    #[test]
    fn 移动列同步列级数组与每行单元格() {
        let 句柄 = 组件实例::登记实例(
            &json!({"类型":"表格","列":["名称","数量","备注"],"行":[["a",1,"x"],["b",2,"y"]],"列宽":[60,80,100],"列对齐方式":["左","中","右"]}),
            "移动列测试",
            None,
        );
        尝试执行(句柄, "移动列", &json!({"列索引":0,"目标位置":2}))
            .unwrap_or_else(|码| panic!("移动列失败 码={码}"));
        let 节点 = 组件实例::取节点(句柄).unwrap();
        assert_eq!(节点["列"], json!(["数量", "备注", "名称"]));
        assert_eq!(节点["列宽"], json!([80, 100, 60]));
        assert_eq!(节点["列对齐方式"], json!(["中", "右", "左"]));
        assert_eq!(节点["行"][0], json!([1, "x", "a"]));
        assert!(尝试执行(句柄, "移动列", &json!({"列索引":0,"目标位置":9})).is_err());
        assert!(组件实例::释放(句柄));
    }

    #[test]
    fn 清空表格连行级数组一起清() {
        let 句柄 = 组件实例::登记实例(
            &json!({"类型":"表格","列":["名称"],"行":[["面膜"],["精华"]],"勾选列":true}),
            "清空测试",
            None,
        );
        尝试执行(
            句柄,
            "设置表项提示",
            &json!({"表项索引":0,"提示文本":"看这里"}),
        )
        .unwrap_or_else(|码| panic!("设置表项提示失败 码={码}"));
        尝试执行(句柄, "切换检查", &json!({"表项索引":1}))
            .unwrap_or_else(|码| panic!("切换检查失败 码={码}"));
        尝试执行(句柄, "清空表格", &json!({})).unwrap_or_else(|码| panic!("清空失败 码={码}"));
        let 节点 = 组件实例::取节点(句柄).unwrap();
        assert_eq!(节点["行"], json!([]));
        assert_eq!(节点["__表项提示"], json!([]));
        assert_eq!(节点["__检查状态"], json!([]));
        assert!(组件实例::释放(句柄));
    }

    #[test]
    fn 查询编辑与事件原子可用() {
        let 句柄 = 组件实例::登记实例(
            &json!({"类型":"表格","列":["名称","数量"],"行":[["面膜",1]],"选择模式":"单选","允许编辑":true}),
            "表格查询测试",
            None,
        );
        尝试执行(句柄, "设置单元格", &json!({"表项索引":0,"列索引":1,"值":3})).unwrap();
        尝试执行(句柄, "取标题", &json!({"表项索引":0,"列索引":1})).unwrap();
        let 状态 = 组件实例::读状态(句柄).unwrap();
        assert_eq!(状态["查询结果"], json!(3));
        尝试执行(句柄, "进入编辑", &json!({"表项索引":0,"列索引":0})).unwrap();
        尝试执行(
            句柄,
            "结束编辑",
            &json!({"表项索引":0,"列索引":0,"标题":"改名"}),
        )
        .unwrap();
        尝试执行(
            句柄,
            "记录事件",
            &json!({"事件名":"表项被激活","表项索引":0}),
        )
        .unwrap();
        let 状态 = 组件实例::读状态(句柄).unwrap();
        assert_eq!(状态["行"][0][0], json!("改名"));
        assert_eq!(状态["最后事件"]["事件名"], json!("表项被激活"));
        assert!(组件实例::释放(句柄));
    }
}
