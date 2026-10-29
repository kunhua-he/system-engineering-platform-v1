use crate::编号与码面::{能力号, 错误码};
use crate::{向量与重排, 生成任务, 连接与句柄};
use serde_json::Value;
use v1_contract::复合值载荷::{复合元素, 复合值, 编码复合值载荷, 解码复合值载荷};
use v1_contract::{数据槽, 类型标签};

unsafe fn 取文本(参数槽: &数据槽) -> Result<&str, u32> {
    if !参数槽.是否引用() { return Err(错误码::参数不合法); }
    let 参数字节 = if 参数槽.槽字节长度 == 0 {
        &[][..]
    } else {
        unsafe { std::slice::from_raw_parts(参数槽.槽值 as *const u8, 参数槽.槽字节长度 as usize) }
    };
    std::str::from_utf8(参数字节).map_err(|_| 错误码::参数不合法)
}

fn 取无符号(参数槽: &数据槽) -> Result<u64, u32> {
    if 参数槽.是否引用() { return Err(错误码::参数不合法); }
    Ok(参数槽.槽值)
}

fn 取数值(参数槽: &数据槽) -> f64 {
    f64::from_bits(参数槽.槽值)
}

fn 复合转JSON(当前值: 复合值) -> Result<Value, u32> {
    Ok(match 当前值 {
        复合值::无值 => Value::Null,
        复合值::整数值(整数值) => serde_json::json!(整数值),
        复合值::双精度(双精度值) => serde_json::json!(双精度值),
        复合值::逻辑型(逻辑数值) => serde_json::json!(逻辑数值),
        复合值::文本载荷(文本数值) => serde_json::json!(文本数值),
        复合值::复合 { 标签, 元素表 } => {
            if 标签 == 100 {
                Value::Array(元素表.into_iter().map(|元素项| 复合转JSON(元素项.值)).collect::<Result<_, _>>()?)
            } else {
                let mut 对象映射 = serde_json::Map::new();
                for 元素项 in 元素表 { 对象映射.insert(元素项.名称, 复合转JSON(元素项.值)?); }
                Value::Object(对象映射)
            }
        }
        _ => return Err(错误码::参数不合法),
    })
}

fn JSON转复合(当前值: Value) -> Result<复合值, u32> {
    Ok(match 当前值 {
        Value::Null => 复合值::无值,
        Value::Bool(逻辑数值) => 复合值::逻辑型(逻辑数值),
        Value::Number(数值内容) => if let Some(整数值) = 数值内容.as_i64() {
            复合值::整数值(整数值)
        } else {
            复合值::双精度(数值内容.as_f64().ok_or(错误码::响应不合法)?)
        },
        Value::String(文本数值) => 复合值::文本载荷(文本数值),
        Value::Array(数组内容) => 复合值::复合 {
            标签: 100,
            元素表: 数组内容.into_iter().map(|子值| Ok(复合元素 { 名称: String::new(), 值: JSON转复合(子值)? })).collect::<Result<_, u32>>()?,
        },
        Value::Object(对象内容) => 复合值::复合 {
            标签: 101,
            元素表: 对象内容.into_iter().map(|(字段名, 子值)| Ok(复合元素 { 名称: 字段名, 值: JSON转复合(子值)? })).collect::<Result<_, u32>>()?,
        },
    })
}

unsafe fn 取复合(参数槽: &数据槽, 期望标签: u32) -> Result<Value, u32> {
    if !参数槽.是否引用() { return Err(错误码::参数不合法); }
    if 参数槽.槽字节长度 == 0 {
        return Ok(if 期望标签 == 100 { Value::Array(Vec::new()) } else { Value::Object(serde_json::Map::new()) });
    }
    let 参数字节 = unsafe { std::slice::from_raw_parts(参数槽.槽值 as *const u8, 参数槽.槽字节长度 as usize) };
    let 元素表 = 解码复合值载荷(参数字节, 期望标签).map_err(|_| 错误码::参数不合法)?;
    复合转JSON(复合值::复合 { 标签: 期望标签, 元素表 })
}

