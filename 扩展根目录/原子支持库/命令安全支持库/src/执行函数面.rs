use crate::命令声明面::{命令表内位, 造命令表};
use crate::编号与码面::{能力号, 错误码};
use v1_contract::{执行函数, 数据槽, 类型标签};

fn 写调用(
    编号: u32, 返回槽: *mut 数据槽, 参数个数: u32, 参数表: *const 数据槽
) {
    if 返回槽.is_null() {
        return;
    }
    let 调用结果 = std::panic::catch_unwind(|| unsafe {
        crate::业务实现::处理调用(编号, 参数个数, 参数表)
    })
    .unwrap_or(Err(错误码::命令安全不可用));
    unsafe {
        *返回槽 = 调用结果.unwrap_or_else(|失败码| {
            数据槽::内联槽(类型标签::构造(u32::MAX), 失败码 as u64, 4)
        });
    }
}

pub unsafe extern "C-unwind" fn 检测危险命令入口(
    返回槽: *mut 数据槽,
    参数个数: u32,
    参数表: *const 数据槽,
) {
    写调用(能力号::检测危险命令, 返回槽, 参数个数, 参数表);
}
pub const fn 造函数表() -> [执行函数; 1] {
    let mut 本表 = [检测危险命令入口 as 执行函数; 1];
    本表[命令表内位(能力号::检测危险命令)] = 检测危险命令入口;
    本表
}
pub(crate) const 执行函数表: [执行函数; 1] = 造函数表();
const _: () = {
    let _ = 造命令表();
};
