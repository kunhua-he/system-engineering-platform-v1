use std::fs;
use std::path::Path;
use std::thread;
use std::time::Duration;

use db_seam_research::{代际令牌, 数据库连接, 跨进程租约};

fn 连接信息() -> String {
    数据库连接::默认连接信息()
}

fn 子代租约(路径: &Path, 令牌文本: &str) -> Result<(), String> {
    let 令牌 = 代际令牌::从十六进制(令牌文本).map_err(|错误| 错误.to_string())?;
    let 租约 =
        跨进程租约::接管(路径, 令牌).map_err(|错误| format!("跨进程租约接管失败：{错误:?}"))?;
    println!("LEASE_ATTACHED {}", 租约.令牌().十六进制());
    thread::sleep(Duration::from_millis(50));
    Ok(())
}

fn 子代新建租约(路径: &Path, 令牌文本: &str) -> Result<(), String> {
    let 令牌 = 代际令牌::从十六进制(令牌文本).map_err(|错误| 错误.to_string())?;
    let 租约 =
        跨进程租约::申请(路径, 令牌).map_err(|错误| format!("跨进程租约申请失败：{错误:?}"))?;
    println!("LEASE_CREATED {}", 租约.令牌().十六进制());
    Ok(())
}

fn 子代宿主退出(进程号文件: &Path) -> Result<(), String> {
    let mut 连接 = 数据库连接::建立(&连接信息()).map_err(|错误| format!("PG_BLOCKED：{错误}"))?;
    let 后端进程号 = 连接.后端进程号();
    fs::write(进程号文件, 后端进程号.to_string()).map_err(|错误| 错误.to_string())?;
    连接
        .执行命令("SELECT 1")
        .map_err(|错误| format!("PG 查询失败：{错误}"))?;
    println!("PG_BACKEND_PID {后端进程号}");
    Ok(())
}

fn 主程序() -> Result<(), String> {
    let mut 参数表 = std::env::args().skip(1);
    match 参数表.next().as_deref() {
        Some("child-lease") => {
            let 路径 = 参数表.next().ok_or("缺少租约路径")?;
            let 令牌 = 参数表.next().ok_or("缺少代际令牌")?;
            子代租约(Path::new(&路径), &令牌)
        }
        Some("child-create-lease") => {
            let 路径 = 参数表.next().ok_or("缺少租约路径")?;
            let 令牌 = 参数表.next().ok_or("缺少代际令牌")?;
            子代新建租约(Path::new(&路径), &令牌)
        }
        Some("child-host-exit") => {
            let 路径 = 参数表.next().ok_or("缺少后端进程号文件")?;
            子代宿主退出(Path::new(&路径))
        }
        Some("probe-pg") => {
            let mut 连接 =
                数据库连接::建立(&连接信息()).map_err(|错误| format!("PG_BLOCKED：{错误}"))?;
            println!("PG_BACKEND_PID {}", 连接.后端进程号());
            println!(
                "PG_VALUE {}",
                连接
                    .查询单值("SELECT current_database()")
                    .map_err(|错误| 错误.to_string())?
            );
            Ok(())
        }
        _ => Err("用法：probe-pg | child-lease <路径> <令牌> | child-host-exit <PID文件>".into()),
    }
}

fn main() {
    if let Err(错误) = 主程序() {
        eprintln!("{错误}");
        std::process::exit(2);
    }
}
