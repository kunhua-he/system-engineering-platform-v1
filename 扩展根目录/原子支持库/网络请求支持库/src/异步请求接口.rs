use crate::编号与码面::{能力号,错误码};
use serde_json::{Value,json};
use url::form_urlencoded::Serializer as 查询串构造器;
use v1_contract::{数据槽,类型标签};
use v1_contract::复合值载荷::{复合元素,复合值,编码复合值载荷,解码复合值载荷};

fn 复合转JSON(当前值:复合值)->Result<Value,u32>{
    Ok(match 当前值{
        复合值::无值=>Value::Null,
        复合值::整数值(整数值)=>json!(整数值),
        复合值::双精度(双精度值)=>json!(双精度值),
        复合值::逻辑型(逻辑数值)=>json!(逻辑数值),
        复合值::文本载荷(文本数值)=>json!(文本数值),
        复合值::复合{标签,元素表}=>{
            if 标签==100{Value::Array(元素表.into_iter().map(|元素项|复合转JSON(元素项.值)).collect::<Result<_,_>>()?)}
            else{let mut 对象映射=serde_json::Map::new();for 元素项 in 元素表{对象映射.insert(元素项.名称,复合转JSON(元素项.值)?);}Value::Object(对象映射)}
        },
        _=>return Err(错误码::参数不合法),
    })
}
fn JSON转复合(当前值:Value)->Result<复合值,u32>{
    Ok(match 当前值{
        Value::Null=>复合值::无值,
        Value::Bool(逻辑数值)=>复合值::逻辑型(逻辑数值),
        Value::Number(数值内容)=>if let Some(整数值)=数值内容.as_i64(){复合值::整数值(整数值)}else{复合值::双精度(数值内容.as_f64().ok_or(错误码::内容不合法)?)},
        Value::String(文本数值)=>复合值::文本载荷(文本数值),
        Value::Array(数组内容)=>复合值::复合{标签:100,元素表:数组内容.into_iter().map(|子值|Ok(复合元素{名称:String::new(),值:JSON转复合(子值)?})).collect::<Result<_,u32>>()?},
        Value::Object(对象内容)=>复合值::复合{标签:101,元素表:对象内容.into_iter().map(|(字段名,子值)|Ok(复合元素{名称:字段名,值:JSON转复合(子值)?})).collect::<Result<_,u32>>()?},
    })
}
unsafe fn 取字典(参数槽:&数据槽)->Result<Value,u32>{
    if 参数槽.类型标签.取号值()!=101||!参数槽.是否引用()||(参数槽.槽值==0&&参数槽.槽字节长度>0){return Err(错误码::参数不合法);}
    if 参数槽.槽字节长度>786432{return Err(错误码::资源受限);}
    let 源字节=if 参数槽.槽字节长度==0{&[]}else{unsafe{std::slice::from_raw_parts(参数槽.槽值 as *const u8,参数槽.槽字节长度 as usize)}};
    let 元素表=解码复合值载荷(源字节,101).map_err(|_|错误码::参数不合法)?;
    复合转JSON(复合值::复合{标签:101,元素表})
}
fn 写结构(结构值:Value)->Result<数据槽,u32>{
    let 复合值::复合{元素表,..}=JSON转复合(结构值)? else{return Err(错误码::内容不合法);};
    let 返回字节=编码复合值载荷(103,&元素表).map_err(|_|错误码::内容不合法)?;
    let 返回长度=返回字节.len() as u64;
    Ok(数据槽::指针(类型标签::构造(103),Box::into_raw(返回字节.into_boxed_slice()) as *const u8 as u64,返回长度,true))
}
pub(crate) unsafe fn 处理异步(能力编号:u32,参数个数:u32,参数表:*const 数据槽)->Result<数据槽,u32>{
    if 参数个数!=1||参数表.is_null(){return Err(错误码::参数不合法);}
    let 参数槽=unsafe{&*参数表};
    if 能力编号==能力号::提交网络请求 {
        let 请求参数=unsafe{取字典(参数槽)}?;
        return crate::网络任务管理::提交请求(请求参数).map(|任务句柄|数据槽::内联槽(类型标签::构造(7),任务句柄,8));
    }
    if 能力编号==能力号::构建查询串{
        let 字典数值=unsafe{取字典(参数槽)}?;
        let mut 查询构造=查询串构造器::new(String::new());
        for(字段名,字段值)in 字典数值.as_object().ok_or(错误码::参数不合法)?{
            let 文本数值=match 字段值{Value::String(文本数值)=>文本数值.clone(),Value::Null=>String::new(),Value::Bool(_)|Value::Number(_)=>字段值.to_string(),_=>return Err(错误码::参数不合法)};
            查询构造.append_pair(字段名,&文本数值);
        }
        let 查询字节=查询构造.finish().into_bytes();let 查询长度=查询字节.len() as u64;
        return Ok(数据槽::指针(类型标签::构造(4),Box::into_raw(查询字节.into_boxed_slice()) as *const u8 as u64,查询长度,true));
    }
    if 参数槽.类型标签.取号值()!=7||参数槽.是否引用()||参数槽.槽值==0{return Err(错误码::参数不合法);}
    match 能力编号{
        能力号::读取网络任务=>写结构(crate::网络任务管理::读取任务(参数槽.槽值)?),
        能力号::取消网络任务|能力号::释放网络任务=>crate::网络任务管理::取消任务(参数槽.槽值,能力编号==能力号::释放网络任务).map(|已操作|数据槽::内联槽(类型标签::构造(3),已操作 as u64,1)),
        _=>Err(错误码::参数不合法),
    }
}
