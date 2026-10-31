//! libpq所有权边界；所有中文文本均用UTF-8普通字符串。
use crate::编号与码面::错误码;
use serde_json::{Value, json};
use std::ffi::{CString, c_char, c_int, c_void};
use std::time::{Duration, Instant};
#[repr(C)]
struct 连接选项 {
    关键字: *mut c_char,
    环境名: *mut c_char,
    编译默认: *mut c_char,
    选项值: *mut c_char,
    标签文本: *mut c_char,
    显示文本: *mut c_char,
    显示长度: c_int,
}
unsafe extern "C" {
    fn PQconninfoParse(conninfo: *const c_char, errmsg: *mut *mut c_char) -> *mut 连接选项;
    fn PQconninfoFree(connOptions: *mut 连接选项);
    fn PQfreemem(ptr: *mut c_void);
    fn PQconnectStartParams(
        keywords: *const *const c_char,
        values: *const *const c_char,
        expand_dbname: c_int,
    ) -> *mut c_void;
    fn PQconnectPoll(conn: *mut c_void) -> c_int;
    fn PQsetnonblocking(conn: *mut c_void, arg: c_int) -> c_int;
    fn PQsendQueryParams(
        conn: *mut c_void,
        command: *const c_char,
        nParams: c_int,
        paramTypes: *const u32,
        paramValues: *const *const c_char,
        paramLengths: *const c_int,
        paramFormats: *const c_int,
        resultFormat: c_int,
    ) -> c_int;
    fn PQflush(conn: *mut c_void) -> c_int;
    fn PQconsumeInput(conn: *mut c_void) -> c_int;
    fn PQisBusy(conn: *mut c_void) -> c_int;
    fn PQgetResult(conn: *mut c_void) -> *mut c_void;
    fn PQresultStatus(res: *mut c_void) -> c_int;
    fn PQntuples(res: *mut c_void) -> c_int;
    fn PQnfields(res: *mut c_void) -> c_int;
    fn PQfname(res: *mut c_void, field_num: c_int) -> *const c_char;
    fn PQgetisnull(res: *mut c_void, tup_num: c_int, field_num: c_int) -> c_int;
    fn PQgetlength(res: *mut c_void, tup_num: c_int, field_num: c_int) -> c_int;
    fn PQgetvalue(res: *mut c_void, tup_num: c_int, field_num: c_int) -> *const c_char;
    fn PQtransactionStatus(conn: *mut c_void) -> c_int;
    fn PQclear(res: *mut c_void);
    fn PQfinish(conn: *mut c_void);
}
pub(crate) struct 引擎连接 {
    原生连接: *mut c_void,
}
// 连接只在互斥所有权下移动或使用，不同时调用同一PGconn。
unsafe impl Send for 引擎连接 {}
impl Drop for 引擎连接 {
    fn drop(&mut self) {
        unsafe {
            PQfinish(self.原生连接);
        }
    }
}
struct 引擎结果(*mut c_void);
impl Drop for 引擎结果 {
    fn drop(&mut self) {
        unsafe {
            PQclear(self.0);
        }
    }
}
impl 引擎连接 {
    pub(crate) fn 打开(连接文本: &str) -> Result<Self, u32> {
        if 连接文本.is_empty() || 连接文本.len() > 8192 {
            return Err(错误码::连接参数不合法);
        }
        let 连接字串 = CString::new(连接文本).map_err(|_| 错误码::连接参数不合法)?;
        核连接地址(&连接字串)?;
        let 参数名表 = [
            c"dbname".as_ptr(),
            c"connect_timeout".as_ptr(),
            c"client_encoding".as_ptr(),
            c"options".as_ptr(),
            std::ptr::null(),
        ];
        let 参数值表 = [
            连接字串.as_ptr(),
            c"1".as_ptr(),
            c"UTF8".as_ptr(),
            c"-c statement_timeout=400 -c lock_timeout=200".as_ptr(),
            std::ptr::null(),
        ];
        let 原生连接 =
            unsafe { PQconnectStartParams(参数名表.as_ptr(), 参数值表.as_ptr(), 1) };
        if 原生连接.is_null() {
            return Err(错误码::连接建立失败);
        }
        let 连接对象 = Self { 原生连接 };
        let 截止时刻 = Instant::now() + Duration::from_millis(800);
        loop {
            let 连接状态 = unsafe { PQconnectPoll(原生连接) };
            match 连接状态 {
                0 => return Err(错误码::连接建立失败),
                3 => break,
                _ => {}
            }
            if Instant::now() >= 截止时刻 {
                return Err(错误码::连接建立失败);
            }
            std::thread::sleep(Duration::from_millis(1));
        }
        if unsafe { PQsetnonblocking(原生连接, 1) } != 0 {
            return Err(错误码::连接建立失败);
        }
        Ok(连接对象)
    }
    pub(crate) fn 执行(
        &mut self, 语句文本: &str, 截止时刻: Instant
    ) -> Result<Value, u32> {
        let 语句字串 = CString::new(语句文本).map_err(|_| 错误码::连接参数不合法)?;
        if unsafe {
            PQsendQueryParams(
                self.原生连接,
                语句字串.as_ptr(),
                0,
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
                0,
            )
        } != 1
        {
            return Err(错误码::连接不可继续);
        }
        loop {
            let 刷新状态 = unsafe { PQflush(self.原生连接) };
            if 刷新状态 < 0 || unsafe { PQconsumeInput(self.原生连接) } != 1 {
                return Err(错误码::连接不可继续);
            }
            if 刷新状态 == 0 && unsafe { PQisBusy(self.原生连接) } == 0 {
                break;
            }
            if Instant::now() >= 截止时刻 {
                return Err(错误码::连接不可继续);
            }
            std::thread::sleep(Duration::from_millis(1));
        }
        let 原生结果 = unsafe { PQgetResult(self.原生连接) };
        if 原生结果.is_null() {
            return Err(错误码::连接不可继续);
        }
        let 结果对象 = 引擎结果(原生结果);
        let 结果状态 = unsafe { PQresultStatus(结果对象.0) };
        if ![1, 2].contains(&结果状态) {
            // COPY状态尚未完成，不能继续复用这条连接。
            if [3, 4, 8].contains(&结果状态) {
                return Err(错误码::连接不可继续);
            }
            let 后续结果 = unsafe { PQgetResult(self.原生连接) };
            if !后续结果.is_null() {
                unsafe { PQclear(后续结果) };
                return Err(错误码::连接不可继续);
            }
            return Err(错误码::数据库语句失败);
        }
        let 查询返回 = 读取结果(结果对象.0);
        let 后续结果 = unsafe { PQgetResult(self.原生连接) };
        if !后续结果.is_null() {
            unsafe { PQclear(后续结果) };
            return Err(错误码::连接不可继续);
        }
        查询返回
    }
    pub(crate) fn 空闲(&self) -> bool {
        unsafe { PQtransactionStatus(self.原生连接) == 0 }
    }
}
fn 核连接地址(连接字串: &CString) -> Result<(), u32> {
    let mut 解析错误 = std::ptr::null_mut();
    let 选项表 = unsafe { PQconninfoParse(连接字串.as_ptr(), &mut 解析错误) };
    if !解析错误.is_null() {
        unsafe { PQfreemem(解析错误 as *mut c_void) };
    }
    if 选项表.is_null() {
        return Err(错误码::连接参数不合法);
    }
    let mut 目标主机 = String::new();
    let mut 主机地址 = String::new();
    let mut 选项序号 = 0;
    loop {
        let 当前选项 = unsafe { &*选项表.add(选项序号) };
        if 当前选项.关键字.is_null() {
            break;
        }
        if !当前选项.选项值.is_null() {
            let 关键字节 = unsafe { std::ffi::CStr::from_ptr(当前选项.关键字) }.to_bytes();
            let 选项文本 = unsafe { std::ffi::CStr::from_ptr(当前选项.选项值) }.to_string_lossy();
            if 关键字节 == b"host" {
                目标主机 = 选项文本.into_owned();
            } else if 关键字节 == b"hostaddr" {
                主机地址 = 选项文本.into_owned();
            }
        }
        选项序号 += 1;
    }
    unsafe { PQconninfoFree(选项表) };
    // 不进入名称解析器，不隐式取环境里的远程主机。
    let 地址合法 = if !主机地址.is_empty() {
        主机地址.parse::<std::net::IpAddr>().is_ok()
    } else {
        目标主机.starts_with('/') || 目标主机.parse::<std::net::IpAddr>().is_ok()
    };
    if 地址合法 {
        Ok(())
    } else {
        Err(错误码::连接参数不合法)
    }
}
fn 读取结果(原生结果: *mut c_void) -> Result<Value, u32> {
    let 行数 = unsafe { PQntuples(原生结果) };
    let 列数 = unsafe { PQnfields(原生结果) };
    if !(0..=1024).contains(&行数) || !(0..=64).contains(&列数) {
        return Err(错误码::查询结果越界);
    }
    let mut 列名列表 = Vec::new();
    let mut 行列表 = Vec::new();
    let mut 字节总数 = 0usize;
    for 列序号 in 0..列数 {
        let 名称指针 = unsafe { PQfname(原生结果, 列序号) };
        if 名称指针.is_null() {
            return Err(错误码::数据库语句失败);
        }
        let 列名文本 = unsafe { std::ffi::CStr::from_ptr(名称指针) }
            .to_str()
            .map_err(|_| 错误码::数据库语句失败)?;
        列名列表.push(列名文本.to_owned());
    }
    for 行序号 in 0..行数 {
        let mut 行值列表 = Vec::new();
        for 列序号 in 0..列数 {
            if unsafe { PQgetisnull(原生结果, 行序号, 列序号) } != 0 {
                行值列表.push(Value::Null);
                continue;
            }
            let 字节长度 = unsafe { PQgetlength(原生结果, 行序号, 列序号) } as usize;
            字节总数 = 字节总数.checked_add(字节长度).ok_or(错误码::查询结果越界)?;
            if 字节长度 > 65536 || 字节总数 > 262144 {
                return Err(错误码::查询结果越界);
            }
            let 单元字节 = unsafe {
                std::slice::from_raw_parts(
                    PQgetvalue(原生结果, 行序号, 列序号) as *const u8,
                    字节长度,
                )
            };
            let 单元文本 =
                std::str::from_utf8(单元字节).map_err(|_| 错误码::数据库语句失败)?;
            行值列表.push(Value::String(单元文本.to_owned()));
        }
        行列表.push(行值列表);
    }
    Ok(json!({"列名列表":列名列表,"行列表":行列表}))
}
pub(crate) fn 核语句(语句文本: &str, 只读: bool) -> Result<(), u32> {
    if 语句文本.len() > 65536 || 语句文本.contains('\0') {
        return Err(错误码::连接参数不合法);
    }
    let 首关键字 = 语句文本
        .trim_start()
        .split(|待判字符: char| !待判字符.is_ascii_alphabetic())
        .next()
        .unwrap_or("")
        .to_ascii_uppercase();
    let 允许关键字 = if 只读 {
        &["SELECT", "WITH", "VALUES", "TABLE"][..]
    } else {
        &[
            "SELECT", "WITH", "VALUES", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP",
            "TRUNCATE",
        ][..]
    };
    if !允许关键字.contains(&首关键字.as_str()) {
        return Err(错误码::连接参数不合法);
    }
    Ok(())
}