/// 请求头字典转有序表；保留调用方给的顺序，拒绝受控头。
pub(crate) fn 解析头表(头字典: &Value) -> Result<Vec<(String, String)>, u32> {
    let 头部对象 = 头字典.as_object().ok_or(错误码::参数不合法)?;
    let mut 头表 = Vec::with_capacity(头部对象.len());
    let mut 头部总长 = 0usize;
    for (头名称, 头内容) in 头部对象 {
        let 小写名 = 头名称.to_ascii_lowercase();
        if ["host", "content-length", "transfer-encoding", "connection", "authorization", "content-type"].contains(&小写名.as_str()) {
            return Err(错误码::参数不合法);
        }
        let 内容文本 = 头内容.as_str().ok_or(错误码::参数不合法)?;
        头部总长 += 头名称.len() + 内容文本.len();
        头表.push((头名称.clone(), 内容文本.to_owned()));
    }
    if 头表.len() > 32 || 头部总长 > 8192 { return Err(错误码::资源受限); }
    Ok(头表)
}

fn 写结构(结构值: Value) -> Result<数据槽, u32> {
    let 复合值::复合 { 元素表, .. } = JSON转复合(结构值)? else { return Err(错误码::响应不合法); };
    let 返回字节 = 编码复合值载荷(103, &元素表).map_err(|_| 错误码::响应不合法)?;
    let 返回长度 = 返回字节.len() as u64;
    Ok(数据槽::指针(类型标签::构造(103), Box::into_raw(返回字节.into_boxed_slice()) as *const u8 as u64, 返回长度, true))
}

/// 列表返回用标签 100：元素按下标顺序，元素名留空。
fn 写列表(列表值: Value) -> Result<数据槽, u32> {
    let Value::Array(数组内容) = 列表值 else { return Err(错误码::响应不合法); };
    let mut 元素表 = Vec::with_capacity(数组内容.len());
    for 子值 in 数组内容 {
        元素表.push(复合元素 { 名称: String::new(), 值: JSON转复合(子值)? });
    }
    let 返回字节 = 编码复合值载荷(100, &元素表).map_err(|_| 错误码::响应不合法)?;
    let 返回长度 = 返回字节.len() as u64;
    Ok(数据槽::指针(类型标签::构造(100), Box::into_raw(返回字节.into_boxed_slice()) as *const u8 as u64, 返回长度, true))
}

fn 写文本(文本内容: String) -> 数据槽 {
    let 文本字节 = 文本内容.into_bytes();
    let 文本长度 = 文本字节.len() as u64;
    数据槽::指针(类型标签::构造(4), Box::into_raw(文本字节.into_boxed_slice()) as *const u8 as u64, 文本长度, true)
}

fn 写逻辑(结果值: bool) -> 数据槽 {
    数据槽::内联槽(类型标签::构造(3), 结果值 as u64, 1)
}

fn 写句柄(类型编号: u32, 句柄值: u64) -> 数据槽 {
    数据槽::内联槽(类型标签::构造(类型编号), 句柄值, 8)
}

/// 连接参数：模型、模型地址、接口密钥、协议、静态头表。
type 连接参数 = (String, String, String, String, Vec<(String, String)>);

unsafe fn 读连接参数(参数槽表: &[数据槽]) -> Result<连接参数, u32> {
    let 模型 = unsafe { 取文本(&参数槽表[0]) }?;
    let 模型地址 = unsafe { 取文本(&参数槽表[1]) }?;
    let 接口密钥 = unsafe { 取文本(&参数槽表[2]) }?;
    let 协议 = unsafe { 取文本(&参数槽表[3]) }?;
    let 静态头值 = unsafe { 取复合(&参数槽表[4], 101) }?;
    let 静态头表 = 解析头表(&静态头值)?;
    Ok((模型.to_owned(), 模型地址.to_owned(), 接口密钥.to_owned(), 协议.to_owned(), 静态头表))
}

