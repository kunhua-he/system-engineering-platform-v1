use v1_contract::{命令信息, 平台信息, 表段};

use crate::命令声明面::{造命令表, 命令表项数};
use crate::执行函数面::执行函数表;

const 底座声明格式号: v1_contract::格式号 = v1_contract::格式号::构造(1398362929);
const 底座目标字宽: u16 = 64;
const 底座标识串: &[u8] = b"7b1a4e2c9d80f35a6c1e8d47b2f90531\0";
const 底座名称: &[u8] = "浏览器支持库\0".as_bytes();
const 底座说明: &[u8] = "无头浏览器会话与页面操作：创建会话、导航、读页面（文本/HTML/标题地址/按选择器取元素）、操作元素（点击/填值/悬停/滚入）、截图、关闭会话。走 Chrome DevTools 协议，会话生命周期归底座，最多同时 8 个会话；不做坐标模拟，不接管已登录的个人浏览器。\0".as_bytes();
const 底座实现版本: v1_contract::版本三元组 = v1_contract::版本三元组::构造(0, 1, 0);
const 底座要求宿主版本: v1_contract::版本要求 = v1_contract::版本要求::构造(1, 0);
const 底座要求内核版本: v1_contract::版本要求 = v1_contract::版本要求::构造(1, 0);
const 底座能力号段: [v1_contract::号段; 1] = [v1_contract::号段::构造(7001, 7099)];
const 底座错误段位表: [u32; 1] = [7];

const fn 底座能力号段表段() -> 表段<v1_contract::号段> {
    表段::构造(底座能力号段.as_ptr(), 1)
}
const fn 底座错误段位表段() -> 表段<u32> {
    表段::构造(底座错误段位表.as_ptr(), 1)
}

#[repr(transparent)]
struct 静态命令表(pub(crate) [命令信息; 命令表项数]);
unsafe impl Sync for 静态命令表 {}
unsafe impl Send for 静态命令表 {}

static 命令表存储: 静态命令表 = 静态命令表(造命令表());

#[repr(transparent)]
struct 静态声明(平台信息);
unsafe impl Sync for 静态声明 {}
unsafe impl Send for 静态声明 {}

static 扩展存储: 静态声明 = 静态声明(平台信息 {
    声明格式号: 底座声明格式号,
    目标字宽: 底座目标字宽,
    保留: 0,
    标识串: 底座标识串.as_ptr(),
    实现版本: 底座实现版本,
    要求宿主版本: 底座要求宿主版本,
    要求内核版本: 底座要求内核版本,
    名称: 底座名称.as_ptr(),
    说明: 底座说明.as_ptr(),
    状态位: 0,
    类型表: 表段::空实例(),
    命令表: 表段::构造(命令表存储.0.as_ptr(), 命令表项数 as u32),
    函数表: 执行函数表.as_ptr(),
    常量表: 表段::空实例(),
    通知函数: None,
    依赖清单: 表段::空实例(),
    能力号段: 底座能力号段表段(),
    通知号段: 表段::空实例(),
    错误段位表: 底座错误段位表段(),
    错误码表: crate::编号与码面::错误码信息表段(),
    命令类别表: 表段::空实例(),
    要求权限: 表段::空实例(),
    依赖版本要求: 表段::空实例(),
});

pub(crate) fn 取接缝指针() -> *const 平台信息 {
    &扩展存储.0 as *const 平台信息
}

#[unsafe(export_name = "GetPlatformInfo")]
pub extern "C" fn 取平台信息() -> *const 平台信息 {
    取接缝指针()
}

#[doc(hidden)]
#[allow(dead_code)]
pub fn 扩展声明() -> &'static 平台信息 {
    &扩展存储.0
}
