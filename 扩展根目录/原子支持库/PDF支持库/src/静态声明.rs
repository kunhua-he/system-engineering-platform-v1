use v1_contract::{命令信息, 平台信息, 表段};

use crate::命令声明面::{命令表项数, 造命令表};
use crate::执行函数面::执行函数表;

// ── 声明数据（源：本扩展目录 包声明.json）──
const 底座声明格式号: v1_contract::格式号 = v1_contract::格式号::构造(1398362929);
const 底座目标字宽: u16 = 64;
const 底座标识串: &[u8] = b"9c0e4a6494ca0f5ba0840237e3ec86d2\0";
const 底座名称: &[u8] = "PDF支持库\0".as_bytes();
const 底座说明: &[u8] =
    "macOS Apple Silicon原生PDFKit；PDF绝对路径转页数/加密/渲染PNG/内嵌JPEG与结构校验JSON文本；不修改源文件。\0"
        .as_bytes();
const 底座实现版本: v1_contract::版本三元组 = v1_contract::版本三元组::构造(0, 1, 0);
const 底座要求宿主版本: v1_contract::版本要求 = v1_contract::版本要求::构造(1, 0);
const 底座要求内核版本: v1_contract::版本要求 = v1_contract::版本要求::构造(1, 0);
const 底座能力号段: [v1_contract::号段; 1] = [v1_contract::号段::构造(6601, 6699)];
const 底座错误段位表: [u32; 1] = [6];

const fn 底座能力号段表段() -> 表段<v1_contract::号段> {
    表段::构造(底座能力号段.as_ptr(), 1)
}
const fn 底座错误段位表段() -> 表段<u32> {
    表段::构造(底座错误段位表.as_ptr(), 1)
}

#[repr(transparent)]
struct 静态命令表(pub(crate) [命令信息; 命令表项数]);
// SAFETY: 表一旦构造即终生不变；不提供 &mut 通道，对外只交出 *const 指针。
unsafe impl Sync for 静态命令表 {}
unsafe impl Send for 静态命令表 {}

static 命令表存储: 静态命令表 = 静态命令表(造命令表());

#[repr(transparent)]
struct 静态声明(平台信息);
// SAFETY: 静态声明一旦构造即终生不变；只交出 *const 指针，多线程共享只读安全。
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
pub fn 扩展声明() -> &'static 平台信息 {
    &扩展存储.0
}
