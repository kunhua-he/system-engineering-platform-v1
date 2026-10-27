//! 案例读盘的正/反向样本 —— 从 `案例.rs` 拆出（单源文件 ≤400 行的硬数）。
//!
//! 口径与 `案例.rs` 同源，不另立一套；`use super::*` 取它的读盘件与私有函数。

use super::*;

#[test]
fn 十六进制按空白分组也解得对() {
    assert_eq!(解十六进制("4e 4f 54").unwrap(), b"NOT");
    assert_eq!(解十六进制("0a0b").unwrap(), vec![0x0a, 0x0b]);
    assert!(解十六进制("4e4").is_err(), "奇数位该被拒");
    assert!(解十六进制("zz").is_err(), "非十六进制该被拒");
}

#[test]
fn 相对路按案例目录解_绝对路原样() {
    assert_eq!(解路(Path::new("/首目录/次目录"), Path::new("末件.txt")), PathBuf::from("/首目录/次目录/末件.txt"));
    assert_eq!(解路(Path::new("/首目录/次目录"), Path::new("/末目录/末子目录")), PathBuf::from("/末目录/末子目录"));
}

/// 建一个唯一的临时案例根（测试自清；不落仓内）。
fn 建临时案例根(标记: &str) -> PathBuf {
    let 案例根 = std::env::temp_dir().join(format!("v1-案例读盘-{标记}-{}", std::process::id()));
    std::fs::remove_dir_all(&案例根).ok();
    std::fs::create_dir_all(&案例根).expect("建临时案例根");
    案例根
}

/// **4787 正例**：真空目录不是案例 ⇒ 不当成「缺 `案例.json`」报错。
#[test]
fn 真空目录不算案例() {
    let 案例根 = 建临时案例根("空目录");
    std::fs::create_dir(案例根.join("删件残留的空目录")).expect("建空目录");
    std::fs::create_dir(案例根.join("跑案例")).expect("建非案例目录");
    let 错误 = 读全部(&案例根).unwrap_err();
    assert!(
        错误.contains("0 个案例目录"),
        "真空目录要跳过（剩下 0 个 ⇒ 报空集），不能报成缺 `案例.json`；实得：{错误}"
    );
    std::fs::remove_dir_all(&案例根).ok();
}

/// **4787 反例**：非空却缺 `案例.json` 仍是工具错误（破损案例不许静默跳过）。
#[test]
fn 非空缺案例清单仍报错() {
    let 案例根 = 建临时案例根("非空");
    let 破损案例 = 案例根.join("破损案例");
    std::fs::create_dir(&破损案例).expect("建破损案例目录");
    std::fs::write(破损案例.join("期望.json"), "{}").expect("写期望");
    let 错误 = 读全部(&案例根).unwrap_err();
    assert!(
        错误.contains("案例.json"),
        "非空目录缺 `案例.json` 必须点名报错；实得：{错误}"
    );
    std::fs::remove_dir_all(&案例根).ok();
}

/// 反向样本：不认的 `来源` 必须报错，不许静默当成某个默认值。
#[test]
fn 不认的来源报错() {
    let 案例清单 = 最小JSON::解析JSON值(r#"{"步骤":[{"名":"首项","能力编号":1,"实参":[{"类型标签":4,"来源":"猜"}]}]}"#).unwrap();
    assert!(读步骤(&案例清单, Path::new("/首案例")).is_err());
}
