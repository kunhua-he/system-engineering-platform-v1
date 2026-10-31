use std::ffi::{CStr, CString};
use std::fmt;
use std::os::raw::{c_char, c_int, c_void};
use std::ptr::NonNull;

#[repr(C)]
pub struct PGconn {
    _私有字段: [u8; 0],
}

#[repr(C)]
pub struct PGresult {
    _私有字段: [u8; 0],
}

#[repr(C)]
pub struct PGcancel {
    _私有字段: [u8; 0],
}

unsafe extern "C" {
    fn PQconnectdb(连接信息: *const c_char) -> *mut PGconn;
    fn PQstatus(连接: *const PGconn) -> c_int;
    fn PQerrorMessage(连接: *const PGconn) -> *const c_char;
    fn PQfinish(连接: *mut PGconn);
    fn PQbackendPID(连接: *const PGconn) -> c_int;
    fn PQexec(连接: *mut PGconn, 语句: *const c_char) -> *mut PGresult;
    fn PQresultStatus(结果: *const PGresult) -> c_int;
    fn PQresultErrorMessage(结果: *const PGresult) -> *const c_char;
    fn PQntuples(结果: *const PGresult) -> c_int;
    fn PQgetvalue(结果: *const PGresult, 行: c_int, 列: c_int) -> *mut c_char;
    fn PQclear(结果: *mut PGresult);
    fn PQgetCancel(连接: *mut PGconn) -> *mut PGcancel;
    fn PQcancel(取消: *mut PGcancel, 错误缓冲: *mut c_char, 缓冲长度: c_int) -> c_int;
    fn PQfreeCancel(取消: *mut PGcancel);
    fn PQrequestCancel(连接: *mut PGconn) -> c_int;
    fn PQconsumeInput(连接: *mut PGconn) -> c_int;
    fn PQisBusy(连接: *mut PGconn) -> c_int;
    fn PQgetResult(连接: *mut PGconn) -> *mut PGresult;
    fn PQsendQuery(连接: *mut PGconn, 语句: *const c_char) -> c_int;
    fn PQsetnonblocking(连接: *mut PGconn, 非阻塞: c_int) -> c_int;
    fn PQsocket(连接: *const PGconn) -> c_int;
    fn PQescapeLiteral(连接: *mut PGconn, 字面量: *const c_char, 长度: usize)
    -> *mut c_char;
    fn PQfreemem(内存: *mut c_void);
}

const 连接正常: c_int = 0;
const 执行命令成功: c_int = 1;
const 执行查询成功: c_int = 2;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 数据库错误(pub String);

impl fmt::Display for 数据库错误 {
    fn fmt(&self, 格式: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(格式)
    }
}

impl std::error::Error for 数据库错误 {}

pub struct 数据库连接 {
    原始连接: NonNull<PGconn>,
}

impl 数据库连接 {
    pub fn 建立(连接信息: &str) -> Result<Self, 数据库错误> {
        let 连接信息 =
            CString::new(连接信息).map_err(|_| 数据库错误("连接信息含有 NUL".into()))?;
        let 原始连接 = unsafe { PQconnectdb(连接信息.as_ptr()) };
        let 原始连接 = NonNull::new(原始连接)
            .ok_or_else(|| 数据库错误("PQconnectdb 返回空指针".into()))?;
        let 连接 = Self { 原始连接 };
        if unsafe { PQstatus(连接.原始连接.as_ptr()) } != 连接正常 {
            return Err(数据库错误(连接.错误文本()));
        }
        Ok(连接)
    }

    pub fn 默认连接信息() -> String {
        std::env::var("V1_PG_DSN")
            .unwrap_or_else(|_| "host=127.0.0.1 port=5432 dbname=postgres".into())
    }

    pub fn 后端进程号(&self) -> i32 {
        unsafe { PQbackendPID(self.原始连接.as_ptr()) }
    }

    pub fn 执行命令(&mut self, 语句: &str) -> Result<(), 数据库错误> {
        let 语句 = CString::new(语句).map_err(|_| 数据库错误("SQL 含有 NUL".into()))?;
        let 结果 = unsafe { PQexec(self.原始连接.as_ptr(), 语句.as_ptr()) };
        let 结果 = NonNull::new(结果).ok_or_else(|| 数据库错误(self.错误文本()))?;
        let 状态 = unsafe { PQresultStatus(结果.as_ptr()) };
        let 错误 = if 状态 == 执行命令成功 || 状态 == 执行查询成功 {
            None
        } else {
            Some(unsafe { 结果错误文本(结果.as_ptr()) })
        };
        unsafe { PQclear(结果.as_ptr()) };
        错误.map_or(Ok(()), |消息| Err(数据库错误(消息)))
    }

    pub fn 查询单值(&mut self, 语句: &str) -> Result<String, 数据库错误> {
        let 语句 = CString::new(语句).map_err(|_| 数据库错误("SQL 含有 NUL".into()))?;
        let 结果 = unsafe { PQexec(self.原始连接.as_ptr(), 语句.as_ptr()) };
        let 结果 = NonNull::new(结果).ok_or_else(|| 数据库错误(self.错误文本()))?;
        let 状态 = unsafe { PQresultStatus(结果.as_ptr()) };
        let 取值 = if 状态 == 执行查询成功 && unsafe { PQntuples(结果.as_ptr()) } > 0 {
            let 指针 = unsafe { PQgetvalue(结果.as_ptr(), 0, 0) };
            if 指针.is_null() {
                Err(数据库错误("PQgetvalue 返回空指针".into()))
            } else {
                Ok(unsafe { CStr::from_ptr(指针) }
                    .to_string_lossy()
                    .into_owned())
            }
        } else {
            Err(数据库错误(unsafe { 结果错误文本(结果.as_ptr()) }))
        };
        unsafe { PQclear(结果.as_ptr()) };
        取值
    }

