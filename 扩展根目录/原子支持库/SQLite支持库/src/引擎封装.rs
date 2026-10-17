//! 系统SQLite引擎的唯一封装；连接与语句由各自析构回收，不持有全局状态。
use crate::编号与码面::错误码;
use std::ffi::{CStr, CString, c_char, c_int, c_void};
use v1_contract::复合值载荷::{复合值, 复合元素};

#[link(name = "sqlite3")]
unsafe extern "C" {
    #[link_name = "sqlite3_open_v2"]
    fn sqlite_open_database(
        路径: *const c_char,
        连接: *mut *mut c_void,
        打开标志: c_int,
        后端: *const c_char,
    ) -> c_int;
    #[link_name = "sqlite3_close"]
    fn sqlite_close_database(连接: *mut c_void) -> c_int;
    #[link_name = "sqlite3_limit"]
    fn sqlite_set_limit(连接: *mut c_void, 限制类别: c_int, 限制数值: c_int) -> c_int;
    #[link_name = "sqlite3_busy_timeout"]
    fn sqlite_set_busy_timeout(连接: *mut c_void, 等待毫秒: c_int) -> c_int;
    #[link_name = "sqlite3_exec"]
    fn sqlite_execute_sql(
        连接: *mut c_void,
        SQL文本: *const c_char,
        回调: *const c_void,
        上下文: *mut c_void,
        错文: *mut *mut c_char,
    ) -> c_int;
    #[link_name = "sqlite3_set_authorizer"]
    fn sqlite_set_authorizer(
        连接: *mut c_void,
        回调: Option<
            unsafe extern "C" fn(
                *mut c_void,
                c_int,
                *const c_char,
                *const c_char,
                *const c_char,
                *const c_char,
            ) -> c_int,
        >,
        上下文: *mut c_void,
    ) -> c_int;
    #[link_name = "sqlite3_prepare_v2"]
    fn sqlite_prepare_statement(
        连接: *mut c_void,
        SQL文本: *const c_char,
        SQL长度: c_int,
        语句: *mut *mut c_void,
        尾部: *mut *const c_char,
    ) -> c_int;
    #[link_name = "sqlite3_finalize"]
    fn sqlite_finalize_statement(语句: *mut c_void) -> c_int;
    #[link_name = "sqlite3_stmt_readonly"]
    fn sqlite_statement_readonly(语句: *mut c_void) -> c_int;
    #[link_name = "sqlite3_step"]
    fn sqlite_step_statement(语句: *mut c_void) -> c_int;
    #[link_name = "sqlite3_column_count"]
    fn sqlite_column_count(语句: *mut c_void) -> c_int;
    #[link_name = "sqlite3_column_name"]
    fn sqlite_column_name(语句: *mut c_void, 列序: c_int) -> *const c_char;
    #[link_name = "sqlite3_column_type"]
    fn sqlite_column_type(语句: *mut c_void, 列序: c_int) -> c_int;
    #[link_name = "sqlite3_column_int64"]
    fn sqlite_column_integer(语句: *mut c_void, 列序: c_int) -> i64;
    #[link_name = "sqlite3_column_double"]
    fn sqlite_column_double(语句: *mut c_void, 列序: c_int) -> f64;
    #[link_name = "sqlite3_column_text"]
    fn sqlite_column_text(语句: *mut c_void, 列序: c_int) -> *const u8;
    #[link_name = "sqlite3_column_blob"]
    fn sqlite_column_blob(语句: *mut c_void, 列序: c_int) -> *const u8;
    #[link_name = "sqlite3_column_bytes"]
    fn sqlite_column_bytes(语句: *mut c_void, 列序: c_int) -> c_int;
    #[link_name = "sqlite3_progress_handler"]
    fn sqlite_set_progress_handler(
        连接: *mut c_void,
        步数: c_int,
        回调: Option<unsafe extern "C" fn(*mut c_void) -> c_int>,
        上下文: *mut c_void,
    );
}

