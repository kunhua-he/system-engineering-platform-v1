use v1_contract::{数据槽,类型标签};
pub(crate) fn 判登录次数(当前失败次数:i64,最大失败次数:i64)->Result<bool,u32>{
    if 当前失败次数<0||最大失败次数<=0{return Err(crate::声明接口面::参数不合法码);}
    Ok(当前失败次数>=最大失败次数)
}
pub(crate) unsafe extern "C-unwind" fn 登录判定入口(返回槽:*mut 数据槽,参数个数:u32,参数表:*const 数据槽){
    if 返回槽.is_null(){return;}
    let 判定结果=if 参数个数!=2||参数表.is_null(){Err(crate::声明接口面::参数不合法码)}else{
        let 参数槽表=unsafe{std::slice::from_raw_parts(参数表,2)};
        if 参数槽表.iter().any(|参数槽|参数槽.类型标签.取号值()!=1||参数槽.是否引用()){Err(crate::声明接口面::参数不合法码)}
        else{判登录次数(参数槽表[0].槽值 as i64,参数槽表[1].槽值 as i64)}
    };
    unsafe{*返回槽=match 判定结果{Ok(锁定)=>数据槽::内联槽(类型标签::构造(3),锁定 as u64,1),Err(失败码)=>数据槽::内联槽(类型标签::构造(u32::MAX),失败码 as u64,4)}};
}