    pub fn 请求取消(&mut self) -> Result<(), 数据库错误> {
        let 取消 = NonNull::new(unsafe { PQgetCancel(self.原始连接.as_ptr()) })
            .ok_or_else(|| 数据库错误("PQgetCancel 返回空指针".into()))?;
        let mut 错误缓冲 = [0 as c_char; 256];
        let 成功 = unsafe {
            PQcancel(
                取消.as_ptr(),
                错误缓冲.as_mut_ptr(),
                错误缓冲.len() as c_int,
            )
        };
        unsafe { PQfreeCancel(取消.as_ptr()) };
        if 成功 == 1 {
            Ok(())
        } else {
            let 消息 = unsafe { CStr::from_ptr(错误缓冲.as_ptr()) }
                .to_string_lossy()
                .into_owned();
            Err(数据库错误(if 消息.is_empty() {
                "PQcancel 失败".into()
            } else {
                消息
            }))
        }
    }

    pub fn 错误文本(&self) -> String {
        let 指针 = unsafe { PQerrorMessage(self.原始连接.as_ptr()) };
        if 指针.is_null() {
            "libpq 未提供错误文本".into()
        } else {
            unsafe { CStr::from_ptr(指针) }
                .to_string_lossy()
                .trim()
                .into()
        }
    }

    pub fn 原始指针(&mut self) -> *mut PGconn {
        self.原始连接.as_ptr()
    }
}

impl Drop for 数据库连接 {
    fn drop(&mut self) {
        unsafe { PQfinish(self.原始连接.as_ptr()) };
    }
}

unsafe fn 结果错误文本(结果: *const PGresult) -> String {
    let 文本 = unsafe { PQresultErrorMessage(结果) };
    if 文本.is_null() {
        "libpq 结果没有错误文本".into()
    } else {
        unsafe { CStr::from_ptr(文本) }
            .to_string_lossy()
            .trim()
            .into()
    }
}

#[allow(dead_code)]
pub fn 取原始套接字(连接: &数据库连接) -> i32 {
    unsafe { PQsocket(连接.原始连接.as_ptr()) }
}

#[allow(dead_code)]
pub fn 设为非阻塞(
    连接: &mut 数据库连接, 非阻塞: bool
) -> Result<(), 数据库错误> {
    let 结果 = unsafe { PQsetnonblocking(连接.原始连接.as_ptr(), i32::from(非阻塞)) };
    if 结果 == 0 {
        Ok(())
    } else {
        Err(数据库错误(连接.错误文本()))
    }
}

#[allow(dead_code)]
pub fn 发送查询(连接: &mut 数据库连接, 语句: &str) -> Result<(), 数据库错误> {
    let 语句 = CString::new(语句).map_err(|_| 数据库错误("SQL 含有 NUL".into()))?;
    if unsafe { PQsendQuery(连接.原始连接.as_ptr(), 语句.as_ptr()) } == 1 {
        Ok(())
    } else {
        Err(数据库错误(连接.错误文本()))
    }
}

#[allow(dead_code)]
pub fn 消费输入(连接: &mut 数据库连接) -> Result<(), 数据库错误> {
    if unsafe { PQconsumeInput(连接.原始连接.as_ptr()) } == 1 {
        Ok(())
    } else {
        Err(数据库错误(连接.错误文本()))
    }
}

#[allow(dead_code)]
pub fn 连接忙碌(连接: &数据库连接) -> bool {
    unsafe { PQisBusy(连接.原始连接.as_ptr()) == 1 }
}

#[allow(dead_code)]
pub fn 取下一个结果(连接: &mut 数据库连接) -> Option<NonNull<PGresult>> {
    NonNull::new(unsafe { PQgetResult(连接.原始连接.as_ptr()) })
}

#[allow(dead_code)]
pub fn 取消当前查询(连接: &mut 数据库连接) -> Result<(), 数据库错误> {
    if unsafe { PQrequestCancel(连接.原始连接.as_ptr()) } == 1 {
        Ok(())
    } else {
        Err(数据库错误(连接.错误文本()))
    }
}

#[allow(dead_code)]
pub fn 清理转义字面量(
    连接: &mut 数据库连接,
    字面量: &str,
) -> Result<String, 数据库错误> {
    let 字面量 = CString::new(字面量).map_err(|_| 数据库错误("字面量含有 NUL".into()))?;
    let 结果 = unsafe {
        PQescapeLiteral(
            连接.原始连接.as_ptr(),
            字面量.as_ptr(),
            字面量.as_bytes().len(),
        )
    };
    let 结果 = NonNull::new(结果).ok_or_else(|| 数据库错误(连接.错误文本()))?;
    let 文本 = unsafe { CStr::from_ptr(结果.as_ptr()) }
        .to_string_lossy()
        .into_owned();
    unsafe { PQfreemem(结果.as_ptr().cast::<c_void>()) };
    Ok(文本)
}