struct 数据库连接(*mut c_void);
impl Drop for 数据库连接 {
    fn drop(&mut self) {
        unsafe {
            sqlite_close_database(self.0);
        }
    }
}
struct 数据库语句(*mut c_void);
impl Drop for 数据库语句 {
    fn drop(&mut self) {
        unsafe {
            sqlite_finalize_statement(self.0);
        }
    }
}
fn 映射引擎码(引擎码: c_int) -> u32 {
    match 引擎码 & 255 {
        5 | 6 | 9 | 18 => 错误码::数据库资源受限,
        _ => 错误码::数据库语句失败,
    }
}
fn 开连接(数据库路径: &str, 只读: bool) -> Result<数据库连接, u32> {
    if !std::path::Path::new(数据库路径).is_absolute() {
        return Err(错误码::数据库参数不合法);
    }
    let 路径文本 = CString::new(数据库路径).map_err(|_| 错误码::数据库参数不合法)?;
    let mut 连接指针 = std::ptr::null_mut();
    let 状态码 = unsafe {
        sqlite_open_database(
            路径文本.as_ptr(),
            &mut 连接指针,
            if 只读 { 1 } else { 6 },
            std::ptr::null(),
        )
    };
    if 状态码 != 0 {
        if !连接指针.is_null() {
            unsafe {
                sqlite_close_database(连接指针);
            }
        }
        return Err(错误码::数据库打开失败);
    }
    let 连接对象 = 数据库连接(连接指针);
    unsafe {
        sqlite_set_busy_timeout(连接指针, 200);
        sqlite_set_limit(连接指针, 0, 1048576);
        sqlite_set_limit(连接指针, 1, 65536);
    }
    Ok(连接对象)
}
unsafe extern "C" fn 拒事务控制(
    _: *mut c_void,
    动作号: c_int,
    _: *const c_char,
    _: *const c_char,
    _: *const c_char,
    _: *const c_char,
) -> c_int {
    if [19, 22, 24, 25, 32].contains(&动作号) {
        1
    } else {
        0
    }
}
unsafe extern "C" fn 检查截止(上下文: *mut c_void) -> c_int {
    let 截止时刻 = unsafe { &*(上下文 as *const std::time::Instant) };
    i32::from(std::time::Instant::now() >= *截止时刻)
}
fn 装预算(连接对象: &数据库连接, 截止时刻: &mut std::time::Instant) {
    unsafe {
        sqlite_set_progress_handler(
            连接对象.0,
            1000,
            Some(检查截止),
            (截止时刻 as *mut std::time::Instant).cast(),
        );
    }
}
fn 跑SQL(连接对象: &数据库连接, SQL文本: &str) -> Result<(), u32> {
    let SQL字串 = CString::new(SQL文本).map_err(|_| 错误码::数据库参数不合法)?;
    let 状态码 = unsafe {
        sqlite_execute_sql(
            连接对象.0,
            SQL字串.as_ptr(),
            std::ptr::null(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
        )
    };
    if 状态码 == 0 {
        Ok(())
    } else {
        Err(映射引擎码(状态码))
    }
}
pub fn 执行事务(数据库路径: &str, 语句列表: &[String]) -> Result<i64, u32> {
    if 语句列表.is_empty()
        || 语句列表.len() > 64
        || 语句列表.iter().any(|语句文本| {
            语句文本.len() > 65536 || 语句文本.trim().is_empty() || 语句文本.contains('\0')
        })
    {
        return Err(错误码::数据库参数不合法);
    }
    let 连接对象 = 开连接(数据库路径, false)?;
    跑SQL(&连接对象, "BEGIN IMMEDIATE")?;
    let mut 截止时刻 = std::time::Instant::now() + std::time::Duration::from_millis(500);
    装预算(&连接对象, &mut 截止时刻);
    unsafe {
        sqlite_set_authorizer(连接对象.0, Some(拒事务控制), std::ptr::null_mut());
    }
    let 执行结果 = 语句列表
        .iter()
        .try_for_each(|语句文本| 跑SQL(&连接对象, 语句文本));
    unsafe {
        sqlite_set_authorizer(连接对象.0, None, std::ptr::null_mut());
        sqlite_set_progress_handler(连接对象.0, 0, None, std::ptr::null_mut());
    }
    match 执行结果 {
        Ok(()) => {
            跑SQL(&连接对象, "COMMIT")?;
            Ok(语句列表.len() as i64)
        }
        Err(失败码) => {
            let _ = 跑SQL(&连接对象, "ROLLBACK");
            Err(失败码)
        }
    }
}
fn 列元素(值: 复合值) -> 复合元素 {
    复合元素 {
        名称: String::new(),
        值,
    }
}
unsafe fn 读列值(语句指针: *mut c_void, 列序: c_int) -> Result<复合值, u32> {
    Ok(match unsafe { sqlite_column_type(语句指针, 列序) } {
        1 => 复合值::整数值(unsafe { sqlite_column_integer(语句指针, 列序) }),
        2 => 复合值::双精度(unsafe { sqlite_column_double(语句指针, 列序) }),
        3 | 4 => {
            let 列类型 = unsafe { sqlite_column_type(语句指针, 列序) };
            let 列指针 = if 列类型 == 3 {
                unsafe { sqlite_column_text(语句指针, 列序) }
            } else {
                unsafe { sqlite_column_blob(语句指针, 列序) }
            };
            let 列长度 = unsafe { sqlite_column_bytes(语句指针, 列序) } as usize;
            if 列长度 > 65536 {
                return Err(错误码::数据库查询越界);
            }
            let 列字节 = if 列长度 == 0 {
                &[][..]
            } else if 列指针.is_null() {
                return Err(错误码::数据库语句失败);
            } else {
                unsafe { std::slice::from_raw_parts(列指针, 列长度) }
            };
            if 列类型 == 3 {
                复合值::文本载荷(
                    std::str::from_utf8(列字节)
                        .map_err(|_| 错误码::数据库语句失败)?
                        .to_owned(),
                )
            } else {
                复合值::字节集(列字节.to_vec())
            }
        }
        _ => 复合值::无值,
    })
}
pub fn 只读查询(数据库路径: &str, 查询语句: &str) -> Result<Vec<复合元素>, u32> {
    if 查询语句.trim().is_empty() || 查询语句.len() > 65536 {
        return Err(错误码::数据库参数不合法);
    }
    let SQL字串 = CString::new(查询语句).map_err(|_| 错误码::数据库参数不合法)?;
    let 连接对象 = 开连接(数据库路径, true)?;
    let mut 截止时刻 = std::time::Instant::now() + std::time::Duration::from_millis(500);
    装预算(&连接对象, &mut 截止时刻);
    unsafe {
        sqlite_set_authorizer(连接对象.0, Some(拒事务控制), std::ptr::null_mut());
    }
    let mut 语句指针 = std::ptr::null_mut();
    let mut 尾部指针 = std::ptr::null();
    let 准备码 = unsafe {
        sqlite_prepare_statement(
            连接对象.0,
            SQL字串.as_ptr(),
            -1,
            &mut 语句指针,
            &mut 尾部指针,
        )
    };
    if 准备码 != 0 || 语句指针.is_null() {
        if !语句指针.is_null() {
            unsafe {
                sqlite_finalize_statement(语句指针);
            }
        }
        return Err(映射引擎码(准备码));
    }
    let 语句对象 = 数据库语句(语句指针);
    if unsafe { sqlite_statement_readonly(语句对象.0) } == 0
        || !unsafe { CStr::from_ptr(尾部指针) }
            .to_bytes()
            .iter()
            .all(u8::is_ascii_whitespace)
    {
        return Err(错误码::数据库参数不合法);
    }
    let 列数 = unsafe { sqlite_column_count(语句对象.0) };
    if !(1..=64).contains(&列数) {
        return Err(错误码::数据库查询越界);
    }
    let 列名列表 = (0..列数)
        .map(|列序| {
            列元素(复合值::文本载荷(
                unsafe { CStr::from_ptr(sqlite_column_name(语句对象.0, 列序)) }
                    .to_string_lossy()
                    .into_owned(),
            ))
        })
        .collect();
    let mut 行列表 = Vec::new();
    let mut 累计字节数 = 0usize;
    loop {
        match unsafe { sqlite_step_statement(语句对象.0) } {
            101 => break,
            100 => {
                if 行列表.len() >= 1024 {
                    return Err(错误码::数据库查询越界);
                }
                let mut 行值列表 = Vec::new();
                for 列序 in 0..列数 {
                    let 列值 = unsafe { 读列值(语句对象.0, 列序) }?;
                    累计字节数 += match &列值 {
                        复合值::文本载荷(文本值) => 文本值.len(),
                        复合值::字节集(字节值) => 字节值.len(),
                        _ => 8,
                    };
                    if 累计字节数 > 262144 {
                        return Err(错误码::数据库查询越界);
                    }
                    行值列表.push(列元素(列值));
                }
                行列表.push(列元素(复合值::复合 {
                    标签: 100,
                    元素表: 行值列表,
                }));
            }
            失败码 => return Err(映射引擎码(失败码)),
        }
    }
    Ok(vec![
        复合元素 {
            名称: "列名列表".to_owned(),
            值: 复合值::复合 {
                标签: 100,
                元素表: 列名列表,
            },
        },
        复合元素 {
            名称: "行列表".to_owned(),
            值: 复合值::复合 {
                标签: 100,
                元素表: 行列表,
            },
        },
    ])
}