pub(crate) unsafe fn 执行(编号: u32, 参数槽表: &[数据槽]) -> Result<数据槽, u32> {
    match 编号 {
        能力号::连接模型 => {
            let (模型, 模型地址, 接口密钥, 协议, 静态头表) = unsafe { 读连接参数(参数槽表) }?;
            连接与句柄::连接对话模型(&模型, &模型地址, &接口密钥, &协议, 静态头表).map(|句柄值| 写句柄(6, 句柄值))
        }
        能力号::提交生成任务 => {
            let 句柄值 = 取无符号(&参数槽表[0])?;
            let 消息列表 = unsafe { 取复合(&参数槽表[1], 100) }?;
            let 系统提示词 = unsafe { 取文本(&参数槽表[2]) }?;
            let 温度 = 取数值(&参数槽表[3]);
            let 最大令牌数 = 取无符号(&参数槽表[4])?;
            let 工具 = unsafe { 取复合(&参数槽表[5], 100) }?;
            let 响应格式 = unsafe { 取复合(&参数槽表[6], 101) }?;
            let 附加请求头 = unsafe { 取复合(&参数槽表[7], 101) }?;
            let 生成请求 = 生成任务::生成请求 {
                消息列表: &消息列表,
                系统提示词,
                温度,
                最大令牌数,
                工具: &工具,
                响应格式: &响应格式,
                附加请求头: &附加请求头,
            };
            生成任务::提交(句柄值, 生成请求).map(|任务句柄| 写句柄(7, 任务句柄))
        }
        能力号::读取生成任务 => 生成任务::读取(取无符号(&参数槽表[0])?).and_then(写结构),
        能力号::取消生成任务 => 生成任务::取消(取无符号(&参数槽表[0])?).map(写逻辑),
        能力号::释放生成任务 => 生成任务::释放(取无符号(&参数槽表[0])?).map(写逻辑),
        能力号::释放句柄 => 连接与句柄::释放(取无符号(&参数槽表[0])?).map(写逻辑),
        能力号::资源快照 => {
            let (句柄数, 句柄明细) = 连接与句柄::快照()?;
            let (任务数, 在途数) = 生成任务::统计()?;
            Ok(写文本(serde_json::json!({
                "句柄数": 句柄数,
                "任务数": 任务数,
                "在途任务": 在途数,
                "句柄明细": 句柄明细.into_iter().map(|(句柄号, 模型名, 地址值)| serde_json::json!({"句柄": 句柄号, "模型": 模型名, "地址": 地址值})).collect::<Vec<_>>(),
            }).to_string()))
        }
        能力号::连接向量模型 => {
            let (模型, 模型地址, 接口密钥, 协议, 静态头表) = unsafe { 读连接参数(参数槽表) }?;
            连接与句柄::连接向量模型(&模型, &模型地址, &接口密钥, &协议, 静态头表).map(|句柄值| 写句柄(6, 句柄值))
        }
        能力号::生成嵌入 => {
            let 句柄值 = 取无符号(&参数槽表[0])?;
            let 文本列表 = unsafe { 取复合(&参数槽表[1], 100) }?;
            let 维度 = 取无符号(&参数槽表[2])?;
            向量与重排::生成嵌入(句柄值, &文本列表, 维度).map(|向量表| serde_json::json!(向量表)).and_then(写列表)
        }
        能力号::连接重排模型 => {
            let (模型, 模型地址, 接口密钥, 协议, 静态头表) = unsafe { 读连接参数(参数槽表) }?;
            连接与句柄::连接重排模型(&模型, &模型地址, &接口密钥, &协议, 静态头表).map(|句柄值| 写句柄(6, 句柄值))
        }
        能力号::执行重排 => {
            let 句柄值 = 取无符号(&参数槽表[0])?;
            let 查询 = unsafe { 取文本(&参数槽表[1]) }?;
            let 文档列表 = unsafe { 取复合(&参数槽表[2], 100) }?;
            let 返回条数 = 取无符号(&参数槽表[3])?;
            向量与重排::执行重排(句柄值, 查询, &文档列表, 返回条数).map(|结果表| {
                serde_json::json!(结果表.into_iter().map(|(文档序, 分数)| serde_json::json!({"索引": 文档序, "分数": 分数})).collect::<Vec<_>>())
            }).and_then(写列表)
        }
        _ => Err(错误码::参数不合法),
    }
}
